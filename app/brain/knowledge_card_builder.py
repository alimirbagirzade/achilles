"""Build structured knowledge cards from papers.

Output schema (per spec):
    paper_id, title, year, domain, main_claim, methods[], datasets[],
    trading_relevance, limitations[], possible_strategy_hypotheses[],
    risk_warnings[], implementation_notes[]

The LLM is asked to return strict JSON. We parse defensively (strip code
fences, fall back to an empty-but-valid card on parse failure).
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.brain.local_llm import LocalLLM
from app.brain.prompt_loader import load_prompt
from app.config import get_settings
from app.memory.sqlite_store import SqliteStore

_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


class KnowledgeCard(BaseModel):
    paper_id: str
    title: str | None = None
    year: str | None = None
    domain: str | None = None
    main_claim: str = ""
    methods: list[str] = Field(default_factory=list)
    datasets: list[str] = Field(default_factory=list)
    trading_relevance: str = ""
    limitations: list[str] = Field(default_factory=list)
    possible_strategy_hypotheses: list[str] = Field(default_factory=list)
    risk_warnings: list[str] = Field(default_factory=list)
    implementation_notes: list[str] = Field(default_factory=list)


def _extract_json(text: str) -> dict[str, Any]:
    m = _JSON_FENCE.search(text)
    raw = m.group(1) if m else text
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end != -1:
        raw = raw[start : end + 1]
    return json.loads(raw)


class KnowledgeCardBuilder:
    def __init__(self, store: SqliteStore | None = None, llm: LocalLLM | None = None) -> None:
        self.store = store or SqliteStore()
        self.llm = llm or LocalLLM()
        self.settings = get_settings()

    def _load_text(self, paper_id: str) -> str:
        path = self.settings.extracted_text_dir / f"{paper_id}.txt"
        if path.exists():
            return path.read_text(encoding="utf-8")
        return "\n\n".join(c.text for c in self.store.list_chunks(paper_id))

    def build(self, paper_id: str, max_chars: int = 14000) -> KnowledgeCard:
        text = self._load_text(paper_id)[:max_chars]
        try:
            system = load_prompt("knowledge_card")
        except FileNotFoundError:
            system = "Makaleden yapılandırılmış JSON bilgi kartı üret. Sadece JSON döndür."

        out = self.llm.generate(
            f"MAKALE:\n{text}\n\nYukarıdaki şemaya uygun JSON üret. paper_id={paper_id}",
            system=system,
            temperature=0.1,
        )
        try:
            data = _extract_json(out)
        except (json.JSONDecodeError, ValueError):
            data = {"paper_id": paper_id, "main_claim": "", "trading_relevance": ""}
        data["paper_id"] = paper_id
        card = KnowledgeCard.model_validate(data)

        card_id = f"card_{uuid.uuid4().hex[:12]}"
        self.store.save_knowledge_card(
            card_id=card_id,
            paper_id=paper_id,
            model=self.llm.model,
            card=card.model_dump(),
        )
        out_path: Path = self.settings.reports_dir / "papers" / f"{paper_id}_card.json"
        out_path.write_text(
            json.dumps(card.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return card
