"""RLM motor adapter + pipeline testleri (talimat §17, offline).

native VARSAYILAN; alexzhang OPSİYONEL (rlms yoksa sistem bozulmaz); OpenAI default değil.
"""

from __future__ import annotations

from pathlib import Path

from app.rlm.adapters.alexzhang_rlm import AlexZhangRLMAdapter
from app.rlm.adapters.base import RLMRequest
from app.rlm.adapters.native import NativeRLMAdapter
from app.rlm.answer_pipeline import run_rlm_answer
from app.rlm.engine_config import build_engine_config, public_engine_config

_VALID_STATUS = {"grounded", "insufficient_evidence", "needs_review"}


def test_native_adapter_is_default_and_available():
    assert build_engine_config()["provider"] == "native"  # varsayılan
    assert NativeRLMAdapter().is_available() is True


def test_pipeline_native_runs_without_rlms_package():
    # Boş korpus (fake embedding) → kaynak yok → grounded değil; ama native ÇALIŞIR (çökmez).
    out = run_rlm_answer("Bilinmeyen bir konu?", adapter="native", write_report=False)
    assert out["adapter"] == "native"
    assert out["status"] in _VALID_STATUS


def test_missing_rlms_package_does_not_break_system():
    adapter = AlexZhangRLMAdapter(build_engine_config())
    if adapter.is_available():
        return  # rlms kuruluysa bu test uygulanmaz (CI'da kurulu değil)
    resp = adapter.complete(RLMRequest(query="x", evidence_pack={}))
    assert resp.success is False
    assert resp.error and "rlms" in resp.error  # temiz hata, exception YOK
    assert resp.used_adapter == "alexzhang_rlm"


def test_alexzhang_backend_is_anthropic_not_openai_by_default():
    cfg = build_engine_config()
    assert cfg["alexzhang"]["backend"] == "anthropic"  # OpenAI DEĞİL
    # OPENAI_API_KEY gerekmemeli — config'i kurmak/okumak key istemez.
    assert public_engine_config()["alexzhang_backend"] == "anthropic"


def test_require_citations_without_sources_is_insufficient():
    # Boş korpus + require_citations → kaynak yok → insufficient_evidence (uydurma yok).
    out = run_rlm_answer("Hiç ingest edilmemiş konu?", adapter="native", write_report=False)
    assert out["status"] == "insufficient_evidence"
    assert out["sources"] == []


def test_alexzhang_answer_rebuilt_from_supported_only():
    # FIX (kural 4/7): alexzhang yolu cevap gövdesini YALNIZ desteklenen iddialardan kurar;
    # motorun ham taslağı gövdeye girmez + uydurma satır-içi atıf çıkarılır.
    from app.memory.retrieval_service import RetrievedChunk
    from app.rlm.answer_pipeline import _rebuild_from_supported

    chunks = [
        RetrievedChunk(
            chunk_id="c1",
            paper_id="p1",
            text="momentum",
            page_number=3,
            section_name="Methods",
            title="Paper One",
            distance=0.1,
        )
    ]
    supported = ["Momentum sinyali test edilebilir [p1:c1].", "Uydurma atıflı cümle [p9:c9]."]
    body = _rebuild_from_supported(supported, chunks, status="grounded")
    assert "Momentum sinyali test edilebilir" in body
    assert "[p1:c1]" in body  # geçerli atıf korunur
    assert "[p9:c9]" not in body  # uydurma atıf (getirilmeyen chunk) çıkarılır
    assert "Güven seviyesi: High" in body


def test_alexzhang_answer_abstains_when_no_supported_claims():
    from app.rlm.answer_pipeline import _rebuild_from_supported

    body = _rebuild_from_supported([], [], status="insufficient_evidence")
    assert "desteklenen güvenilir bir cevap üretilemedi" in body
    assert "Güven seviyesi: Low" in body


def test_chunk_support_levels_strong_partial_weak():
    # §13: kaynak support_level — supported→strong, partially→partial, diğeri→weak.
    from app.rlm.answer_pipeline import _chunk_support_levels
    from app.rlm.claim_extractor import Claim

    claims = [
        Claim(claim="a", support_status="supported", supporting_chunks=["c1"]),
        Claim(claim="b", support_status="partially_supported", supporting_chunks=["c2", "c1"]),
        Claim(claim="c", support_status="unsupported", supporting_chunks=["c3"]),
    ]
    levels = _chunk_support_levels(claims)
    assert levels["c1"] == "strong"  # supported, partial'dan güçlü → strong kazanır
    assert levels["c2"] == "partial"
    assert "c3" not in levels  # unsupported chunk'a güç katmaz → varsayılan weak


