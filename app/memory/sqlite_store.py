"""SQLite structured store (SQLAlchemy 2.0).

Holds every durable, queryable record in the system:
papers, chunks, summaries, knowledge cards, training examples,
strategies, backtests, model evaluations and adapter metadata.

Every object carries a stable string ID so it can be cross-referenced
with the ChromaDB vector memory.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import (
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    select,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)

from app.config import get_settings


def _utcnow() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


class Base(DeclarativeBase):
    pass


class Paper(Base):
    __tablename__ = "papers"

    paper_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    file_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    source_path: Mapped[str] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text, default=None)
    authors: Mapped[str | None] = mapped_column(Text, default=None)  # JSON list
    year: Mapped[str | None] = mapped_column(String(8), default=None)
    source: Mapped[str | None] = mapped_column(String(64), default=None)  # arxiv/ssrn/manual
    n_pages: Mapped[int | None] = mapped_column(Integer, default=None)
    n_chars: Mapped[int | None] = mapped_column(Integer, default=None)
    created_at: Mapped[str] = mapped_column(String(40), default=_utcnow)

    chunks: Mapped[list[Chunk]] = relationship(back_populates="paper", cascade="all, delete-orphan")


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (UniqueConstraint("paper_id", "chunk_index", name="uq_paper_chunk"),)

    chunk_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    paper_id: Mapped[str] = mapped_column(ForeignKey("papers.paper_id"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    section_name: Mapped[str | None] = mapped_column(Text, default=None)
    page_number: Mapped[int | None] = mapped_column(Integer, default=None)
    text: Mapped[str] = mapped_column(Text)
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    token_estimate: Mapped[int] = mapped_column(Integer, default=0)
    embedded: Mapped[int] = mapped_column(Integer, default=0)  # 0/1 flag
    created_at: Mapped[str] = mapped_column(String(40), default=_utcnow)

    paper: Mapped[Paper] = relationship(back_populates="chunks")


class Summary(Base):
    __tablename__ = "summaries"

    summary_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    paper_id: Mapped[str] = mapped_column(ForeignKey("papers.paper_id"), index=True)
    model: Mapped[str] = mapped_column(String(64))
    summary_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(40), default=_utcnow)


class KnowledgeCard(Base):
    __tablename__ = "knowledge_cards"

    card_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    paper_id: Mapped[str] = mapped_column(ForeignKey("papers.paper_id"), index=True)
    model: Mapped[str] = mapped_column(String(64))
    card_json: Mapped[str] = mapped_column(Text)  # full JSON document
    created_at: Mapped[str] = mapped_column(String(40), default=_utcnow)


class TrainingExample(Base):
    __tablename__ = "training_examples"

    example_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    source_paper_id: Mapped[str | None] = mapped_column(String(64), default=None, index=True)
    example_type: Mapped[str] = mapped_column(String(48))
    instruction: Mapped[str] = mapped_column(Text)
    input_text: Mapped[str] = mapped_column(Text, default="")
    output_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(40), default=_utcnow)


class Strategy(Base):
    __tablename__ = "strategies"

    strategy_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    market: Mapped[str] = mapped_column(String(32))
    timeframe: Mapped[str] = mapped_column(String(16))
    ir_json: Mapped[str] = mapped_column(Text)  # Strategy IR document
    origin: Mapped[str] = mapped_column(String(32), default="manual")  # manual/generated
    source_paper_id: Mapped[str | None] = mapped_column(String(64), default=None)
    created_at: Mapped[str] = mapped_column(String(40), default=_utcnow)

    backtests: Mapped[list[Backtest]] = relationship(
        back_populates="strategy", cascade="all, delete-orphan"
    )


class Backtest(Base):
    __tablename__ = "backtests"

    backtest_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    strategy_id: Mapped[str] = mapped_column(ForeignKey("strategies.strategy_id"), index=True)
    data_file: Mapped[str] = mapped_column(Text)
    period_start: Mapped[str | None] = mapped_column(String(40), default=None)
    period_end: Mapped[str | None] = mapped_column(String(40), default=None)
    n_trades: Mapped[int] = mapped_column(Integer, default=0)
    total_return_pct: Mapped[float] = mapped_column(Float, default=0.0)
    sharpe: Mapped[float | None] = mapped_column(Float, default=None)
    sortino: Mapped[float | None] = mapped_column(Float, default=None)
    max_drawdown_pct: Mapped[float | None] = mapped_column(Float, default=None)
    profit_factor: Mapped[float | None] = mapped_column(Float, default=None)
    win_rate_pct: Mapped[float | None] = mapped_column(Float, default=None)
    metrics_json: Mapped[str] = mapped_column(Text, default="{}")
    verdict: Mapped[str | None] = mapped_column(String(32), default=None)  # pass/fail/inconclusive
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[str] = mapped_column(String(40), default=_utcnow)

    strategy: Mapped[Strategy] = relationship(back_populates="backtests")


class ModelEvaluation(Base):
    __tablename__ = "model_evaluations"

    eval_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    eval_set: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(96))
    adapter_version: Mapped[str | None] = mapped_column(String(64), default=None)
    score: Mapped[float | None] = mapped_column(Float, default=None)
    results_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[str] = mapped_column(String(40), default=_utcnow)


class Adapter(Base):
    __tablename__ = "adapters"

    version: Mapped[str] = mapped_column(String(64), primary_key=True)
    base_model: Mapped[str] = mapped_column(String(96))
    adapter_path: Mapped[str] = mapped_column(Text)
    training_data_hash: Mapped[str | None] = mapped_column(String(64), default=None)
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[str] = mapped_column(String(40), default=_utcnow)


class SqliteStore:
    """Thin wrapper around a SQLAlchemy engine + session factory."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        settings = get_settings()
        self.db_path = Path(db_path) if db_path else settings.sqlite_file
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{self.db_path}", future=True)
        self._Session = sessionmaker(bind=self.engine, expire_on_commit=False, future=True)
        self.create_all()

    def create_all(self) -> None:
        Base.metadata.create_all(self.engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        s = self._Session()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    # --- convenience helpers ---------------------------------------------
    def upsert_paper(self, **fields: Any) -> Paper:
        with self.session() as s:
            existing = s.get(Paper, fields["paper_id"])
            if existing:
                for k, v in fields.items():
                    setattr(existing, k, v)
                return existing
            paper = Paper(**fields)
            s.add(paper)
            return paper

    def get_paper_by_hash(self, file_hash: str) -> Paper | None:
        with self.session() as s:
            return s.scalar(select(Paper).where(Paper.file_hash == file_hash))

    def add_chunks(self, chunks: list[dict[str, Any]]) -> int:
        with self.session() as s:
            for c in chunks:
                s.merge(Chunk(**c))
            return len(chunks)

    def list_papers(self) -> list[Paper]:
        with self.session() as s:
            return list(s.scalars(select(Paper).order_by(Paper.created_at.desc())))

    def list_chunks(self, paper_id: str) -> list[Chunk]:
        with self.session() as s:
            return list(
                s.scalars(
                    select(Chunk).where(Chunk.paper_id == paper_id).order_by(Chunk.chunk_index)
                )
            )

    def save_knowledge_card(self, card_id: str, paper_id: str, model: str, card: dict) -> None:
        with self.session() as s:
            s.merge(
                KnowledgeCard(
                    card_id=card_id,
                    paper_id=paper_id,
                    model=model,
                    card_json=json.dumps(card, ensure_ascii=False),
                )
            )

    def has_knowledge_card(self, paper_id: str) -> bool:
        with self.session() as s:
            return (
                s.scalar(
                    select(KnowledgeCard.card_id).where(KnowledgeCard.paper_id == paper_id).limit(1)
                )
                is not None
            )

    def get_latest_knowledge_card(self, paper_id: str) -> dict | None:
        """En son üretilmiş kartın JSON içeriğini döndür (yoksa None)."""
        with self.session() as s:
            row = s.scalar(
                select(KnowledgeCard)
                .where(KnowledgeCard.paper_id == paper_id)
                .order_by(KnowledgeCard.created_at.desc())
                .limit(1)
            )
            if row is None:
                return None
            try:
                return json.loads(row.card_json)
            except (json.JSONDecodeError, TypeError):
                return None

    def save_strategy(self, **fields: Any) -> None:
        with self.session() as s:
            s.merge(Strategy(**fields))

    def save_backtest(self, **fields: Any) -> None:
        with self.session() as s:
            s.merge(Backtest(**fields))

    def list_backtests(self, limit: int = 50) -> list[dict[str, Any]]:
        """Son `limit` adet backtest kaydını yeni→eski sırasıyla döndür."""
        with self.session() as s:
            rows = list(
                s.scalars(select(Backtest).order_by(Backtest.created_at.desc()).limit(limit))
            )
            out = []
            for r in rows:
                strat = s.get(Strategy, r.strategy_id)
                out.append(
                    {
                        "backtest_id": r.backtest_id,
                        "strategy_name": strat.name if strat else r.strategy_id,
                        "market": strat.market if strat else None,
                        "timeframe": strat.timeframe if strat else None,
                        "data_file": r.data_file,
                        "n_trades": r.n_trades,
                        "total_return_pct": r.total_return_pct,
                        "sharpe": r.sharpe,
                        "max_drawdown_pct": r.max_drawdown_pct,
                        "win_rate_pct": r.win_rate_pct,
                        "verdict": r.verdict,
                        "notes": r.notes,
                        "created_at": r.created_at,
                    }
                )
            return out

    def list_training_examples(self, limit: int = 200) -> list[dict[str, Any]]:
        with self.session() as s:
            rows = list(
                s.scalars(
                    select(TrainingExample).order_by(TrainingExample.created_at.desc()).limit(limit)
                )
            )
            return [
                {
                    "example_id": r.example_id,
                    "source_paper_id": r.source_paper_id,
                    "example_type": r.example_type,
                    "instruction": r.instruction,
                    "input_text": r.input_text,
                    "output_text": r.output_text,
                    "created_at": r.created_at,
                }
                for r in rows
            ]

    def delete_training_example(self, example_id: str) -> bool:
        with self.session() as s:
            row = s.get(TrainingExample, example_id)
            if row is None:
                return False
            s.delete(row)
            return True


if __name__ == "__main__":  # pragma: no cover
    store = SqliteStore()
    print(f"SQLite hazır: {store.db_path}")
    print("Tablolar:", ", ".join(Base.metadata.tables))
