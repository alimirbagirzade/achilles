"""Summarize a paper with the local LLM and persist the summary."""

from __future__ import annotations

import uuid

from app.brain.local_llm import LocalLLM
from app.brain.prompt_loader import load_prompt
from app.config import get_settings
from app.memory.sqlite_store import SqliteStore, Summary


class PaperSummarizer:
    def __init__(self, store: SqliteStore | None = None, llm: LocalLLM | None = None) -> None:
        self.store = store or SqliteStore()
        self.llm = llm or LocalLLM()
        self.settings = get_settings()

    def _load_text(self, paper_id: str) -> str:
        path = self.settings.extracted_text_dir / f"{paper_id}.txt"
        if path.exists():
            return path.read_text(encoding="utf-8")
        chunks = self.store.list_chunks(paper_id)
        return "\n\n".join(c.text for c in chunks)

    def summarize(self, paper_id: str, max_chars: int = 12000) -> str:
        text = self._load_text(paper_id)[:max_chars]
        try:
            system = load_prompt("paper_summary")
        except FileNotFoundError:
            system = "Akademik makaleyi tarafsız ve öz biçimde özetle."
        out = self.llm.generate(f"MAKALE:\n{text}\n\nÖZET:", system=system, temperature=0.2)
        with self.store.session() as s:
            s.add(
                Summary(
                    summary_id=f"sum_{uuid.uuid4().hex[:12]}",
                    paper_id=paper_id,
                    model=self.llm.model,
                    summary_text=out,
                )
            )
        return out
