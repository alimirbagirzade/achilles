"""Rule-based entity and relation extractor.

No LLM required; uses regex and keyword matching.
Detects known finance/trading entities and relations.
"""

from __future__ import annotations

import hashlib
import re

from app.memory.knowledge_graph import Entity, Relation

# ---------------------------------------------------------------------------
# Bilinen varlıklar (tip → terimler listesi)
# ---------------------------------------------------------------------------
_KNOWN_ENTITIES: dict[str, list[str]] = {
    "indicator": [
        "volatility",
        "momentum",
        "ATR",
        "drawdown",
        "Sharpe",
        "Sortino",
        "RSI",
        "MACD",
        "EMA",
        "SMA",
        "Bollinger",
        "ADX",
        "VIX",
        "Calmar",
        "beta",
        "alpha",
    ],
    "concept": [
        "regime",
        "microstructure",
        "liquidity",
        "slippage",
        "overfitting",
        "backtest",
        "mean reversion",
        "trend following",
        "carry trade",
        "risk premium",
        "factor model",
        "volatility clustering",
        "fat tail",
        "skewness",
        "kurtosis",
    ],
    "metric": [
        "return",
        "profit factor",
        "win rate",
        "max drawdown",
        "Calmar ratio",
        "information ratio",
        "hit rate",
    ],
}

# ---------------------------------------------------------------------------
# İlişki örüntüleri
# ---------------------------------------------------------------------------
_RELATION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(increases?|boosts?|amplifies?|raises?)\b", re.IGNORECASE), "affects"),
    (re.compile(r"\b(decreases?|reduces?|lowers?|dampens?)\b", re.IGNORECASE), "affects"),
    (re.compile(r"\b(supports?|confirms?|validates?|corroborates?)\b", re.IGNORECASE), "supports"),
    (
        re.compile(r"\b(contradicts?|opposes?|negates?|conflicts? with)\b", re.IGNORECASE),
        "contradicts",
    ),
    (re.compile(r"\b(requires?|depends? on|needs?|relies? on)\b", re.IGNORECASE), "requires"),
    (
        re.compile(r"\b(measured by|quantified by|captured by|proxied by)\b", re.IGNORECASE),
        "is_measured_by",
    ),
]


def _make_id(prefix: str, text: str) -> str:
    """Deterministic ID üret."""
    h = hashlib.md5(text.encode()).hexdigest()[:8]
    return f"{prefix}_{h}"


def _find_entities_in_text(text: str) -> list[Entity]:
    """Metinde geçen bilinen varlıkları bul."""
    found: dict[str, Entity] = {}
    text_lower = text.lower()

    for etype, terms in _KNOWN_ENTITIES.items():
        for term in terms:
            pattern = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
            if pattern.search(text_lower):
                norm_name = term.lower()
                if norm_name not in found:
                    found[norm_name] = Entity(
                        entity_id=_make_id("ent", norm_name),
                        name=norm_name,
                        entity_type=etype,
                        description="",
                    )
    return list(found.values())


def _find_relations_in_sentences(
    text: str,
    entities: list[Entity],
    paper_id: str,
    chunk_id: str,
) -> list[Relation]:
    """Cümle bazında varlıklar arası ilişkileri tespit et."""
    if len(entities) < 2:
        return []

    entity_names = {e.name: e for e in entities}
    relations: list[Relation] = []
    sentences = re.split(r"[.!?;]\s+", text)

    for sentence in sentences:
        sent_lower = sentence.lower()
        # Cümlede geçen varlıkları bul
        present: list[Entity] = [e for name, e in entity_names.items() if name in sent_lower]
        if len(present) < 2:
            continue

        for rel_pattern, rel_type in _RELATION_PATTERNS:
            if rel_pattern.search(sentence):
                # İlk iki varlığı bağla (basit yaklaşım)
                src = present[0]
                tgt = present[1]
                rel_id = _make_id("rel", f"{src.entity_id}_{rel_type}_{tgt.entity_id}_{chunk_id}")
                relations.append(
                    Relation(
                        relation_id=rel_id,
                        source_entity_id=src.entity_id,
                        relation_type=rel_type,
                        target_entity_id=tgt.entity_id,
                        confidence=0.7,
                        source_paper_id=paper_id,
                        source_chunk_id=chunk_id,
                    )
                )
                break  # Cümle başına tek ilişki

    return relations


class EntityRelationExtractor:
    """Kural tabanlı varlık ve ilişki çıkarıcı.

    Regex + anahtar kelime eşleştirmesi kullanır; LLM gerektirmez.
    Deterministik ve çevrimdışı test edilebilir.
    """

    def extract(
        self, text: str, paper_id: str, chunk_id: str
    ) -> tuple[list[Entity], list[Relation]]:
        """Metinden varlık ve ilişki çıkar.

        Args:
            text: İşlenecek metin (chunk içeriği).
            paper_id: Kaynak makale kimliği.
            chunk_id: Kaynak chunk kimliği.

        Returns:
            (varlıklar, ilişkiler) çifti.
        """
        entities = _find_entities_in_text(text)

        # Kaynak bilgisini entitelere ekle
        for e in entities:
            e.source_paper_id = paper_id
            e.source_chunk_id = chunk_id

        relations = _find_relations_in_sentences(text, entities, paper_id, chunk_id)

        return entities, relations
