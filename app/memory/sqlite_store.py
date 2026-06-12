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
    text,
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
    card_json: Mapped[str] = mapped_column(Text)  # tam JSON belgesi
    created_at: Mapped[str] = mapped_column(String(40), default=_utcnow)
    trust_level: Mapped[str] = mapped_column(String(32), default="draft")
    # canonical / verified / draft / unreviewed
    review_status: Mapped[str] = mapped_column(String(32), default="pending")
    # pending / approved / rejected
    lora_eligible: Mapped[int] = mapped_column(Integer, default=0)  # 0/1
    difficulty: Mapped[float] = mapped_column(Float, default=0.0)  # 0.0–1.0
    stage: Mapped[str] = mapped_column(String(32), default="")
    # lora_phase_1 / lora_phase_2 / lora_phase_3 / lora_phase_4 / ""


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


class RiskReportRow(Base):
    __tablename__ = "risk_reports"

    report_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    backtest_id: Mapped[str] = mapped_column(String(80), index=True)
    strategy_name: Mapped[str] = mapped_column(String(255))
    n_trades: Mapped[int] = mapped_column(Integer, default=0)
    win_rate: Mapped[float] = mapped_column(Float, default=0.0)
    half_kelly: Mapped[float] = mapped_column(Float, default=0.0)
    capped_kelly: Mapped[float] = mapped_column(Float, default=0.0)
    scale_factor: Mapped[float] = mapped_column(Float, default=1.0)
    position_size_pct: Mapped[float] = mapped_column(Float, default=0.0)
    position_size_usd: Mapped[float] = mapped_column(Float, default=0.0)
    report_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[str] = mapped_column(String(40), default=_utcnow)


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


class Formula(Base):
    """Bir makaleden çıkarılan matematiksel formül / gösterge."""

    __tablename__ = "formulas"

    formula_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    paper_id: Mapped[str] = mapped_column(ForeignKey("papers.paper_id"), index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)  # "RSI", "EMA"
    latex: Mapped[str | None] = mapped_column(Text, default=None)  # LaTeX gösterim
    plain: Mapped[str | None] = mapped_column(Text, default=None)  # okunabilir
    description: Mapped[str | None] = mapped_column(Text, default=None)  # ne ölçüyor
    variables_json: Mapped[str] = mapped_column(Text, default="{}")  # {"period": "..."}
    category: Mapped[str | None] = mapped_column(String(48), default=None)  # momentum/vol/trend
    created_at: Mapped[str] = mapped_column(String(40), default=_utcnow)


class ConceptLink(Base):
    """Formüller / kavramlar arası ilişki (yönlü kenar)."""

    __tablename__ = "concept_links"

    link_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    from_concept: Mapped[str] = mapped_column(String(128), index=True)
    relation: Mapped[str] = mapped_column(String(48))  # extends/measures/limits/combines
    to_concept: Mapped[str] = mapped_column(String(128), index=True)
    source_paper_id: Mapped[str | None] = mapped_column(String(64), default=None)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[str] = mapped_column(String(40), default=_utcnow)


class ResearchSession(Base):
    """Bir araştırma döngüsünün tam kaydı (hipotez → öneri → test → yansıma)."""

    __tablename__ = "research_sessions"

    session_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    question: Mapped[str] = mapped_column(Text)  # araştırma sorusu
    iteration: Mapped[int] = mapped_column(Integer, default=1)
    parent_session_id: Mapped[str | None] = mapped_column(String(80), default=None)
    source_paper_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    synthesis_reasoning: Mapped[str | None] = mapped_column(Text, default=None)
    proposed_indicator_json: Mapped[str | None] = mapped_column(Text, default=None)
    strategy_ir_json: Mapped[str | None] = mapped_column(Text, default=None)
    backtest_result_json: Mapped[str | None] = mapped_column(Text, default=None)
    verdict: Mapped[str | None] = mapped_column(String(32), default=None)
    reflection: Mapped[str | None] = mapped_column(Text, default=None)
    improvement_notes: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending/done/failed
    created_at: Mapped[str] = mapped_column(String(40), default=_utcnow)


