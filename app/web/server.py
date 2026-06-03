"""Achilles Trader AI — güvenlikli yerel web arayüzü (FastAPI).

Mevcut çekirdek motoru (ingestion, RAG, backtest) saran ince bir katmandır.
Motoru YENİDEN YAZMAZ; yalnız HTTP üzerinden erişilebilir kılar.

Çalıştır:
    achilles-web                     # veya: uvicorn app.web.server:app
Varsayılan: http://127.0.0.1:8765 (yalnız localhost).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import configure_logging, get_settings
from app.web import security
from app.web.schemas import (
    AskRequest,
    AskResponse,
    BacktestRequest,
    BacktestResponse,
    CardResponse,
    IngestResponse,
    PaperOut,
    SourceOut,
    StatusResponse,
)

logger = logging.getLogger(__name__)

_STATIC_DIR = Path(__file__).resolve().parent / "static"
_settings = get_settings()


@asynccontextmanager
async def _lifespan(app: FastAPI):
    configure_logging()
    get_settings().ensure_dirs()
    logger.info("Achilles web başladı — host=%s port=%s", _settings.web_host, _settings.web_port)
    yield


app = FastAPI(
    title="Achilles Trader AI",
    description="Yerel-öncelikli trading araştırma sistemi — web arayüzü.",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=_lifespan,
)

_rate_limiter = security.RateLimiter(_settings.rate_limit_per_min)


@app.middleware("http")
async def _security_middleware(request: Request, call_next):
    # Hız sınırı yalnız API yollarına
    if request.url.path.startswith("/api/"):
        try:
            _rate_limiter.check(security.client_ip(request))
        except Exception as exc:  # HTTPException
            from fastapi import HTTPException

            if isinstance(exc, HTTPException):
                resp = JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
                for k, v in security.SECURITY_HEADERS.items():
                    resp.headers[k] = v
                return resp
            raise
    response = await call_next(request)
    for k, v in security.SECURITY_HEADERS.items():
        response.headers.setdefault(k, v)
    return response


# ====================== API ======================
api_auth = Depends(security.require_auth)


@app.get("/api/status", response_model=StatusResponse, dependencies=[api_auth])
def api_status() -> StatusResponse:
    from app.brain.local_llm import LocalLLM
    from app.memory.chroma_store import ChromaStore
    from app.memory.embedding_service import EmbeddingService
    from app.memory.sqlite_store import SqliteStore

    s = get_settings()
    store = SqliteStore()
    emb = EmbeddingService()
    try:
        n_chunks = ChromaStore().count()
    except Exception:
        n_chunks = 0
    return StatusResponse(
        llm_model=s.llm_model,
        ollama_available=LocalLLM().available(),
        embedding_mode=emb.mode,
        n_papers=len(store.list_papers()),
        n_chunks=n_chunks,
        max_upload_mb=s.max_upload_mb,
    )


@app.get("/api/papers", response_model=list[PaperOut], dependencies=[api_auth])
def api_papers() -> list[PaperOut]:
    from app.memory.sqlite_store import SqliteStore

    store = SqliteStore()
    out: list[PaperOut] = []
    for p in store.list_papers():
        out.append(
            PaperOut(
                paper_id=p.paper_id,
                title=p.title,
                year=p.year,
                authors=p.authors,
                n_chunks=len(store.list_chunks(p.paper_id)),
                has_card=store.has_knowledge_card(p.paper_id),
            )
        )
    return out


@app.post("/api/papers/upload", response_model=IngestResponse, dependencies=[api_auth])
async def api_upload(file: UploadFile = File(...)) -> IngestResponse:
    """PDF yükle (katı doğrulama) → kaydet → indeksle."""
    content = await file.read()
    safe_name = security.validate_pdf_upload(file.filename or "", content)

    s = get_settings()
    dest = security.safe_destination(s.raw_pdf_dir, safe_name)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    logger.info("PDF yüklendi: %s (%d bayt)", dest.name, len(content))

    return _ingest_all()


@app.post("/api/ingest", response_model=IngestResponse, dependencies=[api_auth])
def api_ingest() -> IngestResponse:
    """raw_pdf/ içindeki tüm PDF'leri indeksle (idempotent)."""
    return _ingest_all()


def _ingest_all() -> IngestResponse:
    from app.memory.paper_indexer import PaperIndexer

    results = PaperIndexer().ingest_directory()
    ingested = sum(1 for r in results if not r.skipped)
    skipped = sum(1 for r in results if r.skipped)
    papers = [
        PaperOut(paper_id=r.paper_id, title=r.title, n_chunks=r.n_chunks)
        for r in results
        if not r.skipped
    ]
    return IngestResponse(
        ingested=ingested,
        skipped=skipped,
        papers=papers,
        message=f"{ingested} yeni, {skipped} zaten mevcut.",
    )


@app.post("/api/ask", response_model=AskResponse, dependencies=[api_auth])
def api_ask(req: AskRequest) -> AskResponse:
    from app.brain.rag_answerer import RagAnswerer
    from app.memory.embedding_service import EmbeddingService

    ans = RagAnswerer().answer(req.question, top_k=req.top_k)
    sources = [
        SourceOut(
            paper_id=c.paper_id,
            chunk_id=c.chunk_id,
            title=c.title,
            page=c.page_number,
            distance=c.distance,
        )
        for c in ans.sources
    ]
    return AskResponse(
        answer=ans.answer,
        sources=sources,
        llm_used=ans.llm_used,
        embedding_mode=EmbeddingService().mode,
    )


