"""Turn knowledge cards into instruction-tuning examples (JSONL).

Example types (per spec):
1 summarize, 2 finding->hypothesis, 3 strategy critique, 4 overfit detection,
5 risk management, 6 backtest interpretation, 7 pine idea, 8 python idea.

This module produces deterministic, template-derived examples directly from a
knowledge card's fields. (An LLM-augmented generator can be layered on later
via the ``training_example_builder`` prompt.)
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from app.brain.knowledge_card_builder import KnowledgeCard
from app.config import get_settings
from app.memory.sqlite_store import SqliteStore, TrainingExample


@dataclass
class Example:
    instruction: str
    input: str
    output: str
    example_type: str
    source_paper_id: str | None

    def to_jsonl_record(self) -> dict:
        return {
            "instruction": self.instruction,
            "input": self.input,
            "output": self.output,
            "source_paper_id": self.source_paper_id,
            "type": self.example_type,
        }


def examples_from_card(card: KnowledgeCard) -> list[Example]:
    pid = card.paper_id
    out: list[Example] = []

    if card.main_claim:
        out.append(
            Example(
                instruction="Bu akademik bulguyu öz biçimde özetle.",
                input=card.main_claim,
                output=f"{card.main_claim} (Kaynak: {pid})",
                example_type="summarize",
                source_paper_id=pid,
            )
        )

    for hyp in card.possible_strategy_hypotheses:
        out.append(
            Example(
                instruction="Bu akademik bulguyu test edilebilir bir trading hipotezine çevir.",
                input=card.main_claim or card.trading_relevance,
                output=(
                    f"Hipotez: {hyp}\n"
                    "Test planı: out-of-sample backtest, walk-forward, "
                    "spread/slipaj/komisyon dahil; tek başına kanıt sayılmaz."
                ),
                example_type="finding_to_hypothesis",
                source_paper_id=pid,
            )
        )

    for warn in card.risk_warnings:
        out.append(
            Example(
                instruction="Bu stratejiyle ilgili risk uyarısını açıkla.",
                input=card.trading_relevance,
                output=f"Risk: {warn}. Doğrulanmadan canlı kullanılmamalı.",
                example_type="risk_management",
                source_paper_id=pid,
            )
        )

    for lim in card.limitations:
        out.append(
            Example(
                instruction="Bu bulgunun overfit/genellenebilirlik riskini değerlendir.",
                input=lim,
                output=(
                    f"Sınırlama: {lim}. Bu durum overfit ve örneklem-dışı zayıflık "
                    "riskini artırır; walk-forward ile test edilmeli."
                ),
                example_type="overfit_detection",
                source_paper_id=pid,
            )
        )

    return out


class TrainingDataBuilder:
    def __init__(self, store: SqliteStore | None = None) -> None:
        self.store = store or SqliteStore()
        self.settings = get_settings()

    def persist(self, examples: list[Example]) -> int:
        with self.store.session() as s:
            for ex in examples:
                s.add(
                    TrainingExample(
                        example_id=f"ex_{uuid.uuid4().hex[:12]}",
                        source_paper_id=ex.source_paper_id,
                        example_type=ex.example_type,
                        instruction=ex.instruction,
                        input_text=ex.input,
                        output_text=ex.output,
                    )
                )
        return len(examples)

    def write_jsonl(self, examples: list[Example], filename: str = "train.jsonl") -> Path:
        out_path = self.settings.jsonl_dir / filename
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            for ex in examples:
                f.write(json.dumps(ex.to_jsonl_record(), ensure_ascii=False) + "\n")
        return out_path

    def build_from_card(self, card: KnowledgeCard, *, persist: bool = True) -> list[Example]:
        examples = examples_from_card(card)
        if persist:
            self.persist(examples)
        return examples


__all__ = ["Example", "TrainingDataBuilder", "asdict", "examples_from_card"]
