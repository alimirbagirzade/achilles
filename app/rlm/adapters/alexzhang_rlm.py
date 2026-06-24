"""AlexZhang RLM adapter — OPSİYONEL recursive inference motoru (alexzhang13/rlm).

PyPI paketi `rlms`, import adı `rlm`. Kurulu DEĞİLSE sistem bozulmaz: `is_available()`
False döner, `complete()` temiz hata (`success=False`) verir → çağıran native'e düşer.

Güvenlik (talimat §11): `complete()` çalışmadan ÖNCE `validate_rlm_runtime_security` ile
güvensiz kombinasyonlar (üretimde local-exec/shell/network/fs-write) reddedilir. OpenAI
VARSAYILAN değildir: backend "anthropic" (veya yalnız açıkça verilen yerel OpenAI-uyumlu
endpoint). Bu adapter modele YALNIZ evidence_pack'i metin/JSON olarak verir; serbest
tool/secret/filesystem erişimi AÇMAZ.
"""

from __future__ import annotations

import importlib.util
from typing import Any

from app.rlm.adapters.base import RLMRequest, RLMResponse
from app.rlm.adapters.security import validate_rlm_runtime_security


class AlexZhangRLMAdapter:
    name = "alexzhang_rlm"

    def __init__(self, config: dict[str, Any], tool_registry: Any | None = None) -> None:
        self.config = config or {}
        self.tool_registry = tool_registry

    def is_available(self) -> bool:
        """`rlms` paketi (import adı `rlm`) kurulu mu?"""
        return importlib.util.find_spec("rlm") is not None

    def complete(self, request: RLMRequest) -> RLMResponse:
        if not self.is_available():
            return RLMResponse(
                answer="",
                success=False,
                error=(
                    "Opsiyonel 'rlms' paketi kurulu değil. `uv sync --extra rlm` ile kurun "
                    "veya provider'ı 'native' yapın."
                ),
                used_adapter=self.name,
            )

        # Güvenlik kapısı — güvensizse RLMUnsafeRuntimeError atar (sesli; çağıran native'e düşmeli).
        # Bilerek try DIŞINDA: güvenlik ihlali asla "yumuşak hata"ya çevrilmez.
        validate_rlm_runtime_security(self.config)

        # Level 3 ortam preflight'ı: environment=docker/ipython hazır değilse motoru çağırmadan
        # ÖNCE temiz hata ver (rlms içinde derin/anlaşılmaz stack yerine). Güvenlik DEĞİL,
        # ortam eksikliği → success=False (çağıran native'e düşer). Preflight'ın kendisi
        # beklenmedik hata atarsa da çökme değil, temiz fallback.
        try:
            preflight_error = self._preflight_environment()
        except Exception as exc:
            preflight_error = f"ortam preflight hatası: {type(exc).__name__}: {exc}"
        if preflight_error:
            return RLMResponse(
                answer="", success=False, error=preflight_error, used_adapter=self.name
            )

        # SDK/ağ/API hataları base sözleşmesine göre RAISE EDİLMEZ → success=False döndürülür
        # (çağıran native'e düşer; sistem bozulmaz). Güvenlik istisnası burada YAKALANMAZ.
        try:
            from rlm import RLM  # opsiyonel paket (rlms); kurulu değilse yukarıda dönüldü

            prompt = self._build_prompt(request)
            rlm = RLM(**self._build_rlm_kwargs())
            result = rlm.completion(prompt)
        except Exception as exc:
            return RLMResponse(
                answer="",
                success=False,
                error=f"alexzhang motoru çalışma hatası: {type(exc).__name__}: {exc}",
                used_adapter=self.name,
            )
        return RLMResponse(
            answer=str(getattr(result, "response", result)),
            raw_response=result,
            metadata=dict(getattr(result, "metadata", {}) or {}),
            used_adapter=self.name,
            success=True,
        )

    def _preflight_environment(self) -> str | None:
        """Level 3 ortamı (docker/ipython) hazır mı? Değilse temiz hata mesajı döner.

        docker: `docker` CLI PATH'te olmalı. ipython: IPython paketi import edilebilmeli.
        native/local: ek ortam gerekmez (local üretimde güvenlik kapısınca zaten reddedilir).
        """
        import shutil

        alex = self.config.get("alexzhang", {}) or {}
        env = str(alex.get("environment", "docker")).lower()
        if env == "docker":
            if shutil.which("docker") is None:
                return (
                    "RLM environment='docker' ama 'docker' CLI bulunamadı (Docker kurulu değil). "
                    "Docker'ı kurun/başlatın, environment'ı 'native' yapın ya da provider'ı native "
                    "bırakın (sistem native ile çalışır)."
                )
            if not self._docker_daemon_ok():
                return (
                    "RLM environment='docker': 'docker' CLI var ama daemon çalışmıyor "
                    "('docker info' başarısız). Docker Desktop/daemon'ı başlatın ya da provider'ı "
                    "native bırakın (sistem native ile çalışır)."
                )
        if env == "ipython" and importlib.util.find_spec("IPython") is None:
            return (
                "RLM environment='ipython' ama IPython kurulu değil. `pip install ipython` ya da "
                "environment'ı 'docker' yapın (üretimde yalnız 'docker' güvenlidir)."
            )
        return None

    @staticmethod
    def _docker_daemon_ok() -> bool:
        """`docker info` ile daemon canlı mı (read-only probe, shell DEĞİL, kısa timeout).

        Probe'un KENDİSİ patlarsa (spawn hatası vb.) fail-closed YAPMA → True dön; gerçek
        sorun olsa bile rlms içinde yakalanıp native'e düşülür (çift güvenlik)."""
        import subprocess

        try:
            # Sabit argv (shell YOK), salt-okuma probe, kısa timeout — kullanıcı girdisi geçmez.
            r = subprocess.run(["docker", "info"], capture_output=True, timeout=4)
            return r.returncode == 0
        except Exception:
            return True  # probe çalıştırılamadı → which-sonucuna güven (bloklamadan)

    def environment_ready(self) -> tuple[bool, str]:
        """Motorun seçili ortamı çalıştırmaya hazır mı? (uygunluk raporu; çağrı yapmaz)."""
        if not self.is_available():
            return False, "rlms paketi kurulu değil"
        err = self._preflight_environment()
        return (err is None, err or "ortam hazır")

    def _build_rlm_kwargs(self) -> dict[str, Any]:
        alex = self.config.get("alexzhang", {}) or {}
        # Determinizm (kural 6): üretim/alt-çağrılarda temperature=0 → greedy decode.
        # Anthropic'te determinizm kaldıracı sıcaklıktır (seed param yok); sampling_args
        # rlms tarafından backend'e iletilir. Desteklenmezse rlms içinde yakalanır → fallback.
        sampling = {"temperature": 0.0}
        return {
            "backend": alex.get("backend", "anthropic"),  # OpenAI değil
            "backend_kwargs": {"model_name": alex.get("model_name")},
            "environment": alex.get("environment", "docker"),  # üretimde 'local' yasak
            "sampling_args": sampling,
            "sub_sampling_args": sampling,
            "verbose": False,
        }

    def _build_prompt(self, request: RLMRequest) -> str:
        # Modele YALNIZ evidence verilir; uydurma yasak, kaynak zorunlu (kural 7).
        return (
            "You are the Achilles Recursive Reasoning Engine.\n"
            "Use ONLY the evidence below. Do not invent unsupported claims.\n"
            "If the evidence is insufficient, say so explicitly.\n"
            "Return the final answer with citations using paper_id and chunk_id.\n\n"
            f"TASK_TYPE:\n{request.task_type}\n\n"
            f"USER_QUERY:\n{request.query}\n\n"
            f"EVIDENCE_PACK:\n{request.evidence_pack}\n\n"
            "REQUIRED_OUTPUT:\n"
            "- concise answer\n- bullet evidence\n- citations: paper_id/chunk_id\n"
            "- limitations\n- confidence: 0-100"
        ).strip()
