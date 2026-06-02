"""Decide which model/adapter to use for a given task.

MVP behavior: returns the base model unless a registered adapter is requested.
This is the seam where, later, you can route 'trader-style' tasks to a
fine-tuned adapter and 'factual RAG' tasks to the base model.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import get_settings
from app.training.adapter_registry import AdapterRegistry


@dataclass
class ModelChoice:
    base_model: str
    adapter_version: str | None = None
    adapter_path: str | None = None

    @property
    def label(self) -> str:
        return (
            self.base_model
            if not self.adapter_version
            else (f"{self.base_model}+{self.adapter_version}")
        )


class ModelRouter:
    def __init__(self, registry: AdapterRegistry | None = None) -> None:
        self.settings = get_settings()
        self.registry = registry or AdapterRegistry()

    def choose(self, task: str = "rag", adapter_version: str | None = None) -> ModelChoice:
        base = self.settings.llm_model
        if adapter_version:
            entry = self.registry.get(adapter_version)
            if entry:
                return ModelChoice(base, adapter_version, entry.get("adapter_path"))
        return ModelChoice(base)
