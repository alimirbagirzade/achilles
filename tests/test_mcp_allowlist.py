"""MCP tool yüzeyi testleri — allow-list + token iletimi.

Sözleşme:
- Yasak uçlar (onay, kill-switch, eğitim başlatma, autodrive) tool listesinde YOK.
- İzin verilen salt-okuma uçları VAR.
- ``ACHILLES_API_TOKEN`` ayarlıysa proxy istemcisi Authorization başlığı taşır.
- Token'lı modda gerçek bir MCP çağrısı 200 döner (uçtan uca).

Tümü çevrimdışı: web uygulaması ASGI transport ile bellek içinde konuşulur.
"""

from __future__ import annotations

import httpx
import pytest
from mcp_server import allowlist
from mcp_server.achilles_mcp import auth_headers


@pytest.fixture(scope="module")
def spec() -> dict:
    from app.web.server import app

    return app.openapi()


@pytest.fixture(scope="module")
def filtered(spec: dict) -> dict:
    return allowlist.filter_spec(spec)


def _operations(s: dict) -> set[tuple[str, str]]:
    """Spec'teki (METOD, path) operasyon kümesi."""
    return {
        (method.upper(), path)
        for path, item in s.get("paths", {}).items()
        for method in item
        if method.lower() in allowlist._HTTP_METHODS
    }


# --- Yasak uçlar tool listesinde YOK ---------------------------------------------


# Not: `/api/training/run`, `/api/approvals/*` ve `/api/supervisor/clear-stop-all`
# zaten `include_in_schema=False` ile spec dışıdır; yine de burada test edilir ki
# o bayrak kaldırılırsa allow-list'in hâlâ tuttuğu görülsün (iki bağımsız katman).
@pytest.mark.parametrize(
    "path",
    [
        "/api/approvals",
        "/api/approvals/{approval_id}/approve",
        "/api/approvals/{approval_id}/reject",
        "/api/supervisor/stop-all",
        "/api/supervisor/clear-stop-all",
        "/api/training/run",
        "/api/training/stop",
        "/api/training/dataset",
        "/api/orchestration/start",
        "/api/orchestration/autodrive/{run_id}",
        "/api/orchestration/resume/{run_id}",
        "/api/auto-lora/enable",
        "/api/auto-lora/promote",
        "/api/card/{card_id}/approve",
        "/api/card/{card_id}/reject",
        "/api/feedback/approve/{correction_id}",
        "/api/papers/upload",
        "/api/rag-loop/enable",
    ],
)
def test_yasak_uclar_sunulmaz(filtered: dict, path: str) -> None:
    assert path not in filtered["paths"], f"YASAK uç MCP yüzeyinde: {path}"


def test_yazma_metodlari_tamamen_elenir(filtered: dict) -> None:
    """İzin verilen tek yazma ucu /api/ask; başka POST/DELETE/PUT/PATCH kalmamalı."""
    yazma = {(m, p) for m, p in _operations(filtered) if m in {"POST", "PUT", "DELETE", "PATCH"}}
    assert yazma == {("POST", "/api/ask")}, f"Beklenmeyen yazma ucu: {yazma}"


def test_ayni_path_uzerinde_yalniz_izinli_metod_kalir(filtered: dict) -> None:
    """`/api/card/{paper_id}` GET+POST sunar; yalnız GET geçmeli."""
    assert set(filtered["paths"]["/api/card/{paper_id}"]) == {"get"}


# --- İzin verilen uçlar VAR ------------------------------------------------------


@pytest.mark.parametrize(("method", "path"), sorted(allowlist.ALLOWED))
def test_izinli_uclar_sunulur(filtered: dict, method: str, path: str) -> None:
    assert method.lower() in filtered["paths"].get(path, {}), f"İzinli uç düştü: {method} {path}"


def test_filtre_gercekten_daraltiyor(spec: dict, filtered: dict) -> None:
    ham, budanmis = _operations(spec), _operations(filtered)
    assert budanmis == set(allowlist.ALLOWED)
    assert len(budanmis) < len(ham) / 3, "Budama beklenen kadar daraltmadı"


