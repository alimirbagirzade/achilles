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
