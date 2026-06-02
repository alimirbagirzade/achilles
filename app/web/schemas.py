"""Web API için Pydantic şemaları (girdi doğrulama + tipli yanıtlar)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class StatusResponse(BaseModel):
    llm_model: str
    ollama_available: bool
    embedding_mode: str
    n_papers: int
    n_chunks: int
    max_upload_mb: int = 50


class PaperOut(BaseModel):
    paper_id: str
    title: str | None = None
    year: str | None = None
    authors: str | None = None
    n_chunks: int = 0
    has_card: bool = False


class IngestResponse(BaseModel):
    ingested: int
    skipped: int
    papers: list[PaperOut] = Field(default_factory=list)
    message: str


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    top_k: int | None = Field(default=None, ge=1, le=20)


class SourceOut(BaseModel):
    paper_id: str
    chunk_id: str
    title: str | None = None
    page: int | None = None
    distance: float | None = None


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceOut] = Field(default_factory=list)
    llm_used: bool
    embedding_mode: str


class BacktestRequest(BaseModel):
    # Boşsa örnek strateji + sentetik veri kullanılır.
    use_synthetic: bool = True
    n_bars: int = Field(default=2000, ge=200, le=20000)
    seed: int = Field(default=42, ge=0, le=10_000_000)
    strategy_ir: dict | None = None


class BacktestResponse(BaseModel):
    strategy_name: str
    metrics: dict
    verdict: str
    reasons: list[str]
    backtest_id: str | None = None
    data_source: str | None = None
    n_bars: int | None = None


class CardResponse(BaseModel):
    paper_id: str
    card: dict
    message: str
