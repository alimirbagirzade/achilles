"""Achilles Trader AI — command line interface.

Run:  uv run achilles --help

Pipeline order (per spec):
  ingest -> ask -> card -> extract-formulas -> research -> dataset -> train -> eval -> backtest
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from app.config import configure_logging, get_settings

app = typer.Typer(
    help="Achilles Trader AI — local-first trading research system.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


@app.callback()
def _root(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    configure_logging("DEBUG" if verbose else None)


# --------------------------------------------------------------------------
# init / status
# --------------------------------------------------------------------------
@app.command()
def init() -> None:
    """Tüm dizinleri ve SQLite şemasını oluştur."""
    from app.memory.sqlite_store import SqliteStore

    settings = get_settings()
    settings.ensure_dirs()
    store = SqliteStore()
    console.print(
        Panel.fit(
            f"[green]Hazır.[/green]\nSQLite: {store.db_path}\nChroma: {settings.chroma_dir}",
            title="achilles init",
        )
    )


@app.command()
def status() -> None:
    """Sistem durumunu göster (model, embedding modu, kayıt sayıları)."""
    from app.brain.local_llm import LocalLLM
    from app.memory.chroma_store import ChromaStore
    from app.memory.embedding_service import EmbeddingService
    from app.memory.sqlite_store import SqliteStore

    settings = get_settings()
    store = SqliteStore()
    papers = store.list_papers()
    llm = LocalLLM()

    t = Table(title="Achilles Trader AI — durum")
    t.add_column("Bileşen")
    t.add_column("Değer")
    t.add_row("LLM modeli", settings.llm_model)
    t.add_row("Ollama erişilebilir", "✅" if llm.available() else "❌ (ollama serve)")
    t.add_row("Embedding modu", EmbeddingService().mode)
    t.add_row("Makale sayısı", str(len(papers)))
    try:
        t.add_row("Chroma chunk sayısı", str(ChromaStore().count()))
    except Exception:
        t.add_row("Chroma chunk sayısı", "0")
    try:
        pending = store.list_pending_cards()
        approved = store.list_approved_cards()
        t.add_row(
            "Bilgi kartları (onay / onaylı)",
            f"[yellow]{len(pending)} bekliyor[/yellow] / [green]{len(approved)} onaylı[/green]",
        )
    except Exception:
        t.add_row("Bilgi kartları", "—")
    console.print(t)


# --------------------------------------------------------------------------
# ingestion
# --------------------------------------------------------------------------
@app.command()
def ingest(
    directory: Path = typer.Option(None, help="PDF klasörü (varsayılan: data/papers/raw_pdf)"),
    force: bool = typer.Option(False, help="Var olan makaleleri yeniden indexle"),
) -> None:
    """PDF'leri oku → chunk → SQLite + ChromaDB."""
    from app.memory.paper_indexer import PaperIndexer

    results = PaperIndexer().ingest_directory(directory, force=force)
    if not results:
        console.print("[yellow]PDF bulunamadı. data/papers/raw_pdf içine PDF koyun.[/yellow]")
        raise typer.Exit()
    t = Table(title="Ingestion sonucu")
    t.add_column("paper_id")
    t.add_column("başlık")
    t.add_column("chunk")
    t.add_column("durum")
    for r in results:
        t.add_row(r.paper_id, (r.title or "?")[:50], str(r.n_chunks), "skip" if r.skipped else "ok")
    console.print(t)


@app.command()
def papers() -> None:
    """Indexlenmiş makaleleri listele."""
    from app.memory.sqlite_store import SqliteStore

    rows = SqliteStore().list_papers()
    t = Table(title="Makaleler")
    t.add_column("paper_id")
    t.add_column("yıl")
    t.add_column("başlık")
    for p in rows:
        t.add_row(p.paper_id, p.year or "?", (p.title or "?")[:60])
    console.print(t)


# --------------------------------------------------------------------------
# RAG
# --------------------------------------------------------------------------
@app.command()
def ask(question: str, top_k: int = typer.Option(None)) -> None:
    """RAG ile kaynaklı cevap üret."""
    from app.brain.rag_answerer import RagAnswerer

    ans = RagAnswerer().answer(question, top_k=top_k)
    console.print(Panel(ans.answer, title=f"Cevap (LLM={'on' if ans.llm_used else 'off'})"))
    if ans.sources:
        t = Table(title="Kaynaklar")
        t.add_column("citation")
        t.add_column("başlık")
        t.add_column("dist")
        for s in ans.sources:
            t.add_row(s.citation, (s.title or "?")[:40], f"{s.distance:.3f}" if s.distance else "?")
        console.print(t)