def _traj_cfg(tmp_path):
    return {"alexzhang": {"log_trajectories": True, "trajectory_log_dir": str(tmp_path)}}


def test_trajectory_write_read_roundtrip(tmp_path):
    from app.memory.retrieval_service import RetrievedChunk
    from app.rlm.answer_pipeline import _write_trajectory_file, read_trajectory_file

    cfg = _traj_cfg(tmp_path)
    chunks = [
        RetrievedChunk("c1", "p1", "txt", 1, "Methods", "Paper One", 0.1),
    ]
    _write_trajectory_file(
        cfg,
        "rlm_abc123",
        "soru?",
        "paper_qa",
        "grounded",
        chunks,
        {"recursive_calls": 2},
        ["iddia A"],
        ["iddia B"],
    )
    traj = read_trajectory_file("rlm_abc123", cfg)
    assert traj is not None
    assert traj["run_id"] == "rlm_abc123"
    assert traj["status"] == "grounded"
    assert traj["engine_metadata"] == {"recursive_calls": 2}
    assert traj["evidence"][0]["chunk_id"] == "c1"
    assert read_trajectory_file("rlm_yok", cfg) is None  # olmayan → None (çökme yok)


def test_trajectory_run_id_sanitized_no_path_traversal(tmp_path):
    from app.rlm.answer_pipeline import _write_trajectory_file

    cfg = _traj_cfg(tmp_path)
    # Kötü niyetli run_id path traversal denemesi → sanitize edilir, tmp_path DIŞINA yazmaz.
    _write_trajectory_file(cfg, "../../evil", "q", "paper_qa", "grounded", [], {}, [], [])
    files = list(tmp_path.glob("*.json"))
    assert len(files) == 1
    assert ".." not in files[0].name and "/" not in files[0].name


def test_environment_ready_reports_rlms_missing():
    from app.rlm.adapters.alexzhang_rlm import AlexZhangRLMAdapter

    adp = AlexZhangRLMAdapter(build_engine_config())
    if adp.is_available():
        return  # rlms kuruluysa bu test uygulanmaz (CI'da kurulu değil)
    ready, note = adp.environment_ready()
    assert ready is False
    assert "rlms" in note


def test_preflight_docker_missing_returns_clean_error(monkeypatch):
    import shutil

    from app.rlm.adapters.alexzhang_rlm import AlexZhangRLMAdapter

    monkeypatch.setattr(shutil, "which", lambda _name: None)  # 'docker' CLI yokmuş gibi
    adp = AlexZhangRLMAdapter({"alexzhang": {"environment": "docker"}})
    err = adp._preflight_environment()
    assert err is not None and "docker" in err.lower()  # derin stack değil, temiz mesaj


def test_preflight_docker_present_no_error(monkeypatch):
    import shutil
    import subprocess

    from app.rlm.adapters.alexzhang_rlm import AlexZhangRLMAdapter

    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/docker")  # docker CLI var
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: type("R", (), {"returncode": 0})()
    )  # daemon canlı
    adp = AlexZhangRLMAdapter({"alexzhang": {"environment": "docker"}})
    assert adp._preflight_environment() is None


def test_preflight_docker_daemon_down_returns_error(monkeypatch):
    import shutil
    import subprocess

    from app.rlm.adapters.alexzhang_rlm import AlexZhangRLMAdapter

    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/docker")  # CLI var
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: type("R", (), {"returncode": 1})()
    )  # daemon DOWN
    adp = AlexZhangRLMAdapter({"alexzhang": {"environment": "docker"}})
    err = adp._preflight_environment()
    assert err is not None and "daemon" in err.lower()


def test_docker_daemon_probe_failure_does_not_block(monkeypatch):
    # Probe'un KENDİSİ patlarsa (spawn hatası) fail-closed YAPMA → True (which-sonucuna güven).
    import subprocess

    from app.rlm.adapters.alexzhang_rlm import AlexZhangRLMAdapter

    def _boom(*a, **k):
        raise FileNotFoundError("docker yok")

    monkeypatch.setattr(subprocess, "run", _boom)
    assert AlexZhangRLMAdapter._docker_daemon_ok() is True


