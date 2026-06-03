"""Web API (FastAPI) testleri — TestClient ile, çevrimdışı.

Hem işlevsellik hem güvenlik davranışlarını kapsar:
- status / backtest uçları çalışıyor
- güvenlik başlıkları (CSP vb.) her yanıtta var
- PDF upload doğrulaması kötü içeriği reddediyor
- dosya adı temizleme path-traversal'ı engelliyor
"""

from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

from app.web import security  # noqa: E402
from app.web.server import app  # noqa: E402


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_status_ok(client: TestClient) -> None:
    r = client.get("/api/status")
    assert r.status_code == 200
    body = r.json()
    assert "embedding_mode" in body
    assert "n_papers" in body
    # fake embedding test ortamında bekleniyor
    assert body["embedding_mode"] in {"fake", "ollama"}


def test_security_headers_present(client: TestClient) -> None:
    r = client.get("/api/status")
    assert "content-security-policy" in {k.lower() for k in r.headers}
    assert r.headers.get("x-frame-options") == "DENY"
    assert r.headers.get("x-content-type-options") == "nosniff"


def test_papers_empty_or_list(client: TestClient) -> None:
    r = client.get("/api/papers")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_backtest_synthetic_runs(client: TestClient) -> None:
    r = client.post("/api/backtest", json={"use_synthetic": True, "n_bars": 800, "seed": 7})
    assert r.status_code == 200
    body = r.json()
    assert body["verdict"] in {"pass", "fail", "inconclusive"}
    assert "metrics" in body and "n_trades" in body["metrics"]


def test_backtest_rejects_csv_mode(client: TestClient) -> None:
    r = client.post("/api/backtest", json={"use_synthetic": False})
    assert r.status_code == 400


def test_ask_validation_rejects_short(client: TestClient) -> None:
    r = client.post("/api/ask", json={"question": "x"})
    assert r.status_code == 422  # pydantic min_length


def test_card_unknown_paper_404(client: TestClient) -> None:
    r = client.post("/api/card/paper_does_not_exist")
    assert r.status_code == 404


def test_get_card_unknown_404(client: TestClient) -> None:
    r = client.get("/api/card/paper_yok")
    assert r.status_code == 404


def test_get_card_after_save(client: TestClient) -> None:
    from app.memory.sqlite_store import SqliteStore

    s = SqliteStore()
    s.upsert_paper(paper_id="paper_t1", file_hash="hcard1", source_path="/tmp/x.pdf", title="T")
    s.save_knowledge_card(
        card_id="card_t1",
        paper_id="paper_t1",
        model="test",
        card={"paper_id": "paper_t1", "title": "T", "main_claim": "x"},
    )
    r = client.get("/api/card/paper_t1")
    assert r.status_code == 200
    assert r.json()["card"]["title"] == "T"


# ---- güvenlik birim testleri ----
def test_validate_pdf_rejects_non_pdf() -> None:
    with pytest.raises(fastapi.HTTPException):
        security.validate_pdf_upload("evil.pdf", b"not a real pdf")


def test_validate_pdf_rejects_wrong_extension() -> None:
    with pytest.raises(fastapi.HTTPException):
        security.validate_pdf_upload("evil.exe", b"%PDF-1.7 ...")


def test_validate_pdf_accepts_valid() -> None:
    name = security.validate_pdf_upload("My Paper (v2).pdf", b"%PDF-1.7\n%%EOF")
    assert name.endswith(".pdf")
    assert "/" not in name and "\\" not in name


def test_sanitize_filename_blocks_traversal() -> None:
    safe = security.sanitize_filename("../../etc/passwd.pdf")
    assert ".." not in safe
    assert "/" not in safe
    assert safe.endswith(".pdf")


def test_validate_csv_accepts_ohlcv_header() -> None:
    name = security.validate_csv_upload(
        "data.csv", b"time,open,high,low,close,volume\n2020-01-01,1,2,0.5,1.5,10\n"
    )
    assert name.endswith(".csv")


def test_validate_csv_rejects_missing_columns() -> None:
    with pytest.raises(fastapi.HTTPException):
        security.validate_csv_upload("bad.csv", b"a,b,c\n1,2,3\n")


def test_validate_csv_rejects_non_csv() -> None:
    with pytest.raises(fastapi.HTTPException):
        security.validate_csv_upload("x.txt", b"time,open,high,low,close\n")


def _make_ohlcv_csv(n: int = 150) -> bytes:
    import datetime as dt

    base = dt.datetime(2021, 1, 1, tzinfo=dt.UTC)
    lines = ["time,open,high,low,close,volume"]
    price = 100.0
    for i in range(n):
        price *= 1.004 if i % 3 == 0 else 0.998
        o, h, lo = price, price * 1.01, price * 0.99
        c = price * (1.006 if i % 2 else 0.996)
        ts = (base + dt.timedelta(days=i)).isoformat()
        lines.append(f"{ts},{o:.4f},{h:.4f},{lo:.4f},{c:.4f},{100 + i}")
    return ("\n".join(lines) + "\n").encode()


def test_backtest_csv_real_runs(client: TestClient) -> None:
    import os

    from app.config import get_settings

    csv = _make_ohlcv_csv(150)
    r = client.post("/api/backtest/csv", files={"file": ("webtest_ohlcv.csv", csv, "text/csv")})
    try:
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["verdict"] in {"pass", "fail", "inconclusive"}
        assert body["n_bars"] >= 50
        assert body["data_source"]
        assert "n_trades" in body["metrics"]
    finally:
        p = get_settings().market_raw_dir / "webtest_ohlcv.csv"
        if p.exists():
            os.remove(p)


def test_backtest_csv_rejects_bad_columns(client: TestClient) -> None:
    r = client.post("/api/backtest/csv", files={"file": ("bad.csv", b"a,b,c\n1,2,3\n", "text/csv")})
    assert r.status_code == 400


def test_rate_limiter_blocks_after_limit() -> None:
    rl = security.RateLimiter(per_minute=3)
    for _ in range(3):
        rl.check("1.2.3.4")
    with pytest.raises(fastapi.HTTPException):
        rl.check("1.2.3.4")
    # farklı IP etkilenmez
    rl.check("5.6.7.8")


def test_auth_enforced_when_token_set(monkeypatch) -> None:
    """API token ayarlıysa token'sız istek 401 almalı; doğru token 200."""
    import os

    from app.config import get_settings as _gs

    monkeypatch.setenv("ACHILLES_API_TOKEN", "s3cr3t-token")
    os.environ["ACHILLES_ALLOW_FAKE_EMBEDDINGS"] = "true"
    _gs.cache_clear()
    try:
        c = TestClient(app)
        # token yok -> 401
        assert c.get("/api/status").status_code == 401
        # yanlış token -> 401
        assert c.get("/api/status", headers={"Authorization": "Bearer wrong"}).status_code == 401
        # doğru token -> 200
        assert (
            c.get("/api/status", headers={"Authorization": "Bearer s3cr3t-token"}).status_code
            == 200
        )
    finally:
        monkeypatch.delenv("ACHILLES_API_TOKEN", raising=False)
        _gs.cache_clear()