# --------------------------------------------------------------------------
# knowledge cards / training
# --------------------------------------------------------------------------
@app.command()
def card(paper_id: str) -> None:
    """Bir makaleden knowledge card üret (LLM gerekir)."""
    from app.brain.knowledge_card_builder import KnowledgeCardBuilder

    kc = KnowledgeCardBuilder().build(paper_id)
    console.print_json(json.dumps(kc.model_dump(), ensure_ascii=False))


@app.command("cards")
def cards_cmd(
    action: str = typer.Argument(..., help="pending | approve | reject"),
    card_id: str = typer.Argument("", help="approve/reject için kart ID'si"),
) -> None:
    """Kart onay yönetimi: pending listesi / approve / reject."""
    from app.memory.sqlite_store import SqliteStore

    store = SqliteStore()

    if action == "pending":
        rows = store.list_pending_cards()
        if not rows:
            console.print("[yellow]Onay bekleyen kart yok.[/yellow]")
            return
        t = Table(title="Onay bekleyen kartlar")
        t.add_column("card_id")
        t.add_column("paper_id")
        t.add_column("difficulty")
        t.add_column("stage")
        t.add_column("created_at")
        for r in rows:
            t.add_row(
                r["card_id"][:20],
                r["paper_id"][:20],
                f"{r['difficulty']:.2f}",
                r["stage"] or "—",
                (r["created_at"] or "")[:10],
            )
        console.print(t)

    elif action == "approve":
        if not card_id:
            console.print("[red]approve için card_id gereklidir.[/red]")
            raise typer.Exit(1)
        ok = store.approve_card(card_id)
        if ok:
            console.print(f"[green]Onaylandı:[/green] {card_id}")
        else:
            console.print(f"[red]Kart bulunamadı:[/red] {card_id}")
            raise typer.Exit(1)

    elif action == "reject":
        if not card_id:
            console.print("[red]reject için card_id gereklidir.[/red]")
            raise typer.Exit(1)
        ok = store.reject_card(card_id)
        if ok:
            console.print(f"[yellow]Reddedildi:[/yellow] {card_id}")
        else:
            console.print(f"[red]Kart bulunamadı:[/red] {card_id}")
            raise typer.Exit(1)

    else:
        console.print(f"[red]Bilinmeyen eylem: {action!r}. pending | approve | reject[/red]")
        raise typer.Exit(1)


@app.command()
def dataset(
    phase: int = typer.Option(0, help="1-4: sadece o fazın örnekleri. 0=tümü"),
    all_examples: bool = typer.Option(
        False, "--all", help="lora_eligible filtresi olmadan tümünü al"
    ),
) -> None:
    """Saklanan training örneklerinden train/valid JSONL üret."""
    from app.training.dataset_builder import DatasetBuilder

    res = DatasetBuilder().build(
        phase=phase if phase > 0 else None,
        lora_eligible_only=not all_examples,
    )
    console.print(
        Panel.fit(
            f"train: {res.train_path} ({res.n_train})\n"
            f"valid: {res.valid_path} ({res.n_valid})\n"
            f"hash:  {res.content_hash}",
            title="dataset",
        )
    )


@app.command()
def train(
    base_model: str = typer.Option(None),
    adapter_name: str = typer.Option("achilles_lora_v1"),
    iterations: int = typer.Option(300, help="Eğitim iterasyon sayısı"),
    batch_size: int = typer.Option(2, help="Batch büyüklüğü (8GB için 2 önerilir)"),
    num_layers: int = typer.Option(8, help="LoRA adapter katman sayısı (8GB için 8 önerilir)"),
    run: bool = typer.Option(False, help="Eğitimi gerçekten başlat (Apple Silicon + mlx-lm)"),
) -> None:
    """MLX-LM LoRA eğitim komutunu hazırla (varsayılan dry-run)."""
    from app.training.mlx_lora_train import TrainConfig
    from app.training.mlx_lora_train import main as train_main
    from app.training.mlx_lora_train import run as train_run

    settings = get_settings()
    cfg = TrainConfig(
        base_model=base_model or settings.llm_model,
        train_jsonl=settings.jsonl_dir / "train.jsonl",
        valid_jsonl=settings.jsonl_dir / "valid.jsonl",
        adapter_output_path=settings.adapters_dir / adapter_name,
        iterations=iterations,
        batch_size=batch_size,
        num_layers=num_layers,
    )
    if run:
        train_run(cfg)
    else:
        train_main(
            [
                "--base-model",
                cfg.base_model,
                "--train-jsonl",
                str(cfg.train_jsonl),
                "--valid-jsonl",
                str(cfg.valid_jsonl),
                "--adapter-output-path",
                str(cfg.adapter_output_path),
                "--iterations",
                str(cfg.iterations),
            ]
        )


