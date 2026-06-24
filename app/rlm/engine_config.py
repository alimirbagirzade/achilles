"""RLM motor yapılandırması — Settings/env'den (Achilles-native) config dict'i kurar.

Talimat configs/rlm_engine.yaml öneriyordu; ancak Achilles çalışma-zamanı yapılandırması
pydantic Settings + env'dir (talimat: "mevcut env sistemine uyum sağla"). Bu modül o
Settings'i okuyup security guard + adapter'ların beklediği iç-içe dict'i üretir. Tek
gerçek-kaynak Settings'tir (paralel yaml YOK → tutarsızlık/dead-config riski yok).

Tool allowlist sabit ve KISITLAYICIDIR: RLM yalnız bu adlardaki güvenli wrapper'ları
çağırabilir (serbest Python/exec yok).
"""

from __future__ import annotations

from typing import Any

from app.config import get_settings

# İzinli tool adları (talimat §12). RLM bunların DIŞINDA hiçbir şey çağıramaz.
ALLOWED_TOOL_NAMES: tuple[str, ...] = (
    "rag_search",
    "get_paper_chunks",
    "get_paper_metadata",
    "citation_check",
    "grounding_check",
    "contradiction_check",
    "formula_check",
    "calculator",
)


def build_engine_config() -> dict[str, Any]:
    """Settings → motor config dict (provider + alexzhang + security + allowlist)."""
    s = get_settings()
    # alexzhang model adı boşsa hardcode etme → mevcut Anthropic model config'ine düş.
    model_name = s.rlm_alexzhang_model or s.anthropic_model
    return {
        "provider": s.rlm_engine_provider,
        "alexzhang": {
            "enabled": s.rlm_alexzhang_enabled,
            "package_name": "rlms",
            "import_name": "rlm",
            "backend": s.rlm_alexzhang_backend,  # anthropic | local_openai_compatible
            "model_name": model_name,
            "environment": s.rlm_alexzhang_environment,  # docker | ipython | local
            "allow_local_exec": s.rlm_alexzhang_allow_local_exec,
            "allow_network": s.rlm_alexzhang_allow_network,
            "allow_shell": s.rlm_alexzhang_allow_shell,
            "allow_filesystem_write": s.rlm_alexzhang_allow_filesystem_write,
            "log_trajectories": s.rlm_alexzhang_log_trajectories,
            "trajectory_log_dir": "reports/rlm/trajectories",
        },
        "security": {
            "production_mode": s.rlm_production_mode,
            "deny_local_exec_in_production": True,
            "deny_shell_tools": True,
            "deny_secret_reading": True,
            "deny_network_by_default": True,
            "allowed_tool_names": list(ALLOWED_TOOL_NAMES),
        },
    }


def public_engine_config() -> dict[str, Any]:
    """API/CLI için GÜVENLİ (sır içermeyen) config görünümü."""
    cfg = build_engine_config()
    alex = cfg["alexzhang"]
    return {
        "provider": cfg["provider"],
        "alexzhang_enabled": alex["enabled"],
        "alexzhang_backend": alex["backend"],
        "alexzhang_environment": alex["environment"],
        "production_mode": cfg["security"]["production_mode"],
        "allow_local_exec": alex["allow_local_exec"],
        "allowed_tools": cfg["security"]["allowed_tool_names"],
    }
