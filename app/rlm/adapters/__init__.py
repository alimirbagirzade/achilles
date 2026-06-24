"""RLM engine adapters — değiştirilebilir recursive-reasoning motorları.

Achilles'in RLM katmanı (app/rlm/rlm_controller.py) ÇEKİRDEK ve VARSAYILANDIR. Bu paket
onun ÜSTÜNE opsiyonel bir motor-soyutlaması ekler:

  - NativeRLMAdapter   → mevcut RlmController'ı sarar (varsayılan; ek bağımlılık YOK).
  - AlexZhangRLMAdapter → opsiyonel `rlms` paketi (alexzhang13/rlm) kuruluysa; recursive
    inference motoru. Kurulu değilse sistem BOZULMAZ; native'e düşer.

Mutlak kurallar (talimat + CLAUDE.md):
  - rlms ZORUNLU bağımlılık değildir; yoksa native çalışır.
  - OpenAI VARSAYILAN provider DEĞİLDİR (Anthropic/Claude veya yerel Ollama/native).
  - Production'da local exec / shell / network / filesystem-write YASAK (security guard).
  - RLM yalnız allowlist'teki tool'ları çağırabilir.
  - RAG / Paper Mastery / verifier / SQLite registry / Chroma'nın YERİNE GEÇMEZ.
"""

from __future__ import annotations

from app.rlm.adapters.base import BaseRLMAdapter, RLMRequest, RLMResponse

__all__ = ["BaseRLMAdapter", "RLMRequest", "RLMResponse"]