# ---------------------------------------------------------------------------
# Advanced RAG tracking models
# ---------------------------------------------------------------------------


class ArxivSavedQuery(Base):
    """Kayıtlı arXiv arama sorgusu — tekrar kullanım ve otomasyon için."""

    __tablename__ = "arxiv_saved_queries"

    query_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    query: Mapped[str] = mapped_column(Text)
    max_results: Mapped[int] = mapped_column(Integer, default=5)
    auto_ingest: Mapped[int] = mapped_column(Integer, default=1)  # 0/1
    run_count: Mapped[int] = mapped_column(Integer, default=0)
    last_run_at: Mapped[str | None] = mapped_column(String(40), default=None)
    created_at: Mapped[str] = mapped_column(String(40), default=_utcnow)


class EvalHistory(Base):
    """Adapter versiyonu bazında eval skor geçmişi — öğrenme dinamikleri grafiği için."""

    __tablename__ = "eval_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    adapter_name: Mapped[str] = mapped_column(String(128), index=True)
    eval_set: Mapped[str] = mapped_column(String(64))
    pass_rate: Mapped[float] = mapped_column(Float, default=0.0)
    total_items: Mapped[int] = mapped_column(Integer, default=0)
    passed_items: Mapped[int] = mapped_column(Integer, default=0)
    scored_at: Mapped[str] = mapped_column(String(40), default=_utcnow)


class RagQuery(Base):
    """Records a user query and its expanded variants."""

    __tablename__ = "rag_queries"

    query_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    original_query: Mapped[str] = mapped_column(Text)
    expanded_queries_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[str] = mapped_column(String(40), default=_utcnow)


class RetrievalRun(Base):
    """Metadata for a single retrieval run."""

    __tablename__ = "retrieval_runs"

    retrieval_run_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    query_id: Mapped[str] = mapped_column(ForeignKey("rag_queries.query_id"), index=True)
    retrieval_method: Mapped[str] = mapped_column(String(64), default="semantic")
    top_k: Mapped[int] = mapped_column(Integer, default=5)
    rerank_used: Mapped[int] = mapped_column(Integer, default=0)  # 0/1
    self_refinement_used: Mapped[int] = mapped_column(Integer, default=0)  # 0/1
    created_at: Mapped[str] = mapped_column(String(40), default=_utcnow)


class RetrievalResult(Base):
    """A single chunk result from a retrieval run."""

    __tablename__ = "retrieval_results"

    result_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    retrieval_run_id: Mapped[str] = mapped_column(
        ForeignKey("retrieval_runs.retrieval_run_id"), index=True
    )
    paper_id: Mapped[str] = mapped_column(String(64), index=True)
    chunk_id: Mapped[str] = mapped_column(String(80), index=True)
    semantic_score: Mapped[float | None] = mapped_column(Float, default=None)
    rerank_score: Mapped[float | None] = mapped_column(Float, default=None)
    final_rank: Mapped[int | None] = mapped_column(Integer, default=None)
    reason: Mapped[str | None] = mapped_column(Text, default=None)


class ChunkQualityFlag(Base):
    """Quality flags for a chunk (formula, table, incomplete argument, etc.)."""

    __tablename__ = "chunk_quality_flags"

    flag_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    chunk_id: Mapped[str] = mapped_column(String(80), index=True)
    has_formula: Mapped[int] = mapped_column(Integer, default=0)
    has_incomplete_formula: Mapped[int] = mapped_column(Integer, default=0)
    has_incomplete_argument: Mapped[int] = mapped_column(Integer, default=0)
    has_table: Mapped[int] = mapped_column(Integer, default=0)
    has_definition: Mapped[int] = mapped_column(Integer, default=0)
    has_theorem: Mapped[int] = mapped_column(Integer, default=0)
    needs_adjacent_context: Mapped[int] = mapped_column(Integer, default=0)


