"""Knowledge graph — SQLite-backed entity and relation store.

Does not require ChromaDB; works directly with the sqlite3 module.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from app.config import get_settings


@dataclass
class Entity:
    """Bilgi grafiğindeki varlık."""

    entity_id: str
    name: str
    entity_type: str  # "concept" | "indicator" | "strategy" | "metric" | "paper"
    description: str = ""
    source_paper_id: str = ""
    source_chunk_id: str = ""


@dataclass
class Relation:
    """İki varlık arasındaki yönlü ilişki."""

    relation_id: str
    source_entity_id: str
    relation_type: str  # "affects" | "supports" | "contradicts" | "requires" | "is_measured_by"
    target_entity_id: str
    confidence: float = 1.0
    source_paper_id: str = ""
    source_chunk_id: str = ""
    extra: dict = field(default_factory=dict)


_CREATE_ENTITIES = """
CREATE TABLE IF NOT EXISTS kg_entities (
    entity_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    description TEXT DEFAULT '',
    source_paper_id TEXT DEFAULT '',
    source_chunk_id TEXT DEFAULT ''
)
"""

_CREATE_RELATIONS = """
CREATE TABLE IF NOT EXISTS kg_relations (
    relation_id TEXT PRIMARY KEY,
    source_entity_id TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    target_entity_id TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    source_paper_id TEXT DEFAULT '',
    source_chunk_id TEXT DEFAULT '',
    FOREIGN KEY (source_entity_id) REFERENCES kg_entities(entity_id),
    FOREIGN KEY (target_entity_id) REFERENCES kg_entities(entity_id)
)
"""


class KnowledgeGraph:
    """SQLite tabanlı bilgi grafiği.

    Varlıkları ve ilişkileri kalıcı olarak depolar; sorgu arayüzü sağlar.
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        settings = get_settings()
        path = Path(db_path) if db_path else settings.sqlite_file
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = str(path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(_CREATE_ENTITIES)
            conn.execute(_CREATE_RELATIONS)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_kg_entity_name ON kg_entities(name)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_kg_rel_source ON kg_relations(source_entity_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_kg_rel_target ON kg_relations(target_entity_id)"
            )
            conn.commit()

    def add_entity(self, entity: Entity) -> None:
        """Varlığı ekle veya güncelle (upsert)."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO kg_entities
                    (entity_id, name, entity_type, description, source_paper_id, source_chunk_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    entity.entity_id,
                    entity.name,
                    entity.entity_type,
                    entity.description,
                    entity.source_paper_id,
                    entity.source_chunk_id,
                ),
            )
            conn.commit()

    def add_relation(self, relation: Relation) -> None:
        """İlişkiyi ekle veya güncelle (upsert)."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO kg_relations
                    (relation_id, source_entity_id, relation_type, target_entity_id,
                     confidence, source_paper_id, source_chunk_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    relation.relation_id,
                    relation.source_entity_id,
                    relation.relation_type,
                    relation.target_entity_id,
                    relation.confidence,
                    relation.source_paper_id,
                    relation.source_chunk_id,
                ),
            )
            conn.commit()

    def get_related(self, entity_name: str) -> list[Relation]:
        """Verilen varlık adıyla ilgili tüm ilişkileri döndür."""
        with self._connect() as conn:
            # Önce entity_id bul
            row = conn.execute(
                "SELECT entity_id FROM kg_entities WHERE name = ?", (entity_name,)
            ).fetchone()
            if not row:
                return []
            eid = row["entity_id"]

            rows = conn.execute(
                """
                SELECT relation_id, source_entity_id, relation_type, target_entity_id,
                       confidence, source_paper_id, source_chunk_id
                FROM kg_relations
                WHERE source_entity_id = ? OR target_entity_id = ?
                """,
                (eid, eid),
            ).fetchall()

            return [
                Relation(
                    relation_id=r["relation_id"],
                    source_entity_id=r["source_entity_id"],
                    relation_type=r["relation_type"],
                    target_entity_id=r["target_entity_id"],
                    confidence=r["confidence"],
                    source_paper_id=r["source_paper_id"],
                    source_chunk_id=r["source_chunk_id"],
                )
                for r in rows
            ]

    def get_entity_by_name(self, name: str) -> Entity | None:
        """Ad ile varlık ara."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM kg_entities WHERE name = ?", (name,)).fetchone()
            if not row:
                return None
            return Entity(
                entity_id=row["entity_id"],
                name=row["name"],
                entity_type=row["entity_type"],
                description=row["description"],
                source_paper_id=row["source_paper_id"],
                source_chunk_id=row["source_chunk_id"],
            )