@app.get("/api/card/{paper_id}", response_model=CardResponse, dependencies=[api_auth])
def api_get_card(paper_id: str) -> CardResponse:
    """Kaydedilmiş bilgi kartını getir (LLM gerektirmez). Yoksa 404."""
    from fastapi import HTTPException

    from app.memory.sqlite_store import SqliteStore

    card = SqliteStore().get_latest_knowledge_card(paper_id)
    if card is None:
        raise HTTPException(status_code=404, detail="Bu makale için henüz kart yok.")
    return CardResponse(paper_id=paper_id, card=card, message="ok")


@app.post("/api/card/{paper_id}", response_model=CardResponse, dependencies=[api_auth])
def api_card(paper_id: str) -> CardResponse:
    from fastapi import HTTPException

    from app.brain.knowledge_card_builder import KnowledgeCardBuilder

    # paper_id beyaz-liste: yalnız bilinen makaleler
    from app.memory.sqlite_store import SqliteStore

    known = {p.paper_id for p in SqliteStore().list_papers()}
    if paper_id not in known:
        raise HTTPException(status_code=404, detail="Makale bulunamadı.")

    try:
        card = KnowledgeCardBuilder().build(paper_id)
        return CardResponse(
            paper_id=paper_id,
            card=card.model_dump() if hasattr(card, "model_dump") else dict(card),
            message="Bilgi kartı üretildi.",
        )
    except Exception as exc:
        logger.warning("Kart üretimi başarısız: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Bilgi kartı üretilemedi (LLM gerekli olabilir).",
        ) from exc


@app.post("/api/backtest", response_model=BacktestResponse, dependencies=[api_auth])
def api_backtest(req: BacktestRequest) -> BacktestResponse:
    from fastapi import HTTPException

    from app.trading.backtester import persist_backtest, run_backtest
    from app.trading.evaluator import evaluate as eval_strategy
    from app.trading.market_data_loader import generate_synthetic_ohlcv
    from app.trading.strategy_ir import StrategyIR, example_ir

    # Veri
    if req.use_synthetic:
        df = generate_synthetic_ohlcv(n=req.n_bars, seed=req.seed)
        data_file = f"synthetic(n={req.n_bars},seed={req.seed})"
    else:
        raise HTTPException(
            status_code=400,
            detail="Şimdilik web'den yalnız sentetik veri desteklenir; CSV için CLI kullan.",
        )

    # Strateji IR (güvenli doğrulama; kural çalıştırma YOK, yalnız regex parse)
    if req.strategy_ir:
        try:
            ir = StrategyIR.model_validate(req.strategy_ir)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Geçersiz strateji IR: {exc}") from exc
    else:
        ir = example_ir()

    result = run_backtest(df, ir)
    verdict = eval_strategy(df, ir)
    bt_id = None
    try:
        bt_id = persist_backtest(
            result, data_file, verdict=verdict.verdict, notes="; ".join(verdict.reasons)
        )
    except Exception as exc:
        logger.warning("Backtest kaydı başarısız: %s", exc)

    return BacktestResponse(
        strategy_name=ir.name,
        metrics=result.metrics.to_dict(),
        verdict=verdict.verdict,
        reasons=verdict.reasons,
        backtest_id=bt_id,
        data_source=data_file,
        n_bars=len(df),
    )


@app.post("/api/backtest/csv", response_model=BacktestResponse, dependencies=[api_auth])
async def api_backtest_csv(file: UploadFile = File(...)) -> BacktestResponse:
    """Yüklenen gerçek OHLCV CSV üzerinde backtest (katı doğrulama + look-ahead-safe)."""
    from fastapi import HTTPException

    from app.trading.backtester import persist_backtest, run_backtest
    from app.trading.evaluator import evaluate as eval_strategy
    from app.trading.market_data_loader import load_ohlcv
    from app.trading.strategy_ir import example_ir

    content = await file.read()
    safe_name = security.validate_csv_upload(file.filename or "", content)

    s = get_settings()
    dest = security.safe_destination(s.market_raw_dir, safe_name)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    logger.info("CSV yüklendi: %s (%d bayt)", dest.name, len(content))

    try:
        df = load_ohlcv(dest)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"CSV okunamadı: {exc}") from exc
    if len(df) < 50:
        raise HTTPException(status_code=400, detail="Yetersiz veri (en az ~50 bar gerekli).")

    ir = example_ir()
    result = run_backtest(df, ir)
    verdict = eval_strategy(df, ir)
    bt_id = None
    try:
        bt_id = persist_backtest(
            result, dest.name, verdict=verdict.verdict, notes="; ".join(verdict.reasons)
        )
    except Exception as exc:
        logger.warning("Backtest kaydı başarısız: %s", exc)

    return BacktestResponse(
        strategy_name=ir.name,
        metrics=result.metrics.to_dict(),
        verdict=verdict.verdict,
        reasons=verdict.reasons,
        backtest_id=bt_id,
        data_source=dest.name,
        n_bars=len(df),
    )


# ====================== Statik frontend ======================
# API yollarından SONRA monte edilir.
if _STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(_STATIC_DIR / "assets")), name="assets")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(str(_STATIC_DIR / "index.html"))


def run() -> None:
    """`achilles-web` giriş noktası."""
    import uvicorn

    s = get_settings()
    uvicorn.run(
        "app.web.server:app",
        host=s.web_host,
        port=s.web_port,
        reload=False,
        log_level=s.log_level.lower(),
    )


if __name__ == "__main__":
    run()
