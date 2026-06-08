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
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app.config import configure_logging, get_settings
from app.web import security
from app.web.schemas import (
    AdapterOut,
    ApproveCardResponse,
    ApprovedCardsResponse,
    ArxivEntryOut,
    ArxivFetchRequest,
    ArxivFetchResponse,
    ArxivFetchResult,
    ArxivSavedQueryIn,
    ArxivSavedQueryListResponse,
    ArxivSavedQueryOut,
    ArxivSearchResponse,
    AskRequest,
    AskResponse,
    BacktestHistoryResponse,
    BacktestRecord,
    BacktestRequest,
    BacktestResponse,
    BatchCardResponse,
    BatchCardResult,
    CardResponse,
    CardReviewOut,
    ChainDatasetResponse,
    ConceptLinkOut,
    DatasetBuildResponse,
    DrawdownScaleOut,
    EvalResultRow,
    EvalRunRequest,
    EvalRunResponse,
    EvalSetOut,
    FixedRiskOut,
    FormulaOut,
    HypothesisBacktestResponse,
    HypothesisResult,
    IngestResponse,
    KellyOut,
    PackageCodeOut,
    PackageExportResponse,
    PaperOut,
    PendingCardsResponse,
    PineExportResponse,
    ResearchIterationOut,
    ResearchRequest,
    ResearchRunResponse,
    ResearchSessionOut,
    RiskReportListResponse,
    RiskReportRecord,
    RiskReportResponse,
    SourceOut,
    StatusResponse,
    TrainDryRunRequest,
    TrainDryRunResponse,
    TrainingExampleOut,
    TrainingExamplesResponse,
    TrainingStartRequest,
    TrainingStartResponse,
    TrainingStatusResponse,
)

logger = logging.getLogger(__name__)

_STATIC_DIR = Path(__file__).resolve().parent / "static"
_settings = get_settings()


@asynccontextmanager
async def _lifespan(app: FastAPI):
    import asyncio as _asyncio
    configure_logging()
    get_settings().ensure_dirs()
    logger.info("Achilles web başladı — host=%s port=%s", _settings.web_host, _settings.web_port)
    from app.lora.auto_pipeline import get_auto_pipeline
    _bg_task = _asyncio.create_task(get_auto_pipeline().background_loop())
    _bg_task.add_done_callback(lambda _t: None)
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

    adapter_used: str | None = None

    if req.adapter_version:
        # MLX adapter ile yanıtla (Ollama bypass)
        from app.brain.mlx_llm import MlxLLM, MlxLLMUnavailable
        from app.memory.retrieval_service import RetrievalService
        from app.training.adapter_registry import AdapterRegistry

        entry = AdapterRegistry().get(req.adapter_version)
        if entry is None:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=404, detail=f"Adapter bulunamadı: {req.adapter_version}"
            )

        mlx = MlxLLM(base_model=entry["base_model"], adapter_path=entry["adapter_path"])
        retriever = RetrievalService()
        chunks = retriever.retrieve(req.question, top_k=req.top_k)
        context = "\n\n".join(c.text[:600] for c in chunks) if chunks else "(kaynak yok)"
        prompt = (
            f"Aşağıdaki akademik bağlamı kullanarak soruyu yanıtla.\n\n"
            f"BAĞLAM:\n{context}\n\n"
            f"SORU: {req.question}\n\nYANIT:"
        )
        try:
            answer = mlx.generate(prompt)
            llm_used = True
            adapter_used = req.adapter_version
        except MlxLLMUnavailable as exc:
            answer = f"[MLX adapter kullanılamadı: {exc}]"
            llm_used = False

        sources = [
            SourceOut(
                paper_id=c.paper_id,
                chunk_id=c.chunk_id,
                title=c.title,
                page=c.page_number,
                distance=c.distance,
            )
            for c in chunks
        ]
        return AskResponse(
            answer=answer,
            sources=sources,
            llm_used=llm_used,
            embedding_mode=EmbeddingService().mode,
            adapter_used=adapter_used,
        )

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


@app.post("/api/cards/batch", response_model=BatchCardResponse, dependencies=[api_auth])
def api_cards_batch(skip_existing: bool = True) -> BatchCardResponse:
    """Kartı olmayan tüm makaleler için sırayla bilgi kartı üret (LLM gerekli)."""
    from app.brain.knowledge_card_builder import KnowledgeCardBuilder
    from app.memory.sqlite_store import SqliteStore

    store = SqliteStore()
    papers = store.list_papers()
    builder = KnowledgeCardBuilder()
    results: list[BatchCardResult] = []

    for paper in papers:
        pid = paper.paper_id
        if skip_existing and store.has_knowledge_card(pid):
            results.append(
                BatchCardResult(paper_id=pid, title=paper.title, status="skip", message="zaten var")
            )
            continue
        try:
            builder.build(pid)
            results.append(
                BatchCardResult(paper_id=pid, title=paper.title, status="ok", message="üretildi")
            )
        except Exception as exc:
            logger.warning("Toplu kart — %s başarısız: %s", pid, exc)
            results.append(
                BatchCardResult(
                    paper_id=pid, title=paper.title, status="error", message=str(exc)[:120]
                )
            )

    produced = sum(1 for r in results if r.status == "ok")
    skipped = sum(1 for r in results if r.status == "skip")
    errors = sum(1 for r in results if r.status == "error")
    return BatchCardResponse(produced=produced, skipped=skipped, errors=errors, results=results)