class KnowledgeEntity(Base):
    """Knowledge graph entity (ORM version)."""

    __tablename__ = "knowledge_entities"

    entity_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    entity_type: Mapped[str] = mapped_column(String(48))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    source_paper_id: Mapped[str | None] = mapped_column(String(64), default=None)
    source_chunk_id: Mapped[str | None] = mapped_column(String(80), default=None)


class KnowledgeRelation(Base):
    """Knowledge graph relation (ORM version)."""

    __tablename__ = "knowledge_relations"

    relation_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    source_entity_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_entities.entity_id"), index=True
    )
    relation_type: Mapped[str] = mapped_column(String(48))
    target_entity_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_entities.entity_id"), index=True
    )
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    source_paper_id: Mapped[str | None] = mapped_column(String(64), default=None)
    source_chunk_id: Mapped[str | None] = mapped_column(String(80), default=None)


# ---------------------------------------------------------------------------
# Reliability / verification models
# ---------------------------------------------------------------------------


class GoldenQuestion(Base):
    """Golden set question for retrieval and answer quality evaluation."""

    __tablename__ = "golden_questions"

    question_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    question_text: Mapped[str] = mapped_column(Text)
    domain: Mapped[str] = mapped_column(String(48), default="general")
    expected_answer: Mapped[str | None] = mapped_column(Text, default=None)
    expected_source_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    expected_chunk_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    answer_type: Mapped[str] = mapped_column(String(32), default="factual")
    difficulty: Mapped[str] = mapped_column(String(16), default="medium")
    created_by: Mapped[str] = mapped_column(String(64), default="system")
    reviewed: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String(40), default=_utcnow)


class FailureLog(Base):
    """RAG answer failure record."""

    __tablename__ = "failure_logs"

    failure_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    question_text: Mapped[str] = mapped_column(Text)
    answer_text: Mapped[str] = mapped_column(Text, default="")
    failure_type: Mapped[str] = mapped_column(String(48))
    root_cause: Mapped[str | None] = mapped_column(Text, default=None)
    hallucination: Mapped[int] = mapped_column(Integer, default=0)
    wrong_citation: Mapped[int] = mapped_column(Integer, default=0)
    suggested_fix: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[str] = mapped_column(String(40), default=_utcnow)


class VerificationRun(Base):
    """Record of a verification pass run for a single answer."""

    __tablename__ = "verification_runs"

    verification_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    answer_id: Mapped[str] = mapped_column(String(80), index=True)
    citation_passed: Mapped[int] = mapped_column(Integer, default=0)
    grounding_passed: Mapped[int] = mapped_column(Integer, default=0)
    contradiction_passed: Mapped[int] = mapped_column(Integer, default=0)
    formula_passed: Mapped[int] = mapped_column(Integer, default=0)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    final_decision: Mapped[str] = mapped_column(String(16), default="warn")
    created_at: Mapped[str] = mapped_column(String(40), default=_utcnow)


class RewardSignal(Base):
    """Bir tool-use seansının doğrulanabilir ödül skoru."""

    __tablename__ = "reward_signals"

    signal_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(80), index=True, unique=True)
    composite_score: Mapped[float] = mapped_column(Float, default=0.0)
    label: Mapped[str] = mapped_column(String(16), default="neutral")
    execution_ok: Mapped[float] = mapped_column(Float, default=0.0)
    trade_count_ok: Mapped[float] = mapped_column(Float, default=0.0)
    sharpe_ok: Mapped[float] = mapped_column(Float, default=0.0)
    drawdown_ok: Mapped[float] = mapped_column(Float, default=0.0)
    return_ok: Mapped[float] = mapped_column(Float, default=0.0)
    win_rate_ok: Mapped[float] = mapped_column(Float, default=0.0)
    notes_json: Mapped[str] = mapped_column(Text, default="[]")
    raw_metrics_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[str] = mapped_column(String(40), default=_utcnow)