@app.command()
def evaluate(eval_set: Path, adapter_version: str = typer.Option(None)) -> None:
    """Bir eval seti çalıştır ve hata modlarını işaretle."""
    from app.training.evaluate_model import ModelEvaluator

    res = ModelEvaluator().run_eval(eval_set, adapter_version=adapter_version)
    console.print(
        Panel.fit(
            f"set: {res['eval_set']}\nmodel: {res['model']}\n"
            f"score: {res['score']}\nflags: {res['total_flags']}",
            title="evaluation",
        )
    )


# --------------------------------------------------------------------------
# trading / backtest
# --------------------------------------------------------------------------
@app.command()
def gen_data(
    out: Path = typer.Option(None, help="Çıktı CSV (varsayılan: data/market/raw/synthetic.csv)"),
    n: int = typer.Option(2000),
) -> None:
    """Test için sentetik OHLCV CSV üret."""
    from app.trading.market_data_loader import write_synthetic_csv

    settings = get_settings()
    out = out or (settings.market_raw_dir / "synthetic.csv")
    path = write_synthetic_csv(out, n=n)
    console.print(f"[green]Yazıldı:[/green] {path}")


@app.command()
def backtest(
    data: Path = typer.Argument(..., help="OHLCV CSV yolu"),
    strategy_json: Path = typer.Option(None, help="Strategy IR JSON; yoksa örnek IR kullanılır"),
) -> None:
    """Strategy IR'i bir CSV üzerinde backtest et, evaluator ile yargıla, kaydet."""
    from app.trading.backtester import persist_backtest, run_backtest
    from app.trading.evaluator import evaluate as eval_strategy
    from app.trading.market_data_loader import load_ohlcv
    from app.trading.strategy_ir import StrategyIR, example_ir

    df = load_ohlcv(data)
    ir = (
        StrategyIR.model_validate_json(strategy_json.read_text(encoding="utf-8"))
        if strategy_json
        else example_ir()
    )

    result = run_backtest(df, ir)
    verdict = eval_strategy(df, ir)
    bt_id = persist_backtest(
        result, str(data), verdict=verdict.verdict, notes="; ".join(verdict.reasons)
    )

    m = result.metrics
    t = Table(title=f"Backtest — {ir.name}")
    t.add_column("metrik")
    t.add_column("değer")
    for k, v in m.to_dict().items():
        t.add_row(k, str(v))
    console.print(t)

    color = {"pass": "green", "fail": "red", "inconclusive": "yellow"}.get(verdict.verdict, "white")
    console.print(
        Panel(
            "\n".join(f"- {r}" for r in verdict.reasons),
            title=f"[{color}]YARGI: {verdict.verdict.upper()}[/{color}]  (backtest_id={bt_id})",
        )
    )


# --------------------------------------------------------------------------
# research — trader beyin döngüsü
# --------------------------------------------------------------------------
@app.command("extract-formulas")
def extract_formulas(
    paper_id: str = typer.Argument(None, help="Belirli makale; yoksa tümü"),
    force: bool = typer.Option(False, help="Zaten çıkarılmışları üzerine yaz"),
) -> None:
    """PDF'lerden matematiksel formülleri çıkar ve kavram grafiğini oluştur."""
    from app.research.concept_graph import ConceptGraph
    from app.research.formula_extractor import FormulaExtractor

    extractor = FormulaExtractor()
    graph = ConceptGraph()

    if paper_id:
        formulas = extractor.extract_from_paper(paper_id, force=force)
        console.print(f"[green]{len(formulas)} formül çıkarıldı:[/green] {paper_id}")
    else:
        results = extractor.extract_from_all_papers()
        total = sum(len(v) for v in results.values())
        console.print(f"[green]Toplam {total} formül çıkarıldı ({len(results)} makale)[/green]")

    n_links = graph.build_from_papers()
    console.print(f"[green]Kavram grafiği: {n_links} bağlantı oluşturuldu[/green]")


