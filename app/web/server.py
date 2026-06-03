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
    AdapterOut,
    AskRequest,
    AskResponse,
    BacktestHistoryResponse,
    BacktestRecord,
    BacktestRequest,
    BacktestResponse,
    BatchCardResponse,
    BatchCardResult,
    CardResponse,
    ChainDatasetResponse,
    ConceptLinkOut,
    DatasetBuildResponse,
    EvalResultRow,
    EvalRunRequest,
    EvalRunResponse,
    EvalSetOut,
    FormulaOut,
    HypothesisBacktestResponse,
    HypothesisResult,
    IngestResponse,
    PaperOut,
    ResearchIterationOut,
    ResearchRequest,
    ResearchRunResponse,
    ResearchSessionOut,
    SourceOut,
    StatusResponse,
    TrainDryRunRequest,
    TrainDryRunResponse,
    TrainingExampleOut,
    TrainingExamplesResponse,
    TrainingStatusResponse,
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