class ToolUseExample(Base):
    """Tool-use eğitim örneği — bir araştırma döngüsündeki tek araç çağrısı adımı."""

    __tablename__ = "tool_use_examples"

    example_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(80), index=True)
    question: Mapped[str] = mapped_column(Text)
    step_index: Mapped[int] = mapped_column(Integer, default=0)
    # think | call | observe | conclude
    step_type: Mapped[str] = mapped_column(String(20))
    tool_name: Mapped[str | None] = mapped_column(String(80), default=None)
    tool_input_json: Mapped[str] = mapped_column(Text, default="{}")
    tool_output_json: Mapped[str] = mapped_column(Text, default="{}")
    content: Mapped[str] = mapped_column(Text, default="")
    verdict: Mapped[str | None] = mapped_column(String(20), default=None)
    created_at: Mapped[str] = mapped_column(String(40), default=_utcnow)


class PaperComprehension(Base):
    """Makale anlama skoru — 3 katmanlı hesaplama sonucu."""

    __tablename__ = "paper_comprehension"

    paper_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    extraction_score: Mapped[float] = mapped_column(Float, default=0.0)
    retrieval_score: Mapped[float] = mapped_column(Float, default=0.0)
    llm_score: Mapped[float] = mapped_column(Float, default=0.0)
    total_score: Mapped[float] = mapped_column(Float, default=0.0)
    details_json: Mapped[str] = mapped_column(Text, default="{}")
    computed_at: Mapped[str] = mapped_column(String(40), default=_utcnow)


