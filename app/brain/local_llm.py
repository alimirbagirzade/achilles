"""Local LLM client (Ollama).

Wraps the Ollama HTTP API. Raises a clear, actionable error if Ollama is not
running so the user knows exactly what to start. Brain modules that depend on
generation should catch ``LLMUnavailable`` and degrade gracefully where it
makes sense (e.g. RAG can still show retrieved sources).
"""

from __future__ import annotations

import logging

from app.config import get_settings

logger = logging.getLogger(__name__)


class LLMUnavailable(RuntimeError):
    pass


class LocalLLM:
    def __init__(self, model: str | None = None, host: str | None = None) -> None:
        settings = get_settings()
        self.model = model or settings.llm_model
        self.host = (host or settings.ollama_host).rstrip("/")

    def available(self) -> bool:
        try:
            import requests

            r = requests.get(f"{self.host}/api/tags", timeout=2)
            return r.status_code == 200
        except Exception:
            return False

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> str:
        import requests

        if not self.available():
            raise LLMUnavailable(
                f"Ollama'ya ulaşılamadı ({self.host}). "
                "Başlatın:  ollama serve   ve modeli çekin:  "
                f"ollama pull {self.model}"
            )
        options: dict = {"temperature": temperature}
        if max_tokens:
            options["num_predict"] = max_tokens
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system or "",
            "stream": False,
            "options": options,
        }
        r = requests.post(f"{self.host}/api/generate", json=payload, timeout=300)
        r.raise_for_status()
        return r.json().get("response", "").strip()