@app.post(
    "/api/card/{paper_id}/backtest",
    response_model=HypothesisBacktestResponse,
    dependencies=[api_auth],
)
def api_card_backtest(paper_id: str) -> HypothesisBacktestResponse:
    """Bilgi kartındaki strateji hipotezlerini sentetik veride backtest et."""
    from fastapi import HTTPException

    from app.memory.sqlite_store import SqliteStore
    from app.trading.backtester import run_backtest
    from app.trading.evaluator import evaluate as eval_strategy
    from app.trading.market_data_loader import generate_synthetic_ohlcv
    from app.trading.strategy_generator import generate_from_hypothesis

    card = SqliteStore().get_latest_knowledge_card(paper_id)
    if card is None:
        raise HTTPException(status_code=404, detail="Bu makale için henüz kart yok.")

    hypotheses: list[str] = card.get("possible_strategy_hypotheses") or []
    if not hypotheses:
        raise HTTPException(status_code=422, detail="Kart test edilebilir hipotez içermiyor.")

    df = generate_synthetic_ohlcv(n=2000, seed=42)
    results: list[HypothesisResult] = []
    for i, hyp in enumerate(hypotheses):
        ir = generate_from_hypothesis(hyp, name=f"hyp_{i + 1}", market="XAUUSD", timeframe="15m")
        bt = run_backtest(df, ir)
        ev = eval_strategy(df, ir)
        results.append(
            HypothesisResult(
                hypothesis=hyp,
                strategy_name=ir.name,
                verdict=ev.verdict,
                reasons=ev.reasons,
                metrics=bt.metrics.to_dict(),
            )
        )

    return HypothesisBacktestResponse(
        paper_id=paper_id,
        n_hypotheses=len(results),
        results=results,
    )


# ---------- Araştırma (Trader Beyin) ----------
@app.get("/api/research/formulas", response_model=list[FormulaOut], dependencies=[api_auth])
def api_formulas(paper_id: str | None = None) -> list[FormulaOut]:
    """Çıkarılmış formülleri listele."""
    from app.memory.sqlite_store import SqliteStore

    rows = SqliteStore().list_formulas(paper_id=paper_id)
    return [FormulaOut(**r) for r in rows]


@app.get("/api/research/graph", response_model=list[ConceptLinkOut], dependencies=[api_auth])
def api_concept_graph() -> list[ConceptLinkOut]:
    """Kavram grafiği bağlantılarını listele."""
    from app.memory.sqlite_store import SqliteStore

    rows = SqliteStore().list_concept_links()
    return [ConceptLinkOut(**r) for r in rows]


@app.post("/api/research/extract", dependencies=[api_auth])
def api_extract_formulas(paper_id: str | None = None) -> dict:
    """PDF'lerden formül çıkar ve kavram grafiği oluştur (LLM gerekli)."""
    from app.research.concept_graph import ConceptGraph
    from app.research.formula_extractor import FormulaExtractor

    extractor = FormulaExtractor()
    if paper_id:
        formulas = extractor.extract_from_paper(paper_id)
        n_formulas = len(formulas)
    else:
        results = extractor.extract_from_all_papers()
        n_formulas = sum(len(v) for v in results.values())

    n_links = ConceptGraph().build_from_papers()
    return {
        "n_formulas": n_formulas,
        "n_links": n_links,
        "message": f"{n_formulas} formül, {n_links} bağlantı",
    }


@app.post("/api/research/run", response_model=ResearchRunResponse, dependencies=[api_auth])
def api_research_run(req: ResearchRequest) -> ResearchRunResponse:
    """Agentic araştırma döngüsü: sentezle → backtest → yansıt → iyileştir."""
    from app.research.orchestrator import ResearchOrchestrator

    orchestrator = ResearchOrchestrator(max_iterations=req.max_iterations)
    result = orchestrator.run(req.question, paper_ids=req.paper_ids)

    return ResearchRunResponse(
        question=result.question,
        iterations=[
            ResearchIterationOut(
                session_id=it.session_id,
                iteration=it.iteration,
                indicator_name=it.indicator_name,
                verdict=it.verdict,
                reasons=it.reasons,
                metrics=it.metrics,
                reflection=it.reflection,
                improvement_notes=it.improvement_notes,
            )
            for it in result.iterations
        ],
        final_verdict=result.final_verdict,
        best_session_id=result.best_session_id,
        summary=result.summary(),
    )


@app.get("/api/research/sessions", response_model=list[ResearchSessionOut], dependencies=[api_auth])
def api_research_sessions(limit: int = 30) -> list[ResearchSessionOut]:
    """Kayıtlı araştırma oturumlarını listele."""
    from app.memory.sqlite_store import SqliteStore

    rows = SqliteStore().list_research_sessions(limit=min(limit, 200))
    out: list[ResearchSessionOut] = []
    for r in rows:
        ind = r.get("proposed_indicator") or {}
        out.append(
            ResearchSessionOut(
                session_id=r["session_id"],
                question=r["question"],
                iteration=r["iteration"],
                verdict=r.get("verdict"),
                indicator_name=ind.get("indicator_name") if ind else None,
                status=r["status"],
                created_at=r["created_at"],
            )
        )
    return out