@app.command()
def formulas(paper_id: str = typer.Argument(None)) -> None:
    """Çıkarılmış formülleri listele."""
    from app.memory.sqlite_store import SqliteStore

    rows = SqliteStore().list_formulas(paper_id=paper_id)
    if not rows:
        console.print("[yellow]Formül bulunamadı — önce 'extract-formulas' çalıştır[/yellow]")
        return
    t = Table(title="Formüller")
    t.add_column("Ad")
    t.add_column("Kategori")
    t.add_column("Açıklama")
    t.add_column("Makale")
    for f in rows:
        t.add_row(
            f["name"],
            f.get("category") or "—",
            (f.get("description") or "")[:60],
            f["paper_id"][:16],
        )
    console.print(t)


@app.command()
def research(
    question: str = typer.Argument(..., help="Araştırma sorusu"),
    iterations: int = typer.Option(3, help="Maksimum iterasyon"),
    paper_ids: str = typer.Option(None, help="Virgülle ayrılmış paper_id listesi (opsiyonel)"),
) -> None:
    """Agentic araştırma döngüsünü çalıştır: sentezle → backtest → yansıt → iyileştir."""
    from app.research.orchestrator import ResearchOrchestrator

    pid_list = [p.strip() for p in paper_ids.split(",")] if paper_ids else None
    orchestrator = ResearchOrchestrator(max_iterations=iterations)
    result = orchestrator.run(question, paper_ids=pid_list)

    color = {"pass": "green", "fail": "red", "inconclusive": "yellow"}.get(
        result.final_verdict, "white"
    )
    console.print(Panel(result.summary(), title=f"[{color}]Araştırma Tamamlandı[/{color}]"))


@app.command("research-sessions")
def research_sessions(limit: int = typer.Option(20)) -> None:
    """Kayıtlı araştırma oturumlarını listele."""
    from app.memory.sqlite_store import SqliteStore

    rows = SqliteStore().list_research_sessions(limit=limit)
    if not rows:
        console.print("[yellow]Oturum bulunamadı — önce 'research' komutunu çalıştır[/yellow]")
        return
    t = Table(title="Araştırma Oturumları")
    t.add_column("ID")
    t.add_column("Soru")
    t.add_column("İter")
    t.add_column("Yargı")
    t.add_column("Tarih")
    for r in rows:
        color = {"pass": "green", "fail": "red"}.get(r.get("verdict", ""), "yellow")
        t.add_row(
            r["session_id"][:16],
            (r["question"] or "")[:50],
            str(r["iteration"]),
            f"[{color}]{r.get('verdict', '—')}[/{color}]",
            (r["created_at"] or "")[:10],
        )
    console.print(t)


@app.command("chain-dataset")
def chain_dataset(only_successful: bool = typer.Option(False)) -> None:
    """Araştırma zincirlerinden LoRA eğitim verisi üret."""
    from app.research.chain_data_builder import ChainDataBuilder

    result = ChainDataBuilder().build(only_successful=only_successful)
    console.print(
        Panel(
            f"kayıt: {result['n_records']}\n"
            f"dosya: {result['output_path']}\n"
            f"hash: {result['content_hash']}",
            title="[green]Zincir veri seti[/green]",
        )
    )


@app.command("pine")
def pine_export(
    strategy_name: str = typer.Argument(default="", help="Strateji adı (boşsa varsayılan örnek)"),
    output: str = typer.Option("", help="Çıktı dosyası (.pine). Boşsa stdout."),
) -> None:
    """StrategyIR → TradingView Pine Script v5 olarak dışa aktar."""
    from app.memory.sqlite_store import SqliteStore
    from app.trading.strategy_ir import StrategyIR, example_ir

    if strategy_name:
        from sqlalchemy import select

        from app.memory.sqlite_store import SqliteStore, Strategy

        store = SqliteStore()
        with store.session() as s:
            row = s.scalars(select(Strategy).where(Strategy.name == strategy_name)).first()
        if not row:
            console.print(f"[red]Strateji bulunamadı: {strategy_name}[/red]")
            raise typer.Exit(1)
        ir = StrategyIR.model_validate_json(row.ir_json)
    else:
        ir = example_ir()

    pine_code = ir.to_pine()

    if output:
        Path(output).write_text(pine_code, encoding="utf-8")
        console.print(f"[green]Kaydedildi:[/green] {output}")
    else:
        console.print(pine_code)


