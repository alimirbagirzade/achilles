"""LLM istemcisi — Ollama (yerel) veya OpenAI (bulut).

Öncelik sırası (llm_backend = "auto"):
  1. Ollama çalışıyorsa → yerel model (ücretsiz, gizli)
  2. ACHILLES_OPENAI_API_KEY varsa → OpenAI API
  3. İkisi de yoksa → LLMUnavailable hatası

``llm_backend = "ollama"`` veya ``"openai"`` ile sabitlenebilir.
"""

from __future__ import annotations

import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class LLMUnavailable(RuntimeError):
    pass


class LocalLLM:
    def __init__(self, model: str | None = None, host: str | None = None) -> None:
        s = get_settings()
        self._backend = s.llm_backend
        self._ollama_host = (host or s.ollama_host).rstrip("/")
        self._ollama_model = model or s.llm_model
        self.model = self._ollama_model  # backward compat
        self._openai_key = s.openai_api_key
        self._openai_model = s.openai_model
        self._openai_base = s.openai_base_url.rstrip("/")

    # ---------------------------------------------------------------- probes

    def _ollama_alive(self) -> bool:
        try:
            r = httpx.get(f"{self._ollama_host}/api/tags", timeout=2.0)
            return r.status_code == 200
        except Exception:
            return False

    def _openai_ready(self) -> bool:
        return bool(self._openai_key)

    def available(self) -> bool:
        if self._backend == "ollama":
            return self._ollama_alive()
        if self._backend == "openai":
            return self._openai_ready()
        return self._ollama_alive() or self._openai_ready()

    def active_backend(self) -> str:
        """Hangi backend aktif: 'ollama', 'openai' veya 'none'.

        auto modunda: OpenAI API key varsa OpenAI tercih edilir; yoksa Ollama.
        """
        if self._backend == "ollama":
            return "ollama"
        if self._backend == "openai":
            return "openai"
        # auto: OpenAI önce (API key varsa), sonra Ollama
        if self._openai_ready():
            return "openai"
        if self._ollama_alive():
            return "ollama"
        return "none"

    # ---------------------------------------------------------------- generate

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        fmt: str | None = None,
        timeout: int = 600,
    ) -> str:
        backend = self.active_backend()

        if backend == "ollama":
            return self._generate_ollama(
                prompt, system=system, temperature=temperature,
                max_tokens=max_tokens, fmt=fmt, timeout=timeout,
            )
        if backend == "openai":
            return self._generate_openai(
                prompt, system=system, temperature=temperature,
                max_tokens=max_tokens, timeout=timeout,
            )

        hints: list[str] = []
        if self._backend in ("auto", "ollama"):
            hints.append(f"Ollama başlatın: ollama serve && ollama pull {self._ollama_model}")
        if self._backend in ("auto", "openai"):
            hints.append("veya .env'e ACHILLES_OPENAI_API_KEY=sk-... ekleyin")
        raise LLMUnavailable("LLM kullanılamıyor. " + "  ".join(hints))

    # ---------------------------------------------------------------- backends

    def _generate_ollama(
        self,
        prompt: str,
        *,
        system: str | None,
        temperature: float,
        max_tokens: int | None,
        fmt: str | None,
        timeout: int,
    ) -> str:
        options: dict = {"temperature": temperature}
        if max_tokens:
            options["num_predict"] = max_tokens
        payload: dict = {
            "model": self._ollama_model,
            "prompt": prompt,
            "system": system or "",
            "stream": False,
            "options": options,
        }
        if fmt:
            payload["format"] = fmt
        with httpx.Client(timeout=timeout) as client:
            r = client.post(f"{self._ollama_host}/api/generate", json=payload)
        r.raise_for_status()
        return r.json().get("response", "").strip()

    def _generate_openai(
        self,
        prompt: str,
        *,
        system: str | None,
        temperature: float,
        max_tokens: int | None,
        timeout: int,
    ) -> str:
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: dict = {
            "model": self._openai_model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        headers = {
            "Authorization": f"Bearer {self._openai_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=timeout) as client:
            r = client.post(
                f"{self._openai_base}/chat/completions",
                json=payload,
                headers=headers,
            )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