@app.post(
    "/api/research/chain-dataset", response_model=ChainDatasetResponse, dependencies=[api_auth]
)
def api_chain_dataset(only_successful: bool = False) -> ChainDatasetResponse:
    """Araştırma zincirlerinden LoRA eğitim verisi üret."""
    from app.research.chain_data_builder import ChainDataBuilder

    result = ChainDataBuilder().build(only_successful=only_successful)
    return ChainDatasetResponse(**result)


# ---------- Eğitim ----------
@app.get("/api/eval/sets", response_model=list[EvalSetOut], dependencies=[api_auth])
def api_eval_sets() -> list[EvalSetOut]:
    """Kullanılabilir eval set listesi (evals/ dizini)."""

    evals_dir = get_settings().root / "evals"
    out: list[EvalSetOut] = []
    if evals_dir.exists():
        for p in sorted(evals_dir.glob("*.jsonl")):
            try:
                n = sum(1 for line in p.read_text(encoding="utf-8").splitlines() if line.strip())
            except Exception:
                n = 0
            out.append(EvalSetOut(name=p.stem, path=str(p), n_items=n))
    return out


@app.post("/api/eval/run", response_model=EvalRunResponse, dependencies=[api_auth])
def api_eval_run(req: EvalRunRequest) -> EvalRunResponse:
    """Seçili eval setini çalıştır (Ollama gerekli, ~dakikalar sürebilir)."""
    from fastapi import HTTPException

    from app.training.evaluate_model import ModelEvaluator

    evals_dir = get_settings().root / "evals"
    eval_path = evals_dir / f"{req.eval_set}.jsonl"
    if not eval_path.exists():
        raise HTTPException(status_code=404, detail=f"Eval seti bulunamadı: {req.eval_set}")

    evaluator = ModelEvaluator()
    try:
        results = evaluator.run_eval(eval_path, adapter_version=req.adapter_version)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Eval çalıştırılamadı: {exc}") from exc

    return EvalRunResponse(
        eval_set=results["eval_set"],
        model=results["model"],
        adapter_version=results.get("adapter_version"),
        score=results["score"],
        n_items=results["n_items"],
        total_flags=results["total_flags"],
        rows=[
            EvalResultRow(question=r["q"], answer=r["a"], flags=r["flags"])
            for r in results.get("rows", [])
        ],
    )


@app.get("/api/training/status", response_model=TrainingStatusResponse, dependencies=[api_auth])
def api_training_status() -> TrainingStatusResponse:
    """Eğitim örneği sayısı + kayıtlı adapter listesi."""
    from sqlalchemy import func, select

    from app.memory.sqlite_store import SqliteStore, TrainingExample
    from app.training.adapter_registry import AdapterRegistry

    store = SqliteStore()
    with store.session() as s:
        n = s.scalar(select(func.count()).select_from(TrainingExample)) or 0
    adapters = AdapterRegistry(store).list_all()
    return TrainingStatusResponse(
        n_examples=n,
        adapters=[AdapterOut(**a) for a in adapters],
    )


@app.post("/api/training/dataset", response_model=DatasetBuildResponse, dependencies=[api_auth])
def api_training_dataset() -> DatasetBuildResponse:
    """DatasetBuilder ile train/valid JSONL oluştur."""
    from app.training.dataset_builder import DatasetBuilder

    r = DatasetBuilder().build()
    return DatasetBuildResponse(
        n_train=r.n_train,
        n_valid=r.n_valid,
        content_hash=r.content_hash,
        message=f"{r.n_train} eğitim + {r.n_valid} doğrulama kaydı yazıldı.",
    )


@app.get("/api/backtests", response_model=BacktestHistoryResponse, dependencies=[api_auth])
def api_backtest_history(limit: int = 50) -> BacktestHistoryResponse:
    """Son backtest kayıtlarını listele (yeni → eski)."""
    from app.memory.sqlite_store import SqliteStore

    rows = SqliteStore().list_backtests(limit=min(limit, 200))
    return BacktestHistoryResponse(
        records=[BacktestRecord(**r) for r in rows],
        total=len(rows),
    )


@app.get("/api/training/examples", response_model=TrainingExamplesResponse, dependencies=[api_auth])
def api_training_examples(limit: int = 100) -> TrainingExamplesResponse:
    """Kayıtlı eğitim örneklerini listele."""
    from app.memory.sqlite_store import SqliteStore

    rows = SqliteStore().list_training_examples(limit=min(limit, 500))
    return TrainingExamplesResponse(
        examples=[TrainingExampleOut(**r) for r in rows],
        total=len(rows),
    )


@app.delete("/api/training/examples/{example_id}", dependencies=[api_auth])
def api_delete_training_example(example_id: str) -> dict:
    """Eğitim örneğini sil."""
    from fastapi import HTTPException

    from app.memory.sqlite_store import SqliteStore

    if not SqliteStore().delete_training_example(example_id):
        raise HTTPException(status_code=404, detail="Örnek bulunamadı.")
    return {"ok": True}


