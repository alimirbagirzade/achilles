"""LLM istemcisi — Ollama, OpenAI, Anthropic veya Google.

Backend öncelik sırası (llm_backend = "auto"):
  1. ACHILLES_OPENAI_API_KEY varsa → OpenAI
  2. ACHILLES_ANTHROPIC_API_KEY varsa → Anthropic
  3. ACHILLES_GOOGLE_API_KEY varsa → Google
  4. Ollama çalışıyorsa → yerel model
  5. Hiçbiri yoksa → LLMUnavailable
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

        self._anthropic_key = s.anthropic_api_key
        self._anthropic_model = s.anthropic_model

        self._google_key = s.google_api_key
        self._google_model = s.google_model

    # ---------------------------------------------------------------- probes

    def _ollama_alive(self) -> bool:
        try:
            r = httpx.get(f"{self._ollama_host}/api/tags", timeout=2.0)
            return r.status_code == 200
        except Exception:
            return False

    def _openai_ready(self) -> bool:
        return bool(self._openai_key)

    def _anthropic_ready(self) -> bool:
        return bool(self._anthropic_key)

    def _google_ready(self) -> bool:
        return bool(self._google_key)

    def available(self) -> bool:
        if self._backend == "ollama":
            return self._ollama_alive()
        if self._backend == "openai":
            return self._openai_ready()
        if self._backend == "anthropic":
            return self._anthropic_ready()
        if self._backend == "google":
            return self._google_ready()
        return (
            self._openai_ready()
            or self._anthropic_ready()
            or self._google_ready()
            or self._ollama_alive()
        )

    def active_backend(self) -> str:
        if self._backend in ("ollama", "openai", "anthropic", "google"):
            return self._backend
        # auto: cloud önce, sonra yerel
        if self._openai_ready():
            return "openai"
        if self._anthropic_ready():
            return "anthropic"
        if self._google_ready():
            return "google"
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
        if backend == "anthropic":
            return self._generate_anthropic(
                prompt, system=system, temperature=temperature,
                max_tokens=max_tokens, timeout=timeout,
            )
        if backend == "google":
            return self._generate_google(
                prompt, system=system, temperature=temperature,
                max_tokens=max_tokens, timeout=timeout,
            )

        raise LLMUnavailable(
            "Hicbir LLM backend kullanilamıyor. "
            ".env dosyasina en az birini ekleyin: "
            "ACHILLES_OPENAI_API_KEY, ACHILLES_ANTHROPIC_API_KEY, "
            "ACHILLES_GOOGLE_API_KEY veya Ollama'yi baslatın."
        )

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

    def _generate_anthropic(
        self,
        prompt: str,
        *,
        system: str | None,
        temperature: float,
        max_tokens: int | None,
        timeout: int,
    ) -> str:
        try:
            import anthropic as _anthropic
        except ImportError as e:
            raise LLMUnavailable("anthropic paketi yuklu degil: uv add anthropic") from e

        client = _anthropic.Anthropic(api_key=self._anthropic_key)
        kwargs: dict = {
            "model": self._anthropic_model,
            "max_tokens": max_tokens or 4096,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        _ = timeout  # Anthropic SDK manages its own timeouts
        msg = client.messages.create(**kwargs)
        return msg.content[0].text.strip()

    def _generate_google(
        self,
        prompt: str,
        *,
        system: str | None,
        temperature: float,
        max_tokens: int | None,
        timeout: int,
    ) -> str:
        try:
            from google import genai as _genai
            from google.genai import types as _types
        except ImportError as e:
            raise LLMUnavailable("google-genai paketi yuklu degil: uv add google-genai") from e

        _ = timeout  # Google SDK manages its own timeouts
        client = _genai.Client(api_key=self._google_key)
        config = _types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            system_instruction=system,
        )
        response = client.models.generate_content(
            model=self._google_model,
            contents=prompt,
            config=config,
        )
        return response.text.strip()
