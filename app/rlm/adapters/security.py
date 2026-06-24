"""RLM çalışma-zamanı güvenlik kapısı (talimat §11).

alexzhang13/rlm'in varsayılan yerel REPL ortamı host process içinde Python `exec`
çalıştırabilir → üretimde RİSKLİ. Bu modül, alexzhang adapter ÇALIŞMADAN ÖNCE çağrılır
ve güvensiz kombinasyonları reddeder. Native adapter bu modülü gerektirmez (kod
çalıştırmaz).

Varsayılan duruş: production_mode=True, local-exec/shell/network/filesystem-write KAPALI.
"""

from __future__ import annotations

from typing import Any


class RLMUnsafeRuntimeError(RuntimeError):
    """Güvensiz RLM çalışma-zamanı yapılandırması (üretimde yasak kombinasyon)."""


def validate_rlm_runtime_security(config: dict[str, Any]) -> None:
    """alexzhang adapter çalıştırılmadan önce güvenlik değişmezlerini doğrula.

    Üretim modunda (`security.production_mode`, varsayılan True) şunlar YASAK:
    - `alexzhang.environment == "local"` + `allow_local_exec=False` (host'ta exec),
    - `allow_shell=True`, `allow_network=True`, `allow_filesystem_write=True`.

    İhlalde `RLMUnsafeRuntimeError` atar; çağıran native'e düşmelidir.
    """
    security = config.get("security", {}) or {}
    alex = config.get("alexzhang", {}) or {}

    production = bool(security.get("production_mode", True))
    environment = str(alex.get("environment", "docker"))

    if not production:
        return  # üretim-dışı: geliştirici kendi riskini alır (yine de varsayılanlar kapalı)

    # ALLOW-LIST (deny-by-default): üretimde YALNIZ izole 'docker' ortamına izin var.
    # 'local' VE 'ipython' modelin ürettiği Python'u HOST process'inde çalıştırır (aynı
    # RCE riski: rastgele kod, fs-yazma, ağ, secret okuma); bilinmeyen ortamlar da reddedilir.
    # Deny-list ('environment==local') ipython yolunu kaçırıyordu (güvenlik açığı).
    if environment != "docker":
        raise RLMUnsafeRuntimeError(
            f"Güvensiz RLM çalışma-zamanı: üretimde yalnız izole 'docker' ortamına izin var "
            f"(verilen: {environment!r}). 'local'/'ipython' host-içi kod çalıştırır → yasak. "
            "native kullanın veya 'docker'a geçin (ya da production_mode'u açıkça kapatın)."
        )
    if bool(alex.get("allow_local_exec", False)):
        raise RLMUnsafeRuntimeError(
            "Güvensiz RLM çalışma-zamanı: üretimde host-içi local exec açılamaz."
        )
    if bool(alex.get("allow_shell", False)):
        raise RLMUnsafeRuntimeError("Güvensiz RLM çalışma-zamanı: üretimde shell erişimi yasak.")
    if bool(alex.get("allow_network", False)):
        raise RLMUnsafeRuntimeError(
            "Güvensiz RLM çalışma-zamanı: üretimde ağ erişimi varsayılan olarak yasak."
        )
    if bool(alex.get("allow_filesystem_write", False)):
        raise RLMUnsafeRuntimeError(
            "Güvensiz RLM çalışma-zamanı: üretimde filesystem yazımı varsayılan olarak yasak."
        )