@app.command("export-package")
def export_package(
    strategy_name: str = typer.Argument(
        default="", help="Strateji adı (boşsa varsayılan örnek kullanılır)"
    ),
    output: str = typer.Option("", help="Çıktı dosyası (.achpkg). Boşsa stdout."),
) -> None:
    """StrategyIR → Entropia-uyumlu .achpkg paketi olarak dışa aktar (Pine + Python kodu içerir).

    En son backtest verdict ve metrikleri otomatik olarak pakete eklenir.
    """
    from sqlalchemy import desc, select

    from app.memory.sqlite_store import Backtest, SqliteStore, Strategy
    from app.trading.package_exporter import export_strategy
    from app.trading.strategy_ir import StrategyIR, example_ir

    store = SqliteStore()
    ir: StrategyIR
    strategy_id: str | None = None

    if strategy_name:
        with store.session() as s:
            row = s.scalars(select(Strategy).where(Strategy.name == strategy_name)).first()
        if not row:
            console.print(f"[red]Strateji bulunamadı: {strategy_name}[/red]")
            raise typer.Exit(1)
        ir = StrategyIR.model_validate_json(row.ir_json)
        strategy_id = row.strategy_id
    else:
        ir = example_ir()

    # En son backtest'i otomatik çek
    verdict: str | None = None
    metrics: dict = {}
    if strategy_id:
        with store.session() as s:
            bt = s.scalars(
                select(Backtest)
                .where(Backtest.strategy_id == strategy_id)
                .order_by(desc(Backtest.created_at))
                .limit(1)
            ).first()
        if bt:
            verdict = bt.verdict
            try:
                import json as _json

                metrics = _json.loads(bt.metrics_json or "{}")
            except Exception:
                metrics = {}
            if bt.total_return_pct:
                metrics.setdefault("total_return_pct", bt.total_return_pct)
            if bt.sharpe is not None:
                metrics.setdefault("sharpe", bt.sharpe)
            if bt.max_drawdown_pct is not None:
                metrics.setdefault("max_drawdown_pct", bt.max_drawdown_pct)
            if bt.n_trades:
                metrics.setdefault("n_trades", bt.n_trades)

    pkg = export_strategy(ir, backtest_verdict=verdict, backtest_metrics=metrics)

    if output:
        out_path = Path(output)
        pkg.save(out_path)
        console.print(f"[green]Paket kaydedildi:[/green] {out_path}")
        console.print(f"  İsim    : {pkg.name}")
        console.print(f"  Tip     : {pkg.package_type}")
        color = "green" if verdict == "pass" else "red" if verdict == "fail" else "yellow"
        verdict_str = f"[{color}]{verdict or '—'}[/]"
        console.print(f"  Backtest: {verdict_str}")
        console.print(f"  Boyut   : {len(pkg.to_json())} karakter")
    else:
        console.print(pkg.to_json())