def test_build_rlm_kwargs_deterministic_temperature_zero():
    from app.rlm.adapters.alexzhang_rlm import AlexZhangRLMAdapter

    kw = AlexZhangRLMAdapter(
        {"alexzhang": {"backend": "anthropic", "environment": "docker"}}
    )._build_rlm_kwargs()
    assert kw["backend"] == "anthropic"  # OpenAI değil
    assert kw["sampling_args"]["temperature"] == 0.0  # determinizm (kural 6)
    assert kw["sub_sampling_args"]["temperature"] == 0.0


def test_trajectory_oversize_file_not_read(tmp_path, monkeypatch):
    # OOM savunması: tavanı aşan trajektori dosyası belleğe ALINMAZ → None (çökme yok).
    from app.rlm import answer_pipeline
    from app.rlm.answer_pipeline import _write_trajectory_file, read_trajectory_file

    cfg = _traj_cfg(tmp_path)
    _write_trajectory_file(cfg, "rlm_big", "q", "paper_qa", "grounded", [], {}, [], [])
    monkeypatch.setattr(answer_pipeline, "_TRAJ_MAX_BYTES", 5)  # 5 byte tavan → dosya aşar
    assert read_trajectory_file("rlm_big", cfg) is None


def test_orphan_run_marked_failed_on_partial_error(monkeypatch):
    # create_run sonrası set_verification patlarsa run 'running' asılı kalmasın → 'failed'.
    import app.rlm.rlm_store as rlm_store_mod
    from app.rlm.answer_pipeline import _log_alexzhang_run

    finished: list = []

    class _FakeStore:
        def create_run(self, *a, **k):
            return "rlm_x"

        def add_step(self, *a, **k):
            pass

        def add_evidence(self, *a, **k):
            pass

        def set_verification(self, *a, **k):
            raise RuntimeError("yarıda kesinti")

        def finish_run(self, run_id, *, status, **k):
            finished.append((run_id, status))

    monkeypatch.setattr(rlm_store_mod, "RlmStore", _FakeStore)
    rid = _log_alexzhang_run(
        "q",
        "ans",
        "grounded",
        1.0,
        1.0,
        [],
        [],
        chunks=[],
        engine_meta={},
        engine_draft="d",
        cfg={"alexzhang": {"log_trajectories": False}},
    )
    assert rid is None  # yarıda kaldı → None
    assert ("rlm_x", "failed") in finished  # orphan 'failed' işaretlendi (reaper beklenmedi)


def test_rlms_installed_path_when_available():
    # rlms KURULU ise gerçek opsiyonel yolu doğrula: is_available True + backend anthropic
    # (OpenAI DEĞİL, kurulu olsa bile) + environment docker. Kurulu DEĞİLSE skip (CI opt-in).
    import importlib.util

    if importlib.util.find_spec("rlm") is None:
        import pytest

        pytest.skip("rlms kurulu değil (opsiyonel extra; `uv sync --extra rlm` ile kurulur)")
    from app.rlm.adapters.alexzhang_rlm import AlexZhangRLMAdapter

    adp = AlexZhangRLMAdapter(build_engine_config())
    assert adp.is_available() is True
    kw = adp._build_rlm_kwargs()
    assert kw["backend"] == "anthropic"  # rlms kurulu olsa BİLE OpenAI default değil
    assert kw["environment"] == "docker"


def test_no_secret_patterns_in_rlm_engine_source():
    """Public repo hijyeni: yeni RLM motor dosyalarında gerçek sır/key kalıbı olmamalı."""
    import re

    root = Path(__file__).resolve().parents[1] / "app" / "rlm"
    files = [
        *root.glob("adapters/*.py"),
        root / "engine_config.py",
        root / "safe_tools.py",
        root / "tool_registry.py",
        root / "answer_pipeline.py",
    ]
    secret_re = re.compile(r"sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}")
    assign_re = re.compile(r"(API_KEY|TOKEN|SECRET)\s*=\s*['\"][^'\"]{12,}['\"]")
    for f in files:
        txt = f.read_text(encoding="utf-8")
        assert not secret_re.search(txt), f"sır kalıbı: {f.name}"
        assert not assign_re.search(txt), f"hardcode key: {f.name}"
