"""RLM motor güvenlik kapısı testleri (talimat §11/§17, offline)."""

from __future__ import annotations

import pytest

from app.rlm.adapters.security import RLMUnsafeRuntimeError, validate_rlm_runtime_security


def _cfg(**alex) -> dict:
    base = {
        "environment": "docker",
        "allow_local_exec": False,
        "allow_shell": False,
        "allow_network": False,
        "allow_filesystem_write": False,
    }
    base.update(alex)
    return {"security": {"production_mode": True}, "alexzhang": base}


def test_blocks_local_exec_in_production():
    with pytest.raises(RLMUnsafeRuntimeError):
        validate_rlm_runtime_security(_cfg(environment="local", allow_local_exec=False))
    with pytest.raises(RLMUnsafeRuntimeError):
        validate_rlm_runtime_security(_cfg(environment="local", allow_local_exec=True))


def test_blocks_ipython_environment_in_production():
    # REGRESYON: 'ipython' de host-içi Python exec'tir (deny-list 'local'i kaçırıyordu).
    # Allow-list: üretimde yalnız 'docker' geçer, ipython REDDEDİLİR.
    with pytest.raises(RLMUnsafeRuntimeError):
        validate_rlm_runtime_security(_cfg(environment="ipython"))


def test_blocks_unknown_environment_in_production():
    # Bilinmeyen/yeni ortam adı (deny-by-default) → reddedilir.
    with pytest.raises(RLMUnsafeRuntimeError):
        validate_rlm_runtime_security(_cfg(environment="repl_v2"))


def test_blocks_shell_network_filesystem_in_production():
    for bad in ("allow_shell", "allow_network", "allow_filesystem_write"):
        with pytest.raises(RLMUnsafeRuntimeError):
            validate_rlm_runtime_security(_cfg(**{bad: True}))


def test_safe_default_docker_passes():
    # Üretim + docker + tüm izinler kapalı → güvenli, exception YOK.
    validate_rlm_runtime_security(_cfg())


def test_non_production_does_not_raise():
    cfg = _cfg(environment="local", allow_local_exec=False)
    cfg["security"]["production_mode"] = False
    validate_rlm_runtime_security(cfg)  # üretim-dışı: reddetmez