@app.command("risk")
def risk_analyze(
    backtest_id: str = typer.Argument(..., help="Backtest ID (örn. bt_cd00c55600)"),
    equity: float = typer.Option(10_000.0, help="Başlangıç sermayesi ($)"),
    max_dd: float = typer.Option(-20.0, help="Max drawdown eşiği % (örn. -20)"),
    risk_pct: float = typer.Option(1.0, help="İşlem başına risk %"),
    stop_pct: float = typer.Option(2.0, help="Stop mesafesi %"),
) -> None:
    """Bir backtest için Kelly + drawdown ölçekleme + sabit risk raporu üret."""
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
            console.print(f"[red]Backtest bulunamadı: {backtest_id}[/red]")
            raise typer.Exit(1)
        strat = s.get(Strategy, bt.strategy_id)
        if strat is None:
            console.print("[red]Strateji bulunamadı.[/red]")
            raise typer.Exit(1)
        ir = StrategyIR.model_validate_json(strat.ir_json)

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
        equity_usd=equity,
        max_dd_threshold_pct=max_dd,
        risk_per_trade_pct=risk_pct,
        atr_stop_pct=stop_pct,
    )

    k = report.kelly
    dd = report.drawdown_scale
    fr = report.fixed_risk

    t = Table(title=f"Risk Analizi — {ir.name}")
    t.add_column("Metrik")
    t.add_column("Değer")
    t.add_row("İşlem sayısı", str(report.n_trades))
    t.add_row("Kazanma oranı", f"{k.win_rate:.1%}")
    t.add_row("Ort. kazanç / kayıp", f"+{k.avg_win:.2%} / -{k.avg_loss:.2%}")
    t.add_row("Odds (b)", f"{k.odds:.2f}")
    t.add_row("Tam Kelly", f"{k.full_kelly:.1%}")
    t.add_row("Yarı Kelly (önerilen)", f"[green]{k.half_kelly:.1%}[/green]")
    t.add_row("Sınırlı Kelly (max %25)", f"[cyan]{k.capped_kelly:.1%}[/cyan]")
    t.add_row("Anlık drawdown", f"{dd.current_drawdown_pct:.1f}%")
    t.add_row("Ölçek faktörü", f"{dd.scale_factor:.2f}")
    t.add_row("Sabit risk pozisyonu %", f"{fr.position_size_pct:.1f}%")
    t.add_row("Sabit risk pozisyonu $", f"${fr.position_size_usd:,.0f}")
    console.print(t)

    if report.warnings:
        for w in report.warnings:
            console.print(f"  [yellow]⚠[/yellow] {w}")

    console.print(Panel(report.recommendation, title="Öneri", border_style="cyan"))


@app.command("arxiv")
def arxiv_fetch(
    query: str = typer.Argument(..., help="Arama sorgusu, örn: 'momentum trading volatility'"),
    max_results: int = typer.Option(5, help="İndirilecek maksimum makale sayısı (1-20)"),
    search_only: bool = typer.Option(False, help="Yalnız ara, indirme yapma"),
    auto_ingest: bool = typer.Option(True, help="İndirdikten sonra otomatik indeksle"),
) -> None:
    """arXiv'den trading araştırması ara → indir → otomatik indeksle."""
    from app.ingestion.arxiv_fetcher import fetch_arxiv_papers, search_arxiv

    max_results = max(1, min(max_results, 20))

    if search_only:
        console.print(f"[cyan]arXiv aranıyor:[/cyan] {query!r} (max {max_results})")
        entries = search_arxiv(query, max_results=max_results)
        if not entries:
            console.print("[yellow]Sonuç bulunamadı.[/yellow]")
            raise typer.Exit()
        t = Table(title=f"arXiv sonuçları — '{query}'")
        t.add_column("ID")
        t.add_column("Başlık")
        t.add_column("Tarih")
        t.add_column("PDF")
        for e in entries:
            t.add_row(e.arxiv_id, e.title[:60], e.published, e.pdf_url)
        console.print(t)
        return

    console.print(f"[cyan]arXiv indiriliyor:[/cyan] {query!r} (max {max_results})")
    with console.status("PDF'ler indiriliyor…"):
        results = fetch_arxiv_papers(query, max_results=max_results)

    if not results:
        console.print("[yellow]İndirilecek makale bulunamadı.[/yellow]")
        raise typer.Exit()

    downloaded = [r for r in results if not r.skipped]
    skipped = [r for r in results if r.skipped]
    n_dl, n_sk = len(downloaded), len(skipped)
    console.print(f"[green]İndirilen:[/green] {n_dl}  [yellow]Atlanan:[/yellow] {n_sk}")

    if auto_ingest and downloaded:
        from app.memory.paper_indexer import PaperIndexer

        console.print("[cyan]İndeksleniysor…[/cyan]")
        ingest_results = PaperIndexer().ingest_directory()
        t = Table(title="İndirme + İndeksleme sonucu")
        t.add_column("arxiv_id")
        t.add_column("Başlık")
        t.add_column("Durum")
        for r in results:
            status = "skip (zaten vardı)" if r.skipped else "indirildi"
            t.add_row(r.arxiv_id, r.title[:55], status)
        for ir in ingest_results:
            if not ir.skipped:
                console.print(f"  ✓ {ir.paper_id} — {ir.n_chunks} chunk")
        console.print(t)
    else:
        for r in results:
            status = "[yellow]skip[/yellow]" if r.skipped else "[green]ok[/green]"
            console.print(f"  {status}  {r.arxiv_id}  {r.title[:55]}")