@app.post("/api/training/dry-run", response_model=TrainDryRunResponse, dependencies=[api_auth])
def api_training_dry_run(req: TrainDryRunRequest) -> TrainDryRunResponse:
    """Eğitim komutunu oluştur (çalıştırmaz — CLI'da --run ile başlatılır)."""
    import datetime as dt

    from app.config import get_settings
    from app.training.dataset_builder import DatasetBuilder
    from app.training.mlx_lora_train import TrainConfig, build_command

    r = DatasetBuilder().build()
    s = get_settings()
    ts = dt.datetime.now(dt.UTC).strftime("%Y%m%d_%H%M%S")
    cfg = TrainConfig(
        base_model=req.base_model,
        train_jsonl=r.train_path,
        valid_jsonl=r.valid_path,
        adapter_output_path=s.adapters_dir / f"adapter_{ts}",
        iterations=req.iterations,
        batch_size=req.batch_size,
        learning_rate=req.learning_rate,
        num_layers=req.num_layers,
    )
    return TrainDryRunResponse(
        command=" ".join(build_command(cfg)),
        n_train=r.n_train,
        n_valid=r.n_valid,
        content_hash=r.content_hash,
        message="Dry-run: gerçek eğitim için terminalden --run ile çalıştırın.",
    )


@app.post("/api/training/run", response_model=TrainingStartResponse, dependencies=[api_auth])
def api_training_run(req: TrainingStartRequest) -> TrainingStartResponse:
    """Gerçek LoRA eğitimini başlat (subprocess, SSE ile izle)."""
    import datetime as dt

    from app.config import get_settings
    from app.training.dataset_builder import DatasetBuilder
    from app.training.mlx_lora_train import TrainConfig, build_command
    from app.web.training_manager import get_training_manager

    mgr = get_training_manager()
    if mgr.progress.state.value == "running":
        return TrainingStartResponse(ok=False, message="Zaten eğitim çalışıyor.")

    r = DatasetBuilder().build()
    if r.n_train == 0:
        return TrainingStartResponse(ok=False, message="Eğitim verisi yok — önce dataset oluştur.")

    s = get_settings()
    ts = dt.datetime.now(dt.UTC).strftime("%Y%m%d_%H%M%S")
    adapter_name = f"{req.adapter_name}_{ts}"
    cfg = TrainConfig(
        base_model=req.base_model,
        train_jsonl=r.train_path,
        valid_jsonl=r.valid_path,
        adapter_output_path=s.adapters_dir / adapter_name,
        iterations=req.iterations,
        batch_size=req.batch_size,
        learning_rate=req.learning_rate,
        num_layers=req.num_layers,
    )
    cmd = build_command(cfg)
    mgr.start(cmd, adapter_name=adapter_name, total_iters=req.iterations)
    return TrainingStartResponse(
        ok=True, message=f"Eğitim başladı: {adapter_name} ({r.n_train} örnek)"
    )


@app.post("/api/training/stop", dependencies=[api_auth])
def api_training_stop() -> dict:
    from app.web.training_manager import get_training_manager

    get_training_manager().stop()
    return {"ok": True}


@app.get("/api/training/progress")
def api_training_progress() -> dict:
    from app.web.training_manager import get_training_manager

    return get_training_manager().progress.to_dict()


@app.get("/api/training/stream")
async def api_training_stream(request: Request) -> Response:
    import json

    from fastapi.responses import StreamingResponse

    from app.web.training_manager import get_training_manager

    mgr = get_training_manager()

    async def event_gen():
        async for msg in mgr.subscribe():
            if await request.is_disconnected():
                break
            yield f"data: {json.dumps(msg)}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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


# ---------- kart onay ----------
@app.get("/api/cards/pending", response_model=PendingCardsResponse, dependencies=[api_auth])
def api_cards_pending() -> PendingCardsResponse:
    """review_status=pending olan kartları listele."""
    from app.memory.sqlite_store import SqliteStore

    store = SqliteStore()
    cards = store.list_pending_cards()
    out = []
    for c in cards:
        card_data = c.get("card_json") or {}
        out.append(
            CardReviewOut(
                card_id=c["card_id"],
                paper_id=c["paper_id"],
                model=c["model"],
                trust_level=c["trust_level"],
                review_status=c["review_status"],
                lora_eligible=c["lora_eligible"],
                difficulty=c["difficulty"],
                stage=c["stage"],
                created_at=c["created_at"],
                title=card_data.get("title"),
                main_claim=card_data.get("main_claim", ""),
            )
        )
    return PendingCardsResponse(cards=out, total=len(out))


@app.post(
    "/api/card/{card_id}/approve", response_model=ApproveCardResponse, dependencies=[api_auth]
)
def api_approve_card(card_id: str) -> ApproveCardResponse:
    """Kartı onayla: review_status=approved, lora_eligible=1."""
    from app.memory.sqlite_store import SqliteStore

    ok = SqliteStore().approve_card(card_id)
    if not ok:
        return ApproveCardResponse(card_id=card_id, status="not_found", message="Kart bulunamadı")
    return ApproveCardResponse(
        card_id=card_id, status="approved", message="Kart onaylandı, LoRA'ya girilebilir"
    )