class SqliteStore:
    """Thin wrapper around a SQLAlchemy engine + session factory."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        settings = get_settings()
        self.db_path = Path(db_path) if db_path else settings.sqlite_file
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{self.db_path}", future=True)
        self._Session = sessionmaker(bind=self.engine, expire_on_commit=False, future=True)
        self.create_all()
        self._migrate()

    def create_all(self) -> None:
        Base.metadata.create_all(self.engine)

    def _migrate(self) -> None:
        """Eksik kolonları SQLite'a ekle (idempotent)."""
        with self.engine.connect() as conn:
            existing = {
                row[1]
                for row in conn.execute(text("PRAGMA table_info(knowledge_cards)")).fetchall()
            }
            new_cols = [
                ("trust_level", "VARCHAR(32)", "'draft'"),
                ("review_status", "VARCHAR(32)", "'pending'"),
                ("lora_eligible", "INTEGER", "0"),
                ("difficulty", "REAL", "0.0"),
                ("stage", "VARCHAR(32)", "''"),
            ]
            for col, typ, default in new_cols:
                if col not in existing:
                    conn.execute(
                        text(
                            f"ALTER TABLE knowledge_cards ADD COLUMN {col} {typ} DEFAULT {default}"
                        )
                    )
            conn.commit()

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

    def save_knowledge_card(
        self,
        card_id: str,
        paper_id: str,
        model: str,
        card: dict,
        *,
        trust_level: str = "draft",
        review_status: str = "pending",
        lora_eligible: int = 0,
        difficulty: float = 0.0,
        stage: str = "",
    ) -> None:
        with self.session() as s:
            s.merge(
                KnowledgeCard(
                    card_id=card_id,
                    paper_id=paper_id,
                    model=model,
                    card_json=json.dumps(card, ensure_ascii=False),
                    trust_level=trust_level,
                    review_status=review_status,
                    lora_eligible=lora_eligible,
                    difficulty=difficulty,
                    stage=stage,
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

    def save_comprehension_score(self, score: ComprehensionScore) -> None:  # type: ignore[name-defined]
        import json as _json

        with self.session() as s:
            row = s.get(PaperComprehension, score.paper_id)
            if row is None:
                row = PaperComprehension(paper_id=score.paper_id)
                s.add(row)
            row.extraction_score = score.extraction
            row.retrieval_score = score.retrieval
            row.llm_score = score.llm_verify
            row.total_score = score.total
            row.details_json = _json.dumps(score.details, ensure_ascii=False)
            row.computed_at = score.computed_at

    def get_comprehension_score(self, paper_id: str) -> PaperComprehension | None:
        with self.session() as s:
            return s.get(PaperComprehension, paper_id)

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

    def approve_card(self, card_id: str) -> bool:
        """Kartı onayla: review_status=approved, lora_eligible=1."""
        with self.session() as s:
            row = s.get(KnowledgeCard, card_id)
            if row is None:
                return False
            row.review_status = "approved"
            row.lora_eligible = 1
            return True

    def reject_card(self, card_id: str) -> bool:
        """Kartı reddet: review_status=rejected, lora_eligible=0."""
        with self.session() as s:
            row = s.get(KnowledgeCard, card_id)
            if row is None:
                return False
            row.review_status = "rejected"
            row.lora_eligible = 0
            return True

    def list_pending_cards(self) -> list[dict]:
        """review_status=pending olan kartları döndür.

        Her dict: card_id, paper_id, model, trust_level, review_status,
                   lora_eligible, difficulty, stage, created_at, card_json (parsed)
        """
        with self.session() as s:
            rows = list(
                s.scalars(
                    select(KnowledgeCard)
                    .where(KnowledgeCard.review_status == "pending")
                    .order_by(KnowledgeCard.created_at.desc())
                )
            )
            return [self._card_to_dict(r) for r in rows]

    def list_approved_cards(
        self,
        difficulty_min: float = 0.0,
        difficulty_max: float = 1.0,
    ) -> list[dict]:
        """Onaylı (approved) kartları difficulty aralığına göre filtrele."""
        with self.session() as s:
            rows = list(
                s.scalars(
                    select(KnowledgeCard)
                    .where(
                        KnowledgeCard.review_status == "approved",
                        KnowledgeCard.difficulty >= difficulty_min,
                        KnowledgeCard.difficulty <= difficulty_max,
                    )
                    .order_by(KnowledgeCard.difficulty)
                )
            )
            return [self._card_to_dict(r) for r in rows]

    def get_card_by_id(self, card_id: str) -> dict | None:
        """Tek kartı card_id ile döndür (review metadata dahil)."""
        with self.session() as s:
            row = s.get(KnowledgeCard, card_id)
            if row is None:
                return None
            return self._card_to_dict(row)

    def _card_to_dict(self, row: KnowledgeCard) -> dict:
        """KnowledgeCard ORM satırını dict'e dönüştür."""
        try:
            parsed = json.loads(row.card_json)
        except (json.JSONDecodeError, TypeError):
            parsed = {}
        return {
            "card_id": row.card_id,
            "paper_id": row.paper_id,
            "model": row.model,
            "trust_level": row.trust_level,
            "review_status": row.review_status,
            "lora_eligible": row.lora_eligible,
            "difficulty": row.difficulty,
            "stage": row.stage,
            "created_at": row.created_at,
            "card_json": parsed,
        }

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

    def save_risk_report(self, report_id: str, backtest_id: str, report_dict: dict) -> None:
        """Risk raporunu upsert ile kaydet (idempotent)."""
        kelly = report_dict.get("kelly", {})
        dd = report_dict.get("drawdown_scale", {})
        fr = report_dict.get("fixed_risk", {})
        with self.session() as s:
            s.merge(
                RiskReportRow(
                    report_id=report_id,
                    backtest_id=backtest_id,
                    strategy_name=report_dict.get("strategy_name", ""),
                    n_trades=report_dict.get("n_trades", 0),
                    win_rate=kelly.get("win_rate", 0.0),
                    half_kelly=kelly.get("half_kelly", 0.0),
                    capped_kelly=kelly.get("capped_kelly", 0.0),
                    scale_factor=dd.get("scale_factor", 1.0),
                    position_size_pct=fr.get("position_size_pct", 0.0),
                    position_size_usd=fr.get("position_size_usd", 0.0),
                    report_json=json.dumps(report_dict, ensure_ascii=False),
                )
            )

    def list_risk_reports(self, limit: int = 50) -> list[dict[str, Any]]:
        """Son `limit` adet risk raporunu yeni→eski sırasıyla döndür."""
        with self.session() as s:
            rows = list(
                s.scalars(
                    select(RiskReportRow).order_by(RiskReportRow.created_at.desc()).limit(limit)
                )
            )
            return [
                {
                    "report_id": r.report_id,
                    "backtest_id": r.backtest_id,
                    "strategy_name": r.strategy_name,
                    "n_trades": r.n_trades,
                    "win_rate": r.win_rate,
                    "half_kelly": r.half_kelly,
                    "capped_kelly": r.capped_kelly,
                    "scale_factor": r.scale_factor,
                    "position_size_pct": r.position_size_pct,
                    "position_size_usd": r.position_size_usd,
                    "created_at": r.created_at,
                }
                for r in rows
            ]

    def get_risk_report(self, report_id: str) -> dict | None:
        """Tam rapor JSON'unu döndür (yoksa None)."""
        with self.session() as s:
            row = s.get(RiskReportRow, report_id)
            if row is None:
                return None
            try:
                return json.loads(row.report_json)
            except (json.JSONDecodeError, TypeError):
                return None

    def save_arxiv_query(
        self, query_id: str, query: str, max_results: int = 5, auto_ingest: bool = True
    ) -> None:
        with self.session() as s:
            s.merge(
                ArxivSavedQuery(
                    query_id=query_id,
                    query=query,
                    max_results=max_results,
                    auto_ingest=1 if auto_ingest else 0,
                )
            )

    def list_arxiv_saved_queries(self) -> list[dict[str, Any]]:
        with self.session() as s:
            rows = list(
                s.scalars(select(ArxivSavedQuery).order_by(ArxivSavedQuery.created_at.desc()))
            )
            return [
                {
                    "query_id": r.query_id,
                    "query": r.query,
                    "max_results": r.max_results,
                    "auto_ingest": bool(r.auto_ingest),
                    "run_count": r.run_count,
                    "last_run_at": r.last_run_at,
                    "created_at": r.created_at,
                }
                for r in rows
            ]

    def delete_arxiv_query(self, query_id: str) -> bool:
        with self.session() as s:
            row = s.get(ArxivSavedQuery, query_id)
            if row is None:
                return False
            s.delete(row)
            return True

    def mark_arxiv_query_ran(self, query_id: str) -> None:
        with self.session() as s:
            row = s.get(ArxivSavedQuery, query_id)
            if row:
                row.run_count += 1
                row.last_run_at = _utcnow()

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

    # ---------- formüller ----------
    def save_formula(self, **fields: Any) -> None:
        with self.session() as s:
            s.merge(Formula(**fields))

    def list_formulas(self, paper_id: str | None = None) -> list[dict[str, Any]]:
        with self.session() as s:
            q = select(Formula)
            if paper_id:
                q = q.where(Formula.paper_id == paper_id)
            rows = list(s.scalars(q.order_by(Formula.name)))
            return [
                {
                    "formula_id": r.formula_id,
                    "paper_id": r.paper_id,
                    "name": r.name,
                    "latex": r.latex,
                    "plain": r.plain,
                    "description": r.description,
                    "variables": json.loads(r.variables_json or "{}"),
                    "category": r.category,
                }
                for r in rows
            ]

    def formula_exists(self, paper_id: str, name: str) -> bool:
        with self.session() as s:
            return (
                s.scalar(
                    select(Formula.formula_id)
                    .where(Formula.paper_id == paper_id, Formula.name == name)
                    .limit(1)
                )
                is not None
            )

    # ---------- kavram grafiği ----------
    def save_concept_link(self, **fields: Any) -> None:
        with self.session() as s:
            s.add(ConceptLink(**fields))

    def list_concept_links(self, concept: str | None = None) -> list[dict[str, Any]]:
        with self.session() as s:
            q = select(ConceptLink)
            if concept:
                q = q.where(
                    (ConceptLink.from_concept == concept) | (ConceptLink.to_concept == concept)
                )
            rows = list(s.scalars(q))
            return [
                {
                    "from_concept": r.from_concept,
                    "relation": r.relation,
                    "to_concept": r.to_concept,
                    "source_paper_id": r.source_paper_id,
                }
                for r in rows
            ]

    # ---------- araştırma oturumları ----------
    def save_research_session(self, **fields: Any) -> None:
        with self.session() as s:
            s.merge(ResearchSession(**fields))

    def get_research_session(self, session_id: str) -> dict[str, Any] | None:
        with self.session() as s:
            row = s.get(ResearchSession, session_id)
            if row is None:
                return None
            return self._session_to_dict(row)

    def list_research_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.session() as s:
            rows = list(
                s.scalars(
                    select(ResearchSession).order_by(ResearchSession.created_at.desc()).limit(limit)
                )
            )
            return [self._session_to_dict(r) for r in rows]

    def _session_to_dict(self, r: ResearchSession) -> dict[str, Any]:
        return {
            "session_id": r.session_id,
            "question": r.question,
            "iteration": r.iteration,
            "parent_session_id": r.parent_session_id,
            "source_paper_ids": json.loads(r.source_paper_ids_json or "[]"),
            "synthesis_reasoning": r.synthesis_reasoning,
            "proposed_indicator": json.loads(r.proposed_indicator_json or "null"),
            "strategy_ir": json.loads(r.strategy_ir_json or "null"),
            "backtest_result": json.loads(r.backtest_result_json or "null"),
            "verdict": r.verdict,
            "reflection": r.reflection,
            "improvement_notes": r.improvement_notes,
            "status": r.status,
            "created_at": r.created_at,
        }

    # ---- reward_signals ----

    def save_reward_signal(
        self,
        session_id: str,
        criteria: Any,  # RewardCriteria — circular import önlemek için Any
        raw_metrics: dict | None = None,
    ) -> str:
        import hashlib

        signal_id = "rs_" + hashlib.md5(session_id.encode()).hexdigest()[:16]
        with self.session() as s:
            s.merge(
                RewardSignal(
                    signal_id=signal_id,
                    session_id=session_id,
                    composite_score=criteria.composite,
                    label=criteria.label,
                    execution_ok=criteria.execution_ok,
                    trade_count_ok=criteria.trade_count_ok,
                    sharpe_ok=criteria.sharpe_ok,
                    drawdown_ok=criteria.drawdown_ok,
                    return_ok=criteria.return_ok,
                    win_rate_ok=criteria.win_rate_ok,
                    notes_json=json.dumps(criteria.notes, ensure_ascii=False),
                    raw_metrics_json=json.dumps(raw_metrics or {}, ensure_ascii=False),
                )
            )
        return signal_id

    def list_reward_signals(
        self, label: str | None = None, limit: int = 200
    ) -> list[dict[str, Any]]:
        with self.session() as s:
            q = select(RewardSignal).order_by(RewardSignal.composite_score.desc())
            if label:
                q = q.where(RewardSignal.label == label)
            rows = list(s.scalars(q.limit(limit)))
            return [
                {
                    "signal_id": r.signal_id,
                    "session_id": r.session_id,
                    "composite_score": r.composite_score,
                    "label": r.label,
                    "execution_ok": r.execution_ok,
                    "trade_count_ok": r.trade_count_ok,
                    "sharpe_ok": r.sharpe_ok,
                    "drawdown_ok": r.drawdown_ok,
                    "return_ok": r.return_ok,
                    "win_rate_ok": r.win_rate_ok,
                    "notes": json.loads(r.notes_json),
                    "raw_metrics": json.loads(r.raw_metrics_json),
                    "created_at": r.created_at,
                }
                for r in rows
            ]

    def get_reward_signal(self, session_id: str) -> dict[str, Any] | None:
        with self.session() as s:
            row = s.scalars(
                select(RewardSignal).where(RewardSignal.session_id == session_id)
            ).first()
            if not row:
                return None
            return {
                "signal_id": row.signal_id,
                "session_id": row.session_id,
                "composite_score": row.composite_score,
                "label": row.label,
                "notes": json.loads(row.notes_json),
                "raw_metrics": json.loads(row.raw_metrics_json),
            }

    # ---- tool_use_examples ----

    def save_tool_use_example(
        self,
        example_id: str,
        session_id: str,
        question: str,
        step_index: int,
        step_type: str,
        content: str,
        tool_name: str | None = None,
        tool_input: dict | None = None,
        tool_output: dict | None = None,
        verdict: str | None = None,
    ) -> None:
        with self.session() as s:
            s.merge(
                ToolUseExample(
                    example_id=example_id,
                    session_id=session_id,
                    question=question,
                    step_index=step_index,
                    step_type=step_type,
                    tool_name=tool_name,
                    tool_input_json=json.dumps(tool_input or {}, ensure_ascii=False),
                    tool_output_json=json.dumps(tool_output or {}, ensure_ascii=False),
                    content=content,
                    verdict=verdict,
                )
            )

    def list_tool_use_examples(
        self, session_id: str | None = None, limit: int = 500
    ) -> list[dict[str, Any]]:
        with self.session() as s:
            q = select(ToolUseExample).order_by(
                ToolUseExample.session_id, ToolUseExample.step_index
            )
            if session_id:
                q = q.where(ToolUseExample.session_id == session_id)
            rows = list(s.scalars(q.limit(limit)))
            return [
                {
                    "example_id": r.example_id,
                    "session_id": r.session_id,
                    "question": r.question,
                    "step_index": r.step_index,
                    "step_type": r.step_type,
                    "tool_name": r.tool_name,
                    "tool_input": json.loads(r.tool_input_json),
                    "tool_output": json.loads(r.tool_output_json),
                    "content": r.content,
                    "verdict": r.verdict,
                    "created_at": r.created_at,
                }
                for r in rows
            ]


    # ------------------------------------------------------------------ eval history

    def save_eval_history(
        self,
        adapter_name: str,
        eval_set: str,
        pass_rate: float,
        total_items: int = 0,
        passed_items: int = 0,
    ) -> None:
        with self.session() as s:
            s.add(
                EvalHistory(
                    adapter_name=adapter_name,
                    eval_set=eval_set,
                    pass_rate=pass_rate,
                    total_items=total_items,
                    passed_items=passed_items,
                )
            )

    def list_eval_history(self, limit: int = 200) -> list[dict[str, Any]]:
        with self.session() as s:
            rows = list(
                s.scalars(
                    select(EvalHistory)
                    .order_by(EvalHistory.scored_at)
                    .limit(limit)
                )
            )
            return [
                {
                    "adapter_name": r.adapter_name,
                    "eval_set": r.eval_set,
                    "pass_rate": r.pass_rate,
                    "total_items": r.total_items,
                    "passed_items": r.passed_items,
                    "scored_at": r.scored_at,
                }
                for r in rows
            ]

    def list_card_growth(self) -> list[dict[str, Any]]:
        """Günlük onaylı kart sayısı — öğrenme grafiği için."""
        with self.session() as s:
            rows = list(
                s.execute(
                    text(
                        """
                        SELECT date(created_at) AS day, COUNT(*) AS cnt
                        FROM knowledge_cards
                        WHERE review_status = 'approved'
                        GROUP BY day
                        ORDER BY day
                        """
                    )
                )
            )
            cumulative, result = 0, []
            for day, cnt in rows:
                cumulative += cnt
                result.append({"day": day, "daily": cnt, "cumulative": cumulative})
            return result


if __name__ == "__main__":  # pragma: no cover
    store = SqliteStore()
    print(f"SQLite hazır: {store.db_path}")
    print("Tablolar:", ", ".join(Base.metadata.tables))