@app.command("profile")
def oss_profile(
    as_json: bool = typer.Option(False, "--json", help="JSON formatında çıktı ver"),
) -> None:
    """Sistemin hardware/software profilini tara ve göster."""
    from app.agents.system_profiler.profiler import collect

    profile = collect()
    if as_json:
        console.print_json(profile.model_dump_json(indent=2))
        return

    console.print(Panel("[bold cyan]Sistem Profili[/bold cyan]", border_style="cyan"))
    console.print(f"  OS      : {profile.os} {profile.os_version[:30]}")
    console.print(f"  Arch    : {profile.arch}")
    console.print(f"  CPU     : {profile.cpu.name} ({profile.cpu.cores}c/{profile.cpu.threads}t)")
    console.print(f"  RAM     : {profile.memory.ram_total_gb:.1f} GB total  |  {profile.memory.ram_available_gb:.1f} GB free")
    console.print(f"  GPU     : {profile.gpu.name}")
    console.print(f"  Vendor  : {profile.gpu.vendor}")
    console.print(f"  VRAM    : {profile.gpu.vram_gb:.1f} GB")
    flags = []
    if profile.gpu.cuda:
        flags.append("CUDA")
    if profile.gpu.metal:
        flags.append("Metal")
    if profile.gpu.rocm:
        flags.append("ROCm")
    console.print(f"  Accel   : {', '.join(flags) if flags else 'CPU only'}")
    console.print(f"  Disk    : {profile.disk.free_gb:.1f} GB free")
    console.print(f"  Python  : {profile.python_version}")
    tools = []
    if profile.tools.ollama:
        tools.append("ollama")
    if profile.tools.git:
        tools.append("git")
    if profile.tools.cmake:
        tools.append("cmake")
    console.print(f"  Tools   : {', '.join(tools) if tools else '—'}")


@app.command("recommend")
def oss_recommend(
    task: str = typer.Option("general", help="Görev türü: coding, general, reasoning, trading"),
    top_k: int = typer.Option(3, help="Kaç öneri gösterilsin"),
) -> None:
    """RAM/VRAM'a göre en uygun OSS modelini öner."""
    from app.agents.model_advisor.advisor import recommend
    from app.agents.system_profiler.profiler import collect

    console.print("[cyan]Sistem taranıyor...[/cyan]")
    profile = collect()
    result = recommend(profile, task=task, top_k=top_k)

    console.print(f"\n[bold]Sistem:[/bold] {result.system_summary}")
    console.print(f"[bold]Görev :[/bold] {task}\n")

    if result.recommended:
        t = Table(title="Önerilen Modeller")
        t.add_column("Sıra")
        t.add_column("Model")
        t.add_column("Ollama")
        t.add_column("Güven")
        t.add_column("Neden")
        for rec in result.recommended:
            t.add_row(
                str(rec.rank),
                rec.display_name,
                rec.ollama_name,
                f"{rec.confidence:.0%}",
                rec.reasons[0] if rec.reasons else "",
            )
        console.print(t)
    else:
        console.print("[yellow]Bu sistem için uygun model bulunamadı.[/yellow]")

    if result.rejected:
        console.print("\n[dim]Reddedilenler:[/dim]")
        for r in result.rejected:
            console.print(f"  [red]✗[/red] {r.display_name} — {r.reason}")


