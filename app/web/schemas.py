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


# ---------- Eğitim ----------
class AdapterOut(BaseModel):
    version: str
    base_model: str
    adapter_path: str
    created_at: str
    notes: str | None = None


class TrainingStatusResponse(BaseModel):
    n_examples: int
    adapters: list[AdapterOut]


class DatasetBuildResponse(BaseModel):
    n_train: int
    n_valid: int
    content_hash: str
    message: str


class TrainDryRunRequest(BaseModel):
    base_model: str = "mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit"
    iterations: int = Field(default=300, ge=50, le=5000)
    batch_size: int = Field(default=2, ge=1, le=16)
    learning_rate: float = Field(default=1e-4, gt=0)
    num_layers: int = Field(default=8, ge=1, le=64)


class TrainDryRunResponse(BaseModel):
    command: str
    n_train: int
    n_valid: int
    content_hash: str
    message: str


# ---------- Hipotez backtest ----------
class HypothesisResult(BaseModel):
    hypothesis: str
    strategy_name: str
    verdict: str
    reasons: list[str]
    metrics: dict


class HypothesisBacktestResponse(BaseModel):
    paper_id: str
    n_hypotheses: int
    results: list[HypothesisResult]


# ---------- Backtest geçmişi ----------
class BacktestRecord(BaseModel):
    backtest_id: str
    strategy_name: str
    market: str | None = None
    timeframe: str | None = None
    data_file: str | None = None
    n_trades: int = 0
    total_return_pct: float = 0.0
    sharpe: float | None = None
    max_drawdown_pct: float | None = None
    win_rate_pct: float | None = None
    verdict: str | None = None
    notes: str | None = None
    created_at: str


class BacktestHistoryResponse(BaseModel):
    records: list[BacktestRecord]
    total: int


# ---------- Eğitim örneği ----------
class TrainingExampleOut(BaseModel):
    example_id: str
    source_paper_id: str | None = None
    example_type: str
    instruction: str
    input_text: str
    output_text: str
    created_at: str


class TrainingExamplesResponse(BaseModel):
    examples: list[TrainingExampleOut]
    total: int