def test_allowlist_spec_ile_uyumlu(spec: dict) -> None:
    """Allow-list girdileri spec'te gerçekten var (route yeniden adlandırma tespiti)."""
    allowlist.verify_allowlist(spec)


def test_yasak_desen_allowlist_e_sizarsa_fail_closed(
    spec: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Allow-list'e tehlikeli bir uç eklenirse kurulum DÜŞER (sessizce açılmaz)."""
    monkeypatch.setattr(allowlist, "ALLOWED", frozenset({("POST", "/api/supervisor/stop-all")}))
    with pytest.raises(allowlist.AllowlistError, match="yasaklı"):
        allowlist.filter_spec(spec)


# --- Token iletimi ---------------------------------------------------------------


def test_token_ayarliysa_authorization_basligi_uretilir(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import get_settings

    monkeypatch.setenv("ACHILLES_API_TOKEN", "gizli-test-token")
    get_settings.cache_clear()
    try:
        assert auth_headers() == {"Authorization": "Bearer gizli-test-token"}
    finally:
        get_settings.cache_clear()


def test_token_yoksa_baslik_gonderilmez(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import get_settings

    monkeypatch.setenv("ACHILLES_API_TOKEN", "")
    get_settings.cache_clear()
    try:
        assert auth_headers() == {}
    finally:
        get_settings.cache_clear()


# --- Keşif yüzeyi: /api/docs + /api/openapi.json ---------------------------------


def _schema_uclari_durumu(token: str) -> tuple[int, int]:
    """Verilen token ayarıyla TAZE bir süreçte şema uçlarının HTTP kodlarını döndür.

    Alt süreç şart: `_expose_schema` modül İMPORT anında hesaplanır; aynı süreçte
    `app.web.server`'ı yeniden yüklemek route'ları/arka plan görevlerini yeniden
    kaydeder ve diğer testleri bozar.
    """
    import json
    import subprocess
    import sys

    code = (
        "import json\n"
        "from fastapi.testclient import TestClient\n"
        "from app.web.server import app\n"
        "c = TestClient(app)\n"
        "tok = __import__('os').environ.get('ACHILLES_API_TOKEN')\n"
        "h = {'Authorization': f'Bearer {tok}'} if tok else {}\n"
        "print(json.dumps([c.get('/api/openapi.json', headers=h).status_code,"
        " c.get('/api/docs', headers=h).status_code]))"
    )
    env = {**__import__("os").environ, "ACHILLES_API_TOKEN": token}
    res = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, env=env, timeout=300
    )
    assert res.returncode == 0, f"alt süreç düştü:\n{res.stderr[-2000:]}"
    codes = json.loads(res.stdout.strip().splitlines()[-1])
    return codes[0], codes[1]


def test_token_yokken_sema_uclari_aciktir() -> None:
    """Yerel varsayılan mod: geliştirici kolaylığı korunur (web UI'yi kırmayız)."""
    openapi, docs = _schema_uclari_durumu("")
    assert (openapi, docs) == (200, 200)


def test_token_varken_sema_uclari_kapatilir() -> None:
    """Ağa-açık mod: kimliksiz route/şema envanteri keşfi kapanır."""
    openapi, docs = _schema_uclari_durumu("gizli-test-token")
    assert (openapi, docs) == (404, 404)


@pytest.mark.anyio
async def test_tokenli_modda_proxy_cagrisi_200_doner(monkeypatch: pytest.MonkeyPatch) -> None:
    """Uçtan uca: token açıkken proxy başlığıyla yapılan istek 401 DEĞİL 200 alır.

    Bu, kısır döngünün kapandığının kanıtıdır — regresyonda 401 döner.
    """
    from app.config import get_settings

    monkeypatch.setenv("ACHILLES_API_TOKEN", "gizli-test-token")
    get_settings.cache_clear()
    try:
        from app.web.server import app

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test", headers=auth_headers()
        ) as client:
            resp = await client.get("/api/version")
        assert resp.status_code == 200, f"Token'lı MCP çağrısı başarısız: {resp.status_code}"

        # Kontrol: başlıksız aynı istek 401 almalı (test gerçekten auth'u sınıyor).
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as bare:
            assert (await bare.get("/api/version")).status_code == 401
    finally:
        get_settings.cache_clear()