@app.command("install")
def oss_install(
    model: str = typer.Option("", "--model", help="Ollama model adı (örn. qwen2.5-coder:7b)"),
    auto_safe: bool = typer.Option(False, "--auto-safe", help="En iyi uygun modeli otomatik seç ve indir"),
    diagnose: bool = typer.Option(False, "--diagnose", help="Sadece tanı yap, kurma"),
) -> None:
    """OSS modeli Ollama ile kur (sadece güvenli whitelist komutlar)."""
    from app.agents.installer import ollama_installer as oi
    from app.agents.model_advisor.advisor import recommend
    from app.agents.system_profiler.profiler import collect

    profile = collect()

    if not oi.is_ollama_installed():
        console.print(f"[red]{oi.install_guide_text()}[/red]")
        raise typer.Exit(1)

    console.print(f"[green]Ollama:[/green] {oi.get_ollama_version()}")

    if diagnose:
        result = recommend(profile, task="general")
        console.print(f"\n[bold]Sistem:[/bold] {result.system_summary}")
        if result.recommended:
            top = result.recommended[0]
            console.print(f"[bold]Öneri :[/bold] {top.display_name} ({top.ollama_name})")
            for r in top.reasons:
                console.print(f"  • {r}")
        return

    ollama_name = model
    if not ollama_name and auto_safe:
        result = recommend(profile, task="general")
        if not result.recommended:
            console.print("[red]Uygun model bulunamadı.[/red]")
            raise typer.Exit(1)
        ollama_name = result.recommended[0].ollama_name
        console.print(f"[cyan]Otomatik seçildi:[/cyan] {ollama_name}")

    if not ollama_name:
        console.print("[red]--model veya --auto-safe kullan.[/red]")
        raise typer.Exit(1)

    # Manuel seçimde uyarı kontrolü
    if model and not auto_safe:
        result = recommend(profile, task="general")
        if result.recommended and result.recommended[0].ollama_name != model:
            console.print(f"[yellow]⚠ Uyarı: Sisteminiz için önerilen model '{result.recommended[0].ollama_name}'. "
                          f"'{model}' seçildi — çalışmayabilir.[/yellow]")

    console.print(f"[cyan]İndiriliyor:[/cyan] {ollama_name} ...")
    r = oi.pull_model(ollama_name)
    if r.status == "ok":
        console.print(f"[green]✓ İndirildi:[/green] {ollama_name}")
    else:
        console.print(f"[red]Hata:[/red] {r.error}")
        raise typer.Exit(1)


@app.command("benchmark")
def oss_benchmark(
    model: str = typer.Argument(..., help="Ollama model adı (örn. qwen2.5-coder:7b)"),
    quick: bool = typer.Option(False, "--quick", help="Sadece ilk prompt (hızlı)"),
    save: bool = typer.Option(True, help="Sonucu SQLite'a kaydet"),
) -> None:
    """Modeli benchmark et: tokens/sec, kalite, durum."""
    from app.agents.benchmark.runner import run as bench_run
    from app.agents.learning.memory import save_model_trial, save_system_profile
    from app.agents.system_profiler.profiler import collect

    console.print(f"[cyan]Benchmark başlıyor:[/cyan] {model} {'(hızlı)' if quick else ''}")
    result = bench_run(model, quick=quick)

    color_map = {
        "excellent": "green",
        "usable": "cyan",
        "slow_but_usable": "yellow",
        "unstable": "orange3",
        "failed": "red",
    }
    color = color_map.get(result.status, "white")

    t = Table(title=f"Benchmark — {model}")
    t.add_column("Metrik")
    t.add_column("Değer")
    t.add_row("Durum", f"[{color}]{result.status}[/{color}]")
    t.add_row("tokens/sec", f"{result.tokens_per_second:.1f}")
    t.add_row("İlk token gecikmesi", f"{result.first_token_latency_ms:.0f} ms")
    t.add_row("Peak RAM delta", f"{result.peak_ram_gb:.2f} GB")
    t.add_row("Kalite skoru", f"{result.quality_score:.2f}")
    console.print(t)

    for pr in result.prompt_results:
        icon = "[green]✓[/green]" if pr.status == "ok" else "[red]✗[/red]"
        console.print(f"  {icon} {pr.prompt_id}: kalite={pr.quality:.1f}  latency={pr.latency_ms:.0f}ms")

    if save and result.status != "failed":
        profile = collect()
        pid = save_system_profile(profile.model_dump())
        save_model_trial(
            system_profile_id=pid,
            model_id=model,
            backend="ollama",
            status=result.status,
            tokens_per_second=result.tokens_per_second,
            first_token_latency_ms=result.first_token_latency_ms,
            peak_ram_gb=result.peak_ram_gb,
            quality_score=result.quality_score,
        )
        console.print("[dim]✓ Sonuç SQLite'a kaydedildi.[/dim]")


if __name__ == "__main__":  # pragma: no cover
    app()
