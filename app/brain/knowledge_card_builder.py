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
    """Modelin çıktısından JSON nesnesini çıkar; küçük modellerin tipik
    bozulmalarını (kod çiti, akıllı tırnak, sondaki virgül) toleranslı onar."""
    m = _JSON_FENCE.search(text)
    raw = m.group(1) if m else text
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end != -1:
        raw = raw[start : end + 1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        repaired = raw.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
        repaired = re.sub(r",\s*([}\]])", r"\1", repaired)  # sondaki virgüller
        return json.loads(repaired)


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

    _SKELETON = (
        '{"title":"","year":"","domain":"","main_claim":"","methods":[],'
        '"datasets":[],"trading_relevance":"","limitations":[],'
        '"possible_strategy_hypotheses":[],"risk_warnings":[],'
        '"implementation_notes":[]}'
    )

    def _card_json(self, text: str, system: str, *, max_tokens: int) -> dict[str, Any]:
        """Modelden tek bir JSON kart üret; başarısızsa boş dict döner."""
        prompt = (
            f"MAKALE:\n{text}\n\n"
            f"Bu JSON şemasını makaleye göre DOLDUR, yalnızca JSON döndür:\n{self._SKELETON}\n"
            "Bilinmeyen alanı boş bırak; makalede olmayan şeyi uydurma."
        )
        try:
            out = self.llm.generate(
                prompt,
                system=system,
                temperature=0.1,
                fmt="json",
                max_tokens=max_tokens,
                timeout=180,
            )
        except Exception:  # LLM yok / ağ / zaman aşımı — kart boş kalır
            return {}
        try:
            return _extract_json(out)
        except (json.JSONDecodeError, ValueError):
            return {}

    def build(self, paper_id: str, max_chars: int = 6000) -> KnowledgeCard:
        """8GB-dostu: kısa girdi + Ollama JSON modu + num_predict cap + retry.

        Büyük metni tek seferde modele vermek (eski 14000 krk) küçük modellerde
        bozuk JSON / 7B'de timeout üretiyordu. Artık odaklı bir alıntı +
        ``fmt="json"`` ile geçerli JSON garanti altına alınır; boş kalırsa daha
        kısa metinle bir kez daha denenir.
        """
        try:
            system = load_prompt("knowledge_card")
        except FileNotFoundError:
            system = (
                "Akademik makaleden yapılandırılmış bilgi kartı çıkar. "
                "SADECE geçerli JSON döndür (markdown/açıklama yok). Kaynak uydurma."
            )

        data = self._card_json(self._load_text(paper_id)[:max_chars], system, max_tokens=900)
        if not data.get("main_claim"):
            # daha kısa alıntıyla tek retry (8GB'da hız + JSON sağlamlığı)
            data = self._card_json(self._load_text(paper_id)[:3000], system, max_tokens=700) or data

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
