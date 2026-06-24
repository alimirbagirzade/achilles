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

    def _build_rlm_kwargs(self) -> dict[str, Any]:
        alex = self.config.get("alexzhang", {}) or {}
        return {
            "backend": alex.get("backend", "anthropic"),  # OpenAI değil
            "backend_kwargs": {"model_name": alex.get("model_name")},
            "environment": alex.get("environment", "docker"),  # üretimde 'local' yasak
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