@app.post("/api/card/{card_id}/reject", response_model=ApproveCardResponse, dependencies=[api_auth])
def api_reject_card(card_id: str) -> ApproveCardResponse:
    """Kartı reddet: review_status=rejected, lora_eligible=0."""
    from app.memory.sqlite_store import SqliteStore

    ok = SqliteStore().reject_card(card_id)
    if not ok:
        return ApproveCardResponse(card_id=card_id, status="not_found", message="Kart bulunamadı")
    return ApproveCardResponse(card_id=card_id, status="rejected", message="Kart reddedildi")


@app.get("/api/cards/approved", response_model=ApprovedCardsResponse, dependencies=[api_auth])
def api_cards_approved(
    difficulty_min: float = 0.0,
    difficulty_max: float = 1.0,
) -> ApprovedCardsResponse:
    """Onaylı kartları döndür (opsiyonel difficulty filtresi)."""
    from app.memory.sqlite_store import SqliteStore

    store = SqliteStore()
    cards = store.list_approved_cards(difficulty_min=difficulty_min, difficulty_max=difficulty_max)
    out = []
    for c in cards:
        card_data = c.get("card_json") or {}
        out.append(
            CardReviewOut(
                card_id=c["card_id"],
                paper_id=c["paper_id"],
                model=c["model"],
                trust_level=c["trust_level"],
                review_status=c["review_status"],
                lora_eligible=c["lora_eligible"],
                difficulty=c["difficulty"],
                stage=c["stage"],
                created_at=c["created_at"],
                title=card_data.get("title"),
                main_claim=card_data.get("main_claim", ""),
            )
        )
    return ApprovedCardsResponse(
        cards=out,
        total=len(out),
        difficulty_min=difficulty_min,
        difficulty_max=difficulty_max,
    )


# ---------- Risk manager ----------
@app.get(
    "/api/backtest/{backtest_id}/risk",
    response_model=RiskReportResponse,
    dependencies=[api_auth],
)
def api_backtest_risk(
    backtest_id: str,
    equity_usd: float = 10_000.0,
    max_dd_pct: float = -20.0,
    risk_pct: float = 1.0,
    stop_pct: float = 2.0,
) -> RiskReportResponse:
    """Backtest ID için Kelly + drawdown ölçekleme + sabit risk raporu üret."""
    from fastapi import HTTPException
    from sqlalchemy import select

    from app.memory.sqlite_store import Backtest, SqliteStore, Strategy
    from app.trading.backtester import _compute_columns, _position_series
    from app.trading.market_data_loader import generate_synthetic_ohlcv
    from app.trading.risk_manager import analyze_risk
    from app.trading.strategy_ir import StrategyIR

    store = SqliteStore()
    with store.session() as s:
        bt = s.scalars(select(Backtest).where(Backtest.backtest_id == backtest_id)).first()
        if bt is None:
            raise HTTPException(status_code=404, detail=f"Backtest bulunamadı: {backtest_id}")
        strat = s.get(Strategy, bt.strategy_id)
        if strat is None:
            raise HTTPException(status_code=404, detail="Strateji bulunamadı.")
        ir = StrategyIR.model_validate_json(strat.ir_json)

    # Sentetik veriyle risk hesabı (gerçek CSV saklanmıyor, senkron hesaplama)
    df = generate_synthetic_ohlcv(n=2000, seed=42)
    enriched = _compute_columns(df, ir)
    position = _position_series(enriched, ir)
    bar_ret = enriched["close"].pct_change().fillna(0.0)
    net_ret = position.shift(1).fillna(0.0) * bar_ret
    equity_curve = (1 + net_ret).cumprod()

    report = analyze_risk(
        strategy_name=ir.name,
        equity_curve=equity_curve,
        position=position,
        returns=net_ret,
        equity_usd=equity_usd,
        max_dd_threshold_pct=max_dd_pct,
        risk_per_trade_pct=risk_pct,
        atr_stop_pct=stop_pct,
    )

    d = report.to_dict()
    report_id = f"rr_{backtest_id}"
    store.save_risk_report(report_id=report_id, backtest_id=backtest_id, report_dict=d)
    return RiskReportResponse(
        strategy_name=d["strategy_name"],
        n_trades=d["n_trades"],
        kelly=KellyOut(**d["kelly"]),
        drawdown_scale=DrawdownScaleOut(**d["drawdown_scale"]),
        fixed_risk=FixedRiskOut(**d["fixed_risk"]),
        warnings=d["warnings"],
        recommendation=d["recommendation"],
        report_id=report_id,
    )


# ---------- Risk raporu listesi ----------
@app.get(
    "/api/risk-reports",
    response_model=RiskReportListResponse,
    dependencies=[api_auth],
)
def api_list_risk_reports(limit: int = 50) -> RiskReportListResponse:
    """Kaydedilmiş risk raporlarını yeni→eski sırasıyla listele."""
    from app.memory.sqlite_store import SqliteStore

    store = SqliteStore()
    rows = store.list_risk_reports(limit=limit)
    records = [RiskReportRecord(**r) for r in rows]
    return RiskReportListResponse(reports=records, total=len(records))


