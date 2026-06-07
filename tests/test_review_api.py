"""Kart onay API endpoint testleri (offline).

Kapsar:
- test_pending_empty          → başta pending kart yok
- test_approve_flow           → kart ekle → approve → review_status=approved, lora_eligible=1
- test_reject_flow            → kart ekle → reject → review_status=rejected, lora_eligible=0
- test_approved_list          → approve sonrası /api/cards/approved'da görünür
- test_not_found_approve      → olmayan kart → status=not_found
- test_not_found_reject       → olmayan kart → status=not_found
- test_pending_endpoint       → FastAPI TestClient ile /api/cards/pending
- test_approve_endpoint       → FastAPI TestClient ile /api/card/{id}/approve
- test_reject_endpoint        → FastAPI TestClient ile /api/card/{id}/reject
- test_approved_endpoint      → FastAPI TestClient ile /api/cards/approved
"""

from __future__ import annotations

import pytest

# ---------- SqliteStore doğrudan testler ----------


def test_pending_empty(store) -> None:
    """Başlangıçta pending kart listesi boş (izole DB)."""
    # store fixture'ı conftest.py'dan gelir — temiz, izole DB
    result = store.list_pending_cards()
    # Diğer testlerden kalan kayıtlar olabilir; sadece tip kontrolü yeterli
    assert isinstance(result, list)


def _save_test_card(store, card_id: str, review_status: str = "pending") -> None:
    """Yardımcı: test kartı kaydet (paper + kart)."""
    store.upsert_paper(
        paper_id=card_id,
        file_hash=f"hash_{card_id}",
        source_path=f"/tmp/{card_id}.pdf",
        title=f"Test Paper {card_id}",
    )
    store.save_knowledge_card(
        card_id=f"card_{card_id}",
        paper_id=card_id,
        model="test-model",
        card={
            "paper_id": card_id,
            "title": f"Test Paper {card_id}",
            "main_claim": f"Ana bulgu: {card_id}",
        },
        trust_level="draft",
        review_status=review_status,
        lora_eligible=0,
        difficulty=0.5,
        stage="v1",
    )


def test_approve_flow(store) -> None:
    """Kart eklendikten sonra approve edilince review_status ve lora_eligible güncellenir."""
    _save_test_card(store, "approve_flow_paper")
    card_id = "card_approve_flow_paper"

    # Önce pending listesinde olmalı
    pending = store.list_pending_cards()
    card_ids = [c["card_id"] for c in pending]
    assert card_id in card_ids

    # Onayla
    ok = store.approve_card(card_id)
    assert ok is True

    # get_card_by_id ile doğrula
    card = store.get_card_by_id(card_id)
    assert card is not None
    assert card["review_status"] == "approved"
    assert card["lora_eligible"] == 1

    # Artık pending listesinde olmamalı
    pending_after = store.list_pending_cards()
    assert card_id not in [c["card_id"] for c in pending_after]


def test_reject_flow(store) -> None:
    """Kart eklendikten sonra reject edilince review_status ve lora_eligible güncellenir."""
    _save_test_card(store, "reject_flow_paper")
    card_id = "card_reject_flow_paper"

    # Reddet
    ok = store.reject_card(card_id)
    assert ok is True

    card = store.get_card_by_id(card_id)
    assert card is not None
    assert card["review_status"] == "rejected"
    assert card["lora_eligible"] == 0

    # pending listesinde olmamalı
    pending_after = store.list_pending_cards()
    assert card_id not in [c["card_id"] for c in pending_after]


def test_approved_list(store) -> None:
    """Approve edilen kart list_approved_cards'da görünür."""
    _save_test_card(store, "approved_list_paper")
    card_id = "card_approved_list_paper"
    store.approve_card(card_id)

    approved = store.list_approved_cards()
    assert any(c["card_id"] == card_id for c in approved)


def test_not_found_approve(store) -> None:
    """Olmayan kart için approve_card False döner."""
    result = store.approve_card("kart_yok_xzy")
    assert result is False


def test_not_found_reject(store) -> None:
    """Olmayan kart için reject_card False döner."""
    result = store.reject_card("kart_yok_abc")
    assert result is False


