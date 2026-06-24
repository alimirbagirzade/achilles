"""RLM adapter arayüzü — tüm motorların (native/alexzhang) uyduğu sözleşme."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class RLMRequest:
    """Bir motor çağrısının girdisi.

    `evidence_pack`: RAG retrieval'dan ÖNCEDEN üretilmiş kanıt (chunk'lar + metadata).
    Native adapter kendi retrieval'ını yapar (evidence_pack opsiyoneldir); alexzhang
    adapter YALNIZ verilen evidence_pack üzerinde akıl yürütür (kendi retrieval'ı yok).
    """

    query: str
    evidence_pack: dict[str, Any] = field(default_factory=dict)
    task_type: str = "research_qa"
    run_config: dict[str, Any] = field(default_factory=dict)


@dataclass
class RLMResponse:
    """Bir motor çağrısının çıktısı (henüz doğrulanmamış ham taslak olabilir)."""

    answer: str
    raw_response: Any | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    used_adapter: str = "unknown"
    success: bool = True
    error: str | None = None


@runtime_checkable
class BaseRLMAdapter(Protocol):
    """RLM motor arayüzü. `is_available()` çalışma-zamanı uygunluğunu, `complete()`
    asıl çağrıyı yapar. Hiçbir adapter, uygun değilken exception atmamalı — `success=False`
    + temiz `error` döndürmeli (sistem bozulmadan native'e düşebilsin)."""

    name: str

    def is_available(self) -> bool: ...

    def complete(self, request: RLMRequest) -> RLMResponse: ...