# ---------- Pine Script export (backtest → TradingView) ----------
@app.get(
    "/api/backtest/{backtest_id}/pine",
    response_model=PineExportResponse,
    dependencies=[api_auth],
)
def api_backtest_pine(backtest_id: str) -> PineExportResponse:
    """Backtest ID'ye ait StrategyIR'i Pine Script v5'e çevir (TradingView köprüsü için)."""
    from fastapi import HTTPException
    from sqlalchemy import select

    from app.memory.sqlite_store import Backtest, SqliteStore, Strategy
    from app.trading.strategy_ir import StrategyIR

    store = SqliteStore()
    with store.session() as s:
        bt = s.scalars(select(Backtest).where(Backtest.backtest_id == backtest_id)).first()
        if bt is None:
            raise HTTPException(status_code=404, detail=f"Backtest bulunamadı: {backtest_id}")
        strat = s.get(Strategy, bt.strategy_id)
        if strat is None:
            raise HTTPException(status_code=404, detail="Bu backtest'e ait strateji bulunamadı.")
        ir = StrategyIR.model_validate_json(strat.ir_json)

    return PineExportResponse(
        backtest_id=backtest_id,
        strategy_name=ir.name,
        market=ir.market,
        timeframe=ir.timeframe,
        pine_code=ir.to_pine(),
    )


# ---------- arXiv makale arama ve indirme ----------
@app.get("/api/learning/summary")
def api_learning_summary() -> dict:
    """Makale / chunk / kart istatistikleri — dashboard özeti."""
    from sqlalchemy import func
    from sqlalchemy import select as _sel

    from app.memory.sqlite_store import Chunk, KnowledgeCard, SqliteStore
    store = SqliteStore()
    papers = store.list_papers()
    approved = store.list_approved_cards()
    with store.session() as s:
        n_chunks = s.scalar(_sel(func.count()).select_from(Chunk)) or 0
        n_pending = s.scalar(
            _sel(func.count()).select_from(KnowledgeCard)
            .where(KnowledgeCard.review_status == "pending")
        ) or 0
    return {
        "n_papers": len(papers),
        "n_chunks": n_chunks,
        "n_approved_cards": len(approved),
        "n_pending_cards": n_pending,
    }


@app.get("/api/learning/eval-history")
def api_learning_eval_history() -> dict:
    """Tüm adapter versiyonlarının eval skor geçmişi."""
    from app.memory.sqlite_store import SqliteStore
    rows = SqliteStore().list_eval_history()
    return {"rows": rows}


@app.get("/api/learning/training-runs")
def api_learning_training_runs() -> dict:
    """Kayıtlı loss curve JSON dosyalarını listele."""
    import json as _json
    runs = []
    for f in sorted(Path("reports/training").glob("*_loss.json")):
        try:
            data = _json.loads(f.read_text())
            runs.append({
                "adapter_name": data.get("adapter_name", f.stem),
                "started_at": data.get("started_at", ""),
                "finished_at": data.get("finished_at", ""),
                "total_iters": data.get("total_iters", 0),
                "final_train_loss": data["curve"][-1]["train_loss"] if data.get("curve") else None,
                "final_val_loss": data["curve"][-1].get("val_loss") if data.get("curve") else None,
                "curve": data.get("curve", []),
            })
        except Exception:
            pass
    return {"runs": runs}


@app.get("/api/learning/card-growth")
def api_learning_card_growth() -> dict:
    """Günlük onaylı kart büyüme verisi."""
    from app.memory.sqlite_store import SqliteStore
    rows = SqliteStore().list_card_growth()
    return {"rows": rows}


@app.get("/api/profile")
def api_hardware_profile() -> dict:
    """Donanım profili döndürür (auth gerekmez — kurulum popup için)."""
    from app.agents.system_profiler.profiler import collect

    p = collect()
    return {
        "os": p.os,
        "arch": p.arch,
        "cpu": p.cpu.name,
        "cores": p.cpu.cores,
        "ram_gb": round(p.memory.ram_total_gb, 1),
        "gpu": p.gpu.name,
        "gpu_vendor": p.gpu.vendor,
        "metal": p.gpu.metal,
        "cuda": p.gpu.cuda,
        "lora_supported": p.os == "macOS" and p.arch == "arm64",
    }


@app.get("/api/recommend")
def api_model_recommend() -> dict:
    """RAM'e göre önerilen Ollama modellerini döndürür (auth gerekmez)."""
    from app.agents.model_advisor.advisor import recommend
    from app.agents.system_profiler.profiler import collect

    profile = collect()
    result = recommend(profile, task="general", top_k=3)
    recommended = [
        {
            "rank": r.rank,
            "name": r.display_name,
            "ollama": r.ollama_name,
            "confidence": round(r.confidence * 100),
            "reasons": r.reasons[:2],
        }
        for r in result.recommended
    ]
    rejected = [{"name": r.display_name, "reason": r.reason} for r in result.rejected[:3]]
    return {"recommended": recommended, "rejected": rejected}


@app.get("/api/auto-lora/status")
async def api_auto_lora_status() -> dict:
    """Auto-LoRA pipeline durumu."""
    from app.lora.auto_pipeline import get_auto_pipeline
    return get_auto_pipeline().get_status()


@app.post("/api/auto-lora/enable")
async def api_auto_lora_enable(enabled: bool = True) -> dict:
    """Otomatik periyodik kontrolü aç/kapat."""
    from app.lora.auto_pipeline import get_auto_pipeline
    get_auto_pipeline().set_enabled(enabled)
    return {"ok": True, "auto_enabled": enabled}