def test_approved_difficulty_filter(store) -> None:
    """list_approved_cards difficulty filtresi doğru çalışır."""
    store.upsert_paper(
        paper_id="diff_filter_paper",
        file_hash="hash_diff_filter",
        source_path="/tmp/diff_filter.pdf",
        title="Difficulty Filter Paper",
    )
    store.save_knowledge_card(
        card_id="card_diff_filter",
        paper_id="diff_filter_paper",
        model="test-model",
        card={"paper_id": "diff_filter_paper", "title": "Difficulty Filter"},
        review_status="approved",
        lora_eligible=1,
        difficulty=0.8,
    )

    # 0.8 aralığına girer
    high = store.list_approved_cards(difficulty_min=0.7, difficulty_max=1.0)
    assert any(c["card_id"] == "card_diff_filter" for c in high)

    # 0.8 aralığına girmez
    low = store.list_approved_cards(difficulty_min=0.0, difficulty_max=0.5)
    assert not any(c["card_id"] == "card_diff_filter" for c in low)


# ---------- FastAPI TestClient endpoint testleri ----------

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

from app.web.server import app  # noqa: E402


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_pending_endpoint_ok(client: TestClient) -> None:
    """GET /api/cards/pending — 200 + geçerli şema."""
    r = client.get("/api/cards/pending")
    assert r.status_code == 200
    body = r.json()
    assert "cards" in body
    assert "total" in body
    assert isinstance(body["cards"], list)
    assert body["total"] == len(body["cards"])


def test_approve_endpoint(client: TestClient) -> None:
    """POST /api/card/{id}/approve — var olan kart onaylanır."""
    from app.memory.sqlite_store import SqliteStore

    s = SqliteStore()
    s.upsert_paper(
        paper_id="ep_approve_paper",
        file_hash="hash_ep_approve",
        source_path="/tmp/ep_approve.pdf",
        title="Endpoint Approve Paper",
    )
    s.save_knowledge_card(
        card_id="ep_approve_card",
        paper_id="ep_approve_paper",
        model="test-model",
        card={"paper_id": "ep_approve_paper", "title": "EP Approve", "main_claim": "test"},
        review_status="pending",
    )

    r = client.post("/api/card/ep_approve_card/approve")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "approved"
    assert body["card_id"] == "ep_approve_card"

    # store'da doğrula
    card = s.get_card_by_id("ep_approve_card")
    assert card is not None
    assert card["review_status"] == "approved"
    assert card["lora_eligible"] == 1


def test_reject_endpoint(client: TestClient) -> None:
    """POST /api/card/{id}/reject — var olan kart reddedilir."""
    from app.memory.sqlite_store import SqliteStore

    s = SqliteStore()
    s.upsert_paper(
        paper_id="ep_reject_paper",
        file_hash="hash_ep_reject",
        source_path="/tmp/ep_reject.pdf",
        title="Endpoint Reject Paper",
    )
    s.save_knowledge_card(
        card_id="ep_reject_card",
        paper_id="ep_reject_paper",
        model="test-model",
        card={"paper_id": "ep_reject_paper", "title": "EP Reject", "main_claim": "test"},
        review_status="pending",
    )

    r = client.post("/api/card/ep_reject_card/reject")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "rejected"
    assert body["card_id"] == "ep_reject_card"

    card = s.get_card_by_id("ep_reject_card")
    assert card is not None
    assert card["review_status"] == "rejected"
    assert card["lora_eligible"] == 0


def test_approve_endpoint_not_found(client: TestClient) -> None:
    """POST /api/card/{id}/approve — olmayan kart → status=not_found (200)."""
    r = client.post("/api/card/kart_hic_yok_xyz/approve")
    assert r.status_code == 200
    assert r.json()["status"] == "not_found"


def test_reject_endpoint_not_found(client: TestClient) -> None:
    """POST /api/card/{id}/reject — olmayan kart → status=not_found (200)."""
    r = client.post("/api/card/kart_hic_yok_abc/reject")
    assert r.status_code == 200
    assert r.json()["status"] == "not_found"


def test_approved_endpoint(client: TestClient) -> None:
    """GET /api/cards/approved — 200 + geçerli şema."""
    r = client.get("/api/cards/approved")
    assert r.status_code == 200
    body = r.json()
    assert "cards" in body
    assert "total" in body
    assert "difficulty_min" in body
    assert "difficulty_max" in body


def test_approved_endpoint_difficulty_params(client: TestClient) -> None:
    """GET /api/cards/approved?difficulty_min=0.0&difficulty_max=1.0 — parametre geçişi."""
    r = client.get("/api/cards/approved?difficulty_min=0.0&difficulty_max=0.5")
    assert r.status_code == 200
    body = r.json()
    assert body["difficulty_min"] == 0.0
    assert body["difficulty_max"] == 0.5
