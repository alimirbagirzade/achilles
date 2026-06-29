"""Orkestrasyon web uçları — TestClient ile, çevrimdışı.

Tek-tık start → insan kapısında durur (Kural 8); status/timeline/runs/resume/recover.
Gerçek eğitim ASLA gözetimsiz başlamaz: train aşaması hiçbir koşulda 'completed' olmaz.
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from app.web.server import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_start_halts_at_human_gate(client: TestClient) -> None:
    r = client.post(
        "/api/orchestration/start",
        json={"adapter_name": "web_smoke", "hunt_ack": False, "auto_run": True},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["run_id"].startswith("orc_")
    assert body["run"]["status"] in {"blocked", "failed"}
    by_name = {s["name"]: s for s in body["stages"]}
    # gerçek eğitim gözetimsiz BAŞLAMAZ
    assert by_name["train"]["status"] != "completed"
    assert by_name["evaluate"]["status"] != "completed"


def test_status_and_timeline_roundtrip(client: TestClient) -> None:
    run_id = client.post(
        "/api/orchestration/start", json={"adapter_name": "web_rt", "auto_run": False}
    ).json()["run_id"]

    s = client.get(f"/api/orchestration/status/{run_id}")
    assert s.status_code == 200
    assert s.json()["run"]["run_id"] == run_id

    t = client.get(f"/api/orchestration/timeline/{run_id}")
    assert t.status_code == 200
    assert isinstance(t.json()["events"], list)
    assert len(t.json()["events"]) >= 1  # create_run en az bir olay yazar


def test_status_unknown_404(client: TestClient) -> None:
    assert client.get("/api/orchestration/status/orc_yok").status_code == 404
    assert client.get("/api/orchestration/timeline/orc_yok").status_code == 404


def test_resume_unknown_404(client: TestClient) -> None:
    r = client.post("/api/orchestration/resume/orc_yok", json={"hunt_ack": True})
    assert r.status_code == 404


def test_runs_and_recover(client: TestClient) -> None:
    client.post("/api/orchestration/start", json={"adapter_name": "web_list", "auto_run": False})
    runs = client.get("/api/orchestration/runs?limit=5")
    assert runs.status_code == 200
    assert isinstance(runs.json()["runs"], list)

    rec = client.post("/api/orchestration/recover", json={"timeout_min": 30.0})
    assert rec.status_code == 200
    assert isinstance(rec.json()["recovered"], list)


def test_start_rejects_out_of_bounds_iters(client: TestClient) -> None:
    r = client.post("/api/orchestration/start", json={"iters": 99999999})
    assert r.status_code == 422


def test_start_rejects_path_traversal_adapter_name(client: TestClient) -> None:
    r = client.post("/api/orchestration/start", json={"adapter_name": "../../etc/passwd"})
    assert r.status_code == 422


def test_resume_with_hunt_ack_advances(client: TestClient) -> None:
    """hunt_ack ile resume deep-hunt'ı geçirir (checkpoint: preflight tekrar koşmaz)."""
    run_id = client.post(
        "/api/orchestration/start",
        json={"adapter_name": "web_resume", "hunt_ack": False, "auto_run": True},
    ).json()["run_id"]

    resumed = client.post(f"/api/orchestration/resume/{run_id}", json={"hunt_ack": True})
    assert resumed.status_code == 200
    by_name = {s["name"]: s for s in resumed.json()["stages"]}
    # deep-hunt artık bloklu değil (completed) — ya da sonraki aşamada durmuş
    assert by_name["deep-hunt"]["status"] == "completed"
    # train yine de gözetimsiz çalışmaz
    assert by_name["train"]["status"] != "completed"