@app.post("/api/auto-lora/check")
async def api_auto_lora_check() -> dict:
    """Gate 0-8 kontrolünü manuel tetikle."""
    from app.lora.auto_pipeline import get_auto_pipeline
    return await get_auto_pipeline().check_and_prepare()


@app.post("/api/auto-lora/train")
async def api_auto_lora_train(adapter_name: str, iters: int = 300) -> dict:
    """Kullanıcı onayıyla eğitimi başlat (READY_TO_TRAIN durumu gerekir)."""
    from app.lora.auto_pipeline import get_auto_pipeline
    return await get_auto_pipeline().start_training(adapter_name, iters)


@app.post("/api/auto-lora/promote")
async def api_auto_lora_promote() -> dict:
    """Kullanıcı onayıyla adapter'ı production'a terfi et (EVAL_PASSED gerekir)."""
    from app.lora.auto_pipeline import get_auto_pipeline
    return await get_auto_pipeline().promote_to_production()


@app.post("/api/auto-lora/reset")
async def api_auto_lora_reset() -> dict:
    """Pipeline'ı IDLE'a sıfırla."""
    from app.lora.auto_pipeline import get_auto_pipeline
    await get_auto_pipeline().reset()
    return {"ok": True}


@app.get("/api/arxiv/search", response_model=ArxivSearchResponse, dependencies=[api_auth])
def api_arxiv_search(q: str, max_results: int = 10) -> ArxivSearchResponse:
    """arXiv'de ara (indirme yok)."""
    from app.ingestion.arxiv_fetcher import search_arxiv

    n = max(1, min(max_results, 50))
    entries = search_arxiv(q, max_results=n)
    return ArxivSearchResponse(
        query=q,
        results=[
            ArxivEntryOut(
                arxiv_id=e.arxiv_id,
                title=e.title,
                authors=e.authors,
                abstract=e.abstract[:400],
                pdf_url=e.pdf_url,
                published=e.published,
            )
            for e in entries
        ],
        total=len(entries),
    )


@app.post("/api/arxiv/fetch", response_model=ArxivFetchResponse, dependencies=[api_auth])
def api_arxiv_fetch(req: ArxivFetchRequest) -> ArxivFetchResponse:
    """arXiv'de ara → PDF'leri indir → (opsiyonel) otomatik indeksle."""
    from app.ingestion.arxiv_fetcher import fetch_arxiv_papers

    fetch_results = fetch_arxiv_papers(req.query, max_results=req.max_results)
    downloaded = [r for r in fetch_results if not r.skipped]
    skipped_count = sum(1 for r in fetch_results if r.skipped)

    ingested = 0
    if req.auto_ingest and downloaded:
        from app.memory.paper_indexer import PaperIndexer

        ingest_res = PaperIndexer().ingest_directory()
        ingested = sum(1 for r in ingest_res if not r.skipped)

    return ArxivFetchResponse(
        query=req.query,
        fetched=len(downloaded),
        skipped=skipped_count,
        results=[
            ArxivFetchResult(arxiv_id=r.arxiv_id, title=r.title, skipped=r.skipped)
            for r in fetch_results
        ],
        ingested=ingested,
        message=(
            f"{len(downloaded)} PDF indirildi, {skipped_count} atlandı"
            + (f", {ingested} indekslendi" if req.auto_ingest else "")
            + "."
        ),
    )


# ---------- arXiv kayıtlı sorgu kütüphanesi ----------
@app.post("/api/arxiv/queries", response_model=ArxivSavedQueryOut, dependencies=[api_auth])
def api_save_arxiv_query(req: ArxivSavedQueryIn) -> ArxivSavedQueryOut:
    """Sorguyu kaydet (aynı sorgu tekrar kaydedilirse üzerine yaz)."""
    import hashlib

    from app.memory.sqlite_store import SqliteStore

    store = SqliteStore()
    qid = "aq_" + hashlib.md5(req.query.strip().lower().encode()).hexdigest()[:16]
    store.save_arxiv_query(qid, req.query, req.max_results, req.auto_ingest)
    rows = store.list_arxiv_saved_queries()
    row = next(r for r in rows if r["query_id"] == qid)
    return ArxivSavedQueryOut(**row)


@app.get("/api/arxiv/queries", response_model=ArxivSavedQueryListResponse, dependencies=[api_auth])
def api_list_arxiv_queries() -> ArxivSavedQueryListResponse:
    from app.memory.sqlite_store import SqliteStore

    rows = SqliteStore().list_arxiv_saved_queries()
    return ArxivSavedQueryListResponse(
        queries=[ArxivSavedQueryOut(**r) for r in rows], total=len(rows)
    )


@app.delete("/api/arxiv/queries/{query_id}", dependencies=[api_auth])
def api_delete_arxiv_query(query_id: str) -> dict:
    from fastapi import HTTPException

    from app.memory.sqlite_store import SqliteStore

    if not SqliteStore().delete_arxiv_query(query_id):
        raise HTTPException(status_code=404, detail="Sorgu bulunamadı.")
    return {"ok": True}


@app.post(
    "/api/arxiv/queries/{query_id}/run", response_model=ArxivFetchResponse, dependencies=[api_auth]
)
def api_run_arxiv_query(query_id: str) -> ArxivFetchResponse:
    """Kayıtlı sorguyu çalıştır: arXiv'den çek + indeksle."""
    from fastapi import HTTPException

    from app.ingestion.arxiv_fetcher import fetch_arxiv_papers
    from app.memory.sqlite_store import SqliteStore

    store = SqliteStore()
    rows = store.list_arxiv_saved_queries()
    row = next((r for r in rows if r["query_id"] == query_id), None)
    if row is None:
        raise HTTPException(status_code=404, detail="Sorgu bulunamadı.")
    fetch_results = fetch_arxiv_papers(row["query"], max_results=row["max_results"])
    downloaded = [r for r in fetch_results if not r.skipped]
    skipped_count = len(fetch_results) - len(downloaded)
    ingested = 0
    if row["auto_ingest"] and downloaded:
        from app.ingestion.paper_loader import DiscoveredPaper, compute_file_hash
        from app.memory.paper_indexer import PaperIndexer

        for r in downloaded:
            try:
                disc = DiscoveredPaper(path=r.pdf_path, file_hash=compute_file_hash(r.pdf_path))
                PaperIndexer().ingest_one(disc)
                ingested += 1
            except Exception:
                pass
    store.mark_arxiv_query_ran(query_id)
    return ArxivFetchResponse(
        query=row["query"],
        fetched=len(downloaded),
        skipped=skipped_count,
        results=[
            ArxivFetchResult(arxiv_id=r.arxiv_id, title=r.title, skipped=r.skipped)
            for r in fetch_results
        ],
        ingested=ingested,
        message=f"{len(downloaded)} PDF indirildi, {skipped_count} atlandı"
        + (f", {ingested} indekslendi" if row["auto_ingest"] else "")
        + ".",
    )


# ---------- package export (Entropia) ----------
@app.get(
    "/api/strategy/{strategy_name}/export",
    response_model=PackageExportResponse,
    dependencies=[api_auth],
)
def api_export_package(strategy_name: str) -> PackageExportResponse:
    """StrategyIR → .achpkg formatında Entropia-uyumlu paket döndür."""
    from sqlalchemy import select

    from app.memory.sqlite_store import SqliteStore, Strategy
    from app.trading.package_exporter import export_strategy
    from app.trading.strategy_ir import StrategyIR

    store = SqliteStore()
    with store.session() as s:
        row = s.scalars(select(Strategy).where(Strategy.name == strategy_name)).first()
    if row is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=f"Strateji bulunamadı: {strategy_name}")

    ir = StrategyIR.model_validate_json(row.ir_json)
    pkg = export_strategy(ir)
    return PackageExportResponse(
        name=pkg.name,
        version=pkg.version,
        type=pkg.package_type,
        source=pkg.source,
        created_at=pkg.created_at,
        backtest_verdict=pkg.backtest_verdict,
        backtest_metrics=pkg.backtest_metrics,
        code=PackageCodeOut(pine=pkg.pine_code, python=pkg.python_code),
    )


@app.post("/api/package/export", response_model=PackageExportResponse, dependencies=[api_auth])
def api_export_package_from_ir(ir_json: dict) -> PackageExportResponse:
    """Ham StrategyIR JSON'ından .achpkg üret (strateji DB'de kayıtlı olmak zorunda değil)."""
    from app.trading.package_exporter import export_strategy
    from app.trading.strategy_ir import StrategyIR

    ir = StrategyIR.model_validate(ir_json)
    pkg = export_strategy(ir)
    return PackageExportResponse(
        name=pkg.name,
        version=pkg.version,
        type=pkg.package_type,
        source=pkg.source,
        created_at=pkg.created_at,
        backtest_verdict=pkg.backtest_verdict,
        backtest_metrics=pkg.backtest_metrics,
        code=PackageCodeOut(pine=pkg.pine_code, python=pkg.python_code),
    )


# ---------- .achpkg dosya indirme (backtest ID'den) ----------
@app.get(
    "/api/backtest/{backtest_id}/download-pkg",
    dependencies=[api_auth],
)
def api_download_pkg(backtest_id: str) -> Response:
    """Backtest ID'ye ait stratejiyi .achpkg dosyası olarak indir."""
    import re

    from fastapi import HTTPException
    from sqlalchemy import select

    from app.memory.sqlite_store import Backtest, SqliteStore, Strategy
    from app.trading.package_exporter import export_strategy
    from app.trading.strategy_ir import StrategyIR

    store = SqliteStore()
    with store.session() as s:
        bt = s.scalars(select(Backtest).where(Backtest.backtest_id == backtest_id)).first()
        if bt is None:
            raise HTTPException(status_code=404, detail=f"Backtest bulunamadı: {backtest_id}")
        strat = s.get(Strategy, bt.strategy_id)
        if strat is None:
            raise HTTPException(status_code=404, detail="Strateji bulunamadı.")
        ir = StrategyIR.model_validate_json(strat.ir_json)

    pkg = export_strategy(ir, backtest_verdict=bt.verdict)
    safe_name = re.sub(r"[^\w\-]", "_", pkg.name)
    content = pkg.to_json()
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.achpkg"'},
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
