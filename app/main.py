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
    num_layers: int = typer.Option(8, help="LoRA adapter katman sayısı (sadece MLX)"),
    run: bool = typer.Option(False, help="Eğitimi gerçekten başlat"),
    backend: str = typer.Option("auto", help="Backend: auto|mlx|peft"),
) -> None:
    """LoRA eğitim komutunu hazırla — platform otomatik tespit edilir."""
    from app.training.backend import detect_lora_backend

    settings = get_settings()

    resolved = detect_lora_backend() if backend == "auto" else backend

    if resolved == "mlx":
        from app.training.mlx_lora_train import TrainConfig
        from app.training.mlx_lora_train import main as train_main
        from app.training.mlx_lora_train import run as train_run

        cfg = TrainConfig(
            base_model=base_model or settings.mlx_base_model,
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
    else:
        from app.training.peft_lora_train import PeftTrainConfig, dry_run
        from app.training.peft_lora_train import train as peft_train

        cfg = PeftTrainConfig(  # type: ignore[assignment]
            base_model=base_model or settings.peft_base_model,
            train_jsonl=settings.jsonl_dir / "train.jsonl",
            valid_jsonl=settings.jsonl_dir / "valid.jsonl",
            adapter_output_path=settings.adapters_dir / adapter_name,
            iterations=iterations,
        )
        if run:
            result = peft_train(cfg)  # type: ignore[arg-type]
            if not result.get("ok"):
                console.print(f"[red]Hata: {result.get('error')}[/red]")
                if "Eksik paketler" in str(result.get("error", "")):
                    console.print(
                        "[yellow]Kur: uv pip install torch transformers "
                        "peft datasets accelerate[/yellow]"
                    )
        else:
            result = dry_run(cfg)  # type: ignore[arg-type]
            import json as _json

            console.print(_json.dumps(result, ensure_ascii=False, indent=2))
            if result.get("missing_packages"):
                console.print(f"\n[yellow]Eksik paketler: {result['missing_packages']}[/yellow]")
                console.print(
                    "[yellow]Kur: uv pip install torch transformers "
                    "peft datasets accelerate[/yellow]"
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
    console.print(
        f"  RAM     : {profile.memory.ram_total_gb:.1f} GB total  |  "
        f"{profile.memory.ram_available_gb:.1f} GB free"
    )
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
    auto_safe: bool = typer.Option(
        False, "--auto-safe", help="En iyi uygun modeli otomatik seç ve indir"
    ),
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
            for reason in top.reasons:
                console.print(f"  • {reason}")
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
            console.print(
                f"[yellow]⚠ Uyarı: Sisteminiz için önerilen model "
                f"'{result.recommended[0].ollama_name}'. "
                f"'{model}' seçildi — çalışmayabilir.[/yellow]"
            )

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
        console.print(
            f"  {icon} {pr.prompt_id}: kalite={pr.quality:.1f}  latency={pr.latency_ms:.0f}ms"
        )

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


@app.command("tool-use-train")
def tool_use_train(
    questions: list[str] = typer.Argument(None, help="Araştırma soruları (boşsa varsayılan set)."),
    n_loops: int = typer.Option(1, "--n-loops", "-n", help="Her soru için iterasyon sayısı."),
    seed: int = typer.Option(42, "--seed"),
) -> None:
    """Tool-use eğitim döngüsünü çalıştır ve seansları DB'ye kaydet."""
    from app.training.tool_use_trainer import ToolUseTrainer

    _default_questions = [
        "Yüksek volatilitede RSI momentum stratejileri nasıl filtrelenir?",
        "EMA çaprazlaması ile volume spike kombinasyonu backtest'te ne kadar etkili?",
        "Düşük korelasyonlu indikatörler nasıl birleştirilir?",
    ]
    qs = list(questions) if questions else _default_questions
    trainer = ToolUseTrainer(seed=seed)
    console.print(f"[bold cyan]⚙ Tool-use eğitimi başlıyor — {len(qs)} soru[/bold cyan]")
    sessions = trainer.run_batch(qs, max_iterations=n_loops)
    pass_count = sum(1 for s in sessions if s.final_verdict == "pass")
    console.print(
        f"[green]✓ {len(sessions)} seans tamamlandı "
        f"({pass_count} geçti / {len(sessions) - pass_count} başarısız)[/green]"
    )
    console.print("[dim]Veri seti için: achilles tool-use-dataset[/dim]")


@app.command("tool-use-dataset")
def tool_use_dataset(
    output: str = typer.Option("data/training/tool_use_sft.jsonl", "--output", "-o"),
    only_verdict: str = typer.Option("", "--only-verdict", help="pass | fail | (boş=hepsi)"),
) -> None:
    """tool_use_examples → SFT JSONL veri seti oluştur."""
    from app.training.tool_use_dataset_builder import build_tool_use_dataset, get_tool_use_stats

    stats = get_tool_use_stats()
    console.print(
        f"[bold]Tool-use DB:[/bold] {stats['n_sessions']} seans · "
        f"{stats['n_steps']} adım · {stats['sft_eligible']} SFT uygun"
    )
    if stats["n_sessions"] == 0:
        console.print("[yellow]Önce: achilles tool-use-train[/yellow]")
        raise typer.Exit(1)

    examples = build_tool_use_dataset(
        output_path=output,  # type: ignore[arg-type]
        only_verdict=only_verdict or None,
    )
    console.print(f"[green]✓ {len(examples)} örnek → {output}[/green]")


@app.command("auto-research")
def auto_research(
    max_questions: int = typer.Option(5, "--max", "-n", help="İşlenecek maksimum soru sayısı."),
    iterations: int = typer.Option(1, "--iterations", "-i"),
    seed: int = typer.Option(42, "--seed"),
    all_cards: bool = typer.Option(False, "--all-cards", help="Onaysız kartları da dahil et."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Eğitim çalıştırmadan sorular üret."),
) -> None:
    """Onaylı kartlardan otomatik tool-use eğitimi: kart→soru→backtest→ödül."""
    from app.pipeline.auto_researcher import run_pipeline

    console.print("[bold cyan]⚙ Otomatik araştırma pipeline'ı başlıyor…[/bold cyan]")
    run = run_pipeline(
        max_questions=max_questions,
        max_iterations=iterations,
        seed=seed,
        only_approved=not all_cards,
        dry_run=dry_run,
    )
    console.print(f"\n[bold]Özet:[/bold]\n{run.summary()}")
    if run.errors:
        for e in run.errors[:3]:
            console.print(f"  [red]✗[/red] {e}")
    if dry_run:
        console.print(f"\n[dim]Üretilen sorular ({run.n_questions}):[/dim]")
        from app.memory.sqlite_store import SqliteStore
        from app.pipeline.auto_researcher import _extract_questions

        for q in _extract_questions(SqliteStore(), max_questions, not all_cards):
            console.print(f"  • {q}")


@app.command("reward-analyze")
def reward_analyze(
    session_id: str = typer.Option("", "--session", "-s", help="Tek seans ID'si."),
    build_dpo: bool = typer.Option(False, "--build-dpo", help="DPO veri seti oluştur."),
    output: str = typer.Option("data/training/dpo_pairs.jsonl", "--output", "-o"),
) -> None:
    """Tool-use seanslarını ödül sinyaliyle değerlendir; DPO çiftleri üret."""
    from app.training.dpo_dataset_builder import (
        build_dpo_dataset,
        get_dpo_stats,
        score_and_save_sessions,
    )
    from app.training.reward_signal import compute_reward

    if session_id:
        from app.memory.sqlite_store import SqliteStore

        store = SqliteStore()
        steps = store.list_tool_use_examples(session_id=session_id)
        if not steps:
            console.print(f"[red]Seans bulunamadı: {session_id}[/red]")
            raise typer.Exit(1)
        call_steps = [s for s in steps if s["step_type"] == "call"]
        if not call_steps:
            console.print("[yellow]Bu seansda call adımı yok.[/yellow]")
            raise typer.Exit(1)
        last = call_steps[-1]
        metrics = last.get("tool_output", {}).get("metrics", {})
        rc = compute_reward(metrics, verdict=last.get("verdict", "fail"))
        console.print(f"\n[bold]Seans:[/bold] {session_id}")
        console.print(f"Bileşik skor : [bold]{rc.composite:.3f}[/bold] → [{rc.label}]")
        for k, v in rc.to_dict().items():
            if k not in ("composite", "label", "notes"):
                console.print(f"  {k:<16} {v:.2f}")
        if rc.notes:
            console.print("[yellow]Notlar:[/yellow]", " | ".join(rc.notes))
        return

    new = score_and_save_sessions()
    if new:
        console.print(f"[green]✓ {len(new)} seans skorlandı[/green]")

    stats = get_dpo_stats()
    console.print(
        f"Toplam sinyal: {stats['n_signals']} | "
        f"chosen: {stats['label_distribution'].get('chosen', 0)} | "
        f"rejected: {stats['label_distribution'].get('rejected', 0)} | "
        f"DPO çifti potansiyeli: {stats['dpo_eligible_pairs']}"
    )

    if build_dpo:
        pairs = build_dpo_dataset(output_path=Path(output))
        console.print(f"[green]✓ {len(pairs)} DPO çifti → {output}[/green]")
    elif stats["dpo_eligible_pairs"] > 0:
        console.print("[dim]DPO veri seti için: achilles reward-analyze --build-dpo[/dim]")


@app.command("rules-update")
def oss_rules_update(
    dry_run: bool = typer.Option(False, "--dry-run", help="DB'ye yazmadan önerileri göster."),
    approve: str = typer.Option("", "--approve", help="Onaylanacak öneri ID'si."),
    dismiss: str = typer.Option("", "--dismiss", help="Reddedilecek öneri ID'si."),
) -> None:
    """Başarısız trial'lardan kural önerileri üret; bekleyenleri listele."""
    from app.agents.learning.rules_updater import (
        approve_suggestion,
        dismiss_suggestion,
        generate_rule_suggestions,
        list_pending_suggestions,
    )

    if approve:
        ok = approve_suggestion(approve)
        console.print("[green]✓ Onaylandı[/green]" if ok else "[red]Bulunamadı[/red]")
        return

    if dismiss:
        ok = dismiss_suggestion(dismiss)
        console.print("[yellow]✗ Reddedildi[/yellow]" if ok else "[red]Bulunamadı[/red]")
        return

    import json as _json

    new = generate_rule_suggestions(dry_run=dry_run)
    if new:
        label = "[dim](dry-run)[/dim]" if dry_run else ""
        console.print(f"\n[bold cyan]🔧 {len(new)} yeni öneri üretildi {label}[/bold cyan]")
        for s in new:
            console.print(f"  • [yellow]{s.rule_file}[/yellow] — {s.reason[:80]}…")

    pending = list_pending_suggestions()
    if pending:
        console.print(f"\n[bold]Onay bekleyen {len(pending)} öneri:[/bold]")
        for p in pending:
            patch = _json.loads(p.proposed_patch)
            console.print(
                f"  [dim]{p.suggestion_id[:8]}[/dim]  {patch.get('action', '?')} → {p.rule_file}"
            )
            console.print(f"    {p.reason[:100]}")
        console.print("\n[dim]Onaylamak: achilles rules-update --approve <id>[/dim]")
    elif not new:
        console.print("[green]✓ Yeni öneri yok; sistem sağlıklı.[/green]")


if __name__ == "__main__":  # pragma: no cover
    app()


# ---------------------------------------------------------------------------
# mastery commands
# ---------------------------------------------------------------------------


@app.command("mastery-run")
def mastery_run(
    paper_id: str = typer.Argument(..., help="Makale paper_id"),
    questions: int = typer.Option(20, help="Soru sayısı"),
) -> None:
    """Bir makale için Paper Mastery testi çalıştır."""
    from app.learning.paper_mastery_agent import PaperMasteryAgent

    console.print(f"[bold]Mastery testi başlatılıyor:[/bold] {paper_id}")
    agent = PaperMasteryAgent()
    result = agent.run(paper_id, question_count=questions)
    if result.error:
        console.print(f"[red]Hata:[/red] {result.error}")
        raise typer.Exit(1)
    console.print(result.summary())
    console.print(f"[dim]JSON rapor:[/dim] {result.report_json}")
    console.print(f"[dim]MD rapor:[/dim]   {result.report_md}")


@app.command("mastery-queue")
def mastery_queue(
    enqueue_all: bool = typer.Option(False, "--enqueue-all", help="Tüm makaleleri kuyruğa ekle"),
    run_next: bool = typer.Option(False, "--run-next", help="Sıradaki makaleyi test et"),
    run_all: bool = typer.Option(False, "--run-all", help="Tüm kuyruğu işle"),
    limit: int = typer.Option(50, help="--run-all için maks limit"),
) -> None:
    """Mastery öğrenme kuyruğunu göster ve yönet."""
    from app.learning.paper_mastery_agent import LearningQueue

    q = LearningQueue()
    if enqueue_all:
        n = q.enqueue_all_papers()
        console.print(f"[green]{n} makale kuyruğa eklendi.[/green]")
    if run_next:
        result = q.run_next()
        if result is None:
            console.print("[yellow]Kuyrukta bekleyen makale yok.[/yellow]")
        else:
            console.print(result.summary())
    elif run_all:
        results = q.run_all(limit=limit)
        console.print(f"[green]{len(results)} makale işlendi.[/green]")
        for r in results:
            status = "[green]✓[/green]" if not r.error else "[red]✗[/red]"
            total = r.score.total_score
            st = r.score.final_status
            console.print(f"  {status} {r.paper_id} — {total:.1f}/100 {st}")
    else:
        entries = q.list_all()
        if not entries:
            console.print("[dim]Kuyruk boş.[/dim]")
            return
        console.print(f"[bold]Mastery kuyruğu ({len(entries)} makale):[/bold]")
        for e in entries:
            console.print(f"  [{e['status']}] {e['paper_id']}  öncelik={e['priority']}")


@app.command("mastery-score")
def mastery_score(
    paper_id: str = typer.Argument(..., help="Makale paper_id"),
) -> None:
    """Bir makalenin son mastery skorunu göster."""
    from app.memory.mastery_store import MasteryStore

    ms = MasteryStore()
    score = ms.get_latest_score(paper_id)
    if score is None:
        console.print(f"[yellow]'{paper_id}' için henüz mastery skoru yok.[/yellow]")
        raise typer.Exit(1)
    ts = score["total_score"]
    fs = score["final_status"]
    console.print(f"[bold]{paper_id}[/bold]  —  {ts:.1f}/100  [{fs}]")
    for k, v in score.items():
        if k.endswith("_score") and k != "total_score":
            console.print(f"  {k}: {v}")


@app.command("mastery-report")
def mastery_report(
    paper_id: str = typer.Argument(..., help="Makale paper_id"),
) -> None:
    """Bir makalenin mastery raporunu göster."""
    import json as _json2
    from pathlib import Path

    report_path = Path("reports/papers/mastery") / f"{paper_id}_mastery_report.json"
    if not report_path.exists():
        console.print(f"[yellow]Rapor bulunamadı:[/yellow] {report_path}")
        raise typer.Exit(1)
    data = _json2.loads(report_path.read_text())
    score = data.get("score", {})
    ts = score.get("total_score", 0)
    fs = score.get("final_status", "?")
    console.print(f"[bold]{paper_id}[/bold]  total={ts:.1f}  status={fs}")
    q_total = data.get("questions", 0)
    q_pass = data.get("passed", 0)
    q_fail = data.get("failed", 0)
    console.print(f"Sorular: {q_total}  Geçti: {q_pass}  Kaldı: {q_fail}")


# ---------------------------------------------------------------------------
# arxiv-sync (Görev D: kayıtlı sorguları otomatik yeniden çalıştır)
# ---------------------------------------------------------------------------


@app.command("arxiv-sync")
def arxiv_sync(
    dry_run: bool = typer.Option(False, "--dry-run", help="Gerçekten çalıştırmadan listele"),
    force: bool = typer.Option(False, "--force", help="Son çalıştırma zamanına bakma"),
) -> None:
    """Kayıtlı arXiv sorgularını yeniden çalıştır, yeni makaleleri ingest et."""
    from app.ingestion.arxiv_fetcher import fetch_arxiv_papers
    from app.memory.sqlite_store import SqliteStore as _S

    store = _S()
    queries = store.list_arxiv_saved_queries()
    if not queries:
        console.print("[yellow]Kayıtlı arXiv sorgusu yok. Önce:[/yellow]")
        console.print('  uv run achilles arxiv "sorgu terimi"')
        return

    console.print(f"[bold]{len(queries)} kayıtlı sorgu bulundu.[/bold]")
    total_new = 0

    for q in queries:
        if dry_run:
            console.print(
                f"  [dim][dry-run][/dim] {q['query'][:60]}  "
                f"(son çalışma: {q['last_run_at'] or 'hiç'})"
            )
            continue
        if not q["auto_ingest"] and not force:
            console.print(f"  [dim]atla (auto_ingest=False):[/dim] {q['query'][:50]}")
            continue

        console.print(f"  ↻  {q['query'][:60]} ...")
        try:
            results = fetch_arxiv_papers(q["query"], max_results=q["max_results"])
            new_count = sum(1 for r in results if not r.skipped)
            total_new += new_count
            store.mark_arxiv_query_ran(q["query_id"])
            console.print(f"     [green]✓[/green] {new_count} yeni makale / {len(results)} toplam")
        except Exception as exc:
            console.print(f"     [red]✗[/red] Hata: {exc}")

    if not dry_run:
        console.print(f"\n[bold green]Toplam {total_new} yeni makale eklendi.[/bold green]")
        if total_new > 0:
            console.print("[dim]Yeni makaleler için: uv run achilles ingest[/dim]")


# ---------------------------------------------------------------------------
# mastery-to-sft (Mastery cevaplarını SFT eğitim verisi olarak dışa aktar)
# ---------------------------------------------------------------------------


@app.command("mastery-to-sft")
def mastery_to_sft(
    min_score: float = typer.Option(75.0, help="Minimum mastery skoru (0-100)"),
    citation: float = typer.Option(0.5, help="Minimum citation_score (0-1)"),
    output: str = typer.Option("", help="Çıktı JSONL dosya yolu"),
) -> None:
    """Mastery test sonuçlarından SFT eğitim JSONL'i üret."""
    from app.training.mastery_sft_builder import MasterySFTBuilder

    builder = MasterySFTBuilder()
    out_path = None if not output else __import__("pathlib").Path(output)
    path, n = builder.build_jsonl(
        output_path=out_path,
        min_mastery_score=min_score,
        citation_threshold=citation,
    )
    if n == 0:
        console.print(
            f"[yellow]Skor ≥ {min_score} olan ve citation ≥ {citation} olan "
            "cevap bulunamadı.[/yellow]"
        )
        console.print(
            "[dim]İpucu: Önce mastery testleri çalıştır:[/dim] "
            "achilles mastery-queue --enqueue-all && achilles mastery-queue --run-all"
        )
    else:
        console.print(f"[green]✓[/green] {n} SFT örneği → [bold]{path}[/bold]")


@app.command("unified-dataset")
def unified_dataset(
    min_score: float = typer.Option(75.0, help="Minimum mastery skoru"),
    citation: float = typer.Option(0.5, help="Minimum citation_score"),
    output: str = typer.Option("", help="Çıktı JSONL dosya yolu"),
) -> None:
    """Tüm SFT kaynaklarını birleştirip unified_sft.jsonl üret (LoRA faz 2)."""
    from pathlib import Path as _P

    from app.training.unified_dataset import UnifiedDatasetBuilder

    builder = UnifiedDatasetBuilder()
    stats = builder.build(
        output_path=_P(output) if output else None,
        min_mastery_score=min_score,
        citation_threshold=citation,
    )
    console.print("[bold green]✓ Unified dataset hazır[/bold green]")
    console.print(f"  {stats.summary()}")
    console.print(f"  → [bold]{stats.output_path}[/bold]")
    console.print()
    console.print("[dim]LoRA eğitimi için:[/dim]")
    console.print(f"  uv run achilles train --run --data {stats.output_path}")


# ---------------------------------------------------------------------------
# LoRA Training Control Plane (Gate 0-8 denetim hattı)
# ---------------------------------------------------------------------------


@app.command("lora-audit")
def lora_audit(
    dry_run: bool = typer.Option(
        True, "--dry-run/--run", help="Yalnız denetle (varsayılan); --run ile tam hat."
    ),
) -> None:
    """LoRA dataset denetim hattını (Gate 0-7, --run ile 0-8) çalıştır."""
    from app.lora.control_plane import LoRAControlPlane
    from app.memory.sqlite_store import SqliteStore

    plane = LoRAControlPlane(store=SqliteStore())
    report = plane.run_audit() if dry_run else plane.run_full(dry_run=False)

    table = Table(title="LoRA Denetim — Kapılar")
    table.add_column("Gate", justify="right")
    table.add_column("Ad")
    table.add_column("Sonuç")
    table.add_column("Red", justify="right")
    table.add_column("İnceleme", justify="right")
    for stage in report.stages:
        status = "[green]PASS[/green]" if stage.passed else "[red]FAIL[/red]"
        table.add_row(
            str(stage.gate_id),
            stage.name,
            status,
            str(stage.rejected_count),
            str(stage.review_count),
        )
    console.print(table)
    console.print(
        f"Girdi: {report.total_input} | Onaylanan: {report.total_approved} | "
        f"Reddedilen: {report.total_rejected} | İnceleme: {report.total_review_needed}"
    )
    verdict = "[green]GEÇTİ[/green]" if report.passed else "[red]BAŞARISIZ[/red]"
    console.print(f"Genel sonuç: {verdict}")

    settings = get_settings()
    report_path = settings.root / "reports" / "lora" / "audit_report.md"
    plane.generate_report(report, output_path=report_path)
    console.print(f"[dim]Rapor:[/dim] {report_path}")


@app.command("lora-dataset")
def lora_dataset(
    output: Path = typer.Option(
        Path("data/lora_sft"), "--output", help="Çıktı dizini (JSONL buraya yazılır)."
    ),
) -> None:
    """Onaylı kartlardan LoRA SFT JSONL veri seti üret."""
    from app.lora.dataset_builder import build_dataset, export_jsonl
    from app.memory.sqlite_store import SqliteStore

    store = SqliteStore()
    cards = store.list_approved_cards()
    examples = build_dataset(cards)
    settings = get_settings()
    out_dir = output if output.is_absolute() else (settings.root / output)
    out_path = out_dir / "lora_sft.jsonl"
    n = export_jsonl(examples, out_path)
    if n == 0:
        console.print(
            "[yellow]Uygun (approved + eligible) kart bulunamadı. Önce kartları onayla.[/yellow]"
        )
        return
    console.print(f"[green]✓[/green] {n} LoRA örneği → [bold]{out_path}[/bold]")

    # Eğitim split'i (train/valid) → jsonl_dir. PEFT/MLX eğitimi ve
    # auto-pipeline bu dosyaları okur. Çok küçük veri setinde valid boş kalmasın.
    from app.lora.dataset_splitter import split_dataset

    split = split_dataset(examples)
    train_ex = list(split.train) or list(examples)
    valid_ex = list(split.valid)
    if not valid_ex and len(train_ex) > 1:
        valid_ex = train_ex[-1:]
        train_ex = train_ex[:-1]
    jsonl_dir = settings.jsonl_dir
    jsonl_dir.mkdir(parents=True, exist_ok=True)
    nt = export_jsonl(train_ex, jsonl_dir / "train.jsonl")
    nv = export_jsonl(valid_ex, jsonl_dir / "valid.jsonl")
    console.print(f"[green]✓[/green] eğitim split → train={nt}, valid={nv}")
    console.print(f"  → [bold]{jsonl_dir}[/bold]")


@app.command("rag-mastery")
def rag_mastery() -> None:
    """RAG'in ne kadar 'öğrendiğini' gösteren ustalık panosu (LLM gerektirmez)."""
    from app.lora.dataset_builder import build_dataset
    from app.memory.sqlite_store import SqliteStore

    store = SqliteStore()
    papers = store.list_papers()
    n_papers = len(papers)
    cards = store.list_approved_cards()
    n_cards = len(cards)
    # Yalnızca İÇERİK TAŞIYAN kartları say (boş/title'sız kabuk kartlar örnek üretmez).
    examples = build_dataset(cards)
    n_examples = len(examples)
    papers_with_real = len(
        {str(e.metadata.get("paper_id", "")) for e in examples if e.metadata.get("paper_id")}
    )
    empty_cards = n_cards - n_examples

    scored = 0
    total_comp = 0.0
    for p in papers:
        row = store.get_comprehension_score(p.paper_id)
        if row is not None:
            scored += 1
            total_comp += row.total_score
    avg_comp = (total_comp / scored) if scored else None

    coverage = (papers_with_real / n_papers * 100) if n_papers else 0.0
    train_readiness = min(1.0, n_examples / 50.0) * 100
    comp_component = avg_comp if avg_comp is not None else 0.0

    # Bileşik ustalık = bilgi kapsamı (çıkarım) + anlama kalitesi + eğitim hazırlığı.
    # Anlama henüz hesaplanmadıysa 0 sayılır (ölçülmemiş = kanıtlanmamış).
    mastery = 0.40 * coverage + 0.30 * comp_component + 0.30 * train_readiness

    table = Table(title="RAG Ustalık Panosu")
    table.add_column("Metrik")
    table.add_column("Değer", justify="right")
    table.add_row("İçe alınan makale", str(n_papers))
    table.add_row("Onaylı bilgi kartı", f"{n_cards}  ({empty_cards} içeriksiz/atlandı)")
    table.add_row(
        "Bilgi kapsamı (gerçek kart/makale)",
        f"{papers_with_real}/{n_papers}  %{coverage:.0f}",
    )
    table.add_row("LoRA eğitim örneği", f"{n_examples}  (hazırlık %{train_readiness:.0f})")
    comp_txt = (
        f"%{avg_comp:.0f} ({scored}/{n_papers} makale)"
        if avg_comp is not None
        else f"hesaplanmadı ({scored}/{n_papers}) — LLM ile çalıştır"
    )
    table.add_row("Anlama skoru", comp_txt)
    console.print(table)
    console.print(
        f"\n[bold]RAG Ustalık (bileşik): %{mastery:.0f}[/bold]\n"
        f"[dim]= kapsam %{coverage:.0f}×0.4 + anlama %{comp_component:.0f}×0.3 "
        f"+ eğitim %{train_readiness:.0f}×0.3[/dim]"
    )
    if avg_comp is None:
        console.print(
            "[dim]Not: Anlama skoru için makale başına LLM doğrulaması gerekir "
            "(eğitim sürerken RAM çakışır — cooldown'da çalıştır).[/dim]"
        )


@app.command("lora-registry")
def lora_registry() -> None:
    """Adapter kayıt defterini listele."""
    from app.lora.adapter_registry import AdapterRegistry

    registry = AdapterRegistry()
    records = registry.list_adapters()
    if not records:
        console.print("[yellow]Kayıtlı adapter yok.[/yellow]")
        return

    table = Table(title="LoRA Adapter Kayıt Defteri")
    table.add_column("ID")
    table.add_column("Ad")
    table.add_column("Base Model")
    table.add_column("Durum")
    table.add_column("Eval", justify="right")
    for r in records:
        score = "-" if r.eval_score is None else f"{r.eval_score:.3f}"
        table.add_row(r.adapter_id, r.adapter_name, r.base_model, r.status.value, score)
    console.print(table)

    production = registry.get_production()
    if production:
        console.print(f"[green]Production:[/green] {production.adapter_name}")


@app.command("lora-status")
def lora_status() -> None:
    """LoRA hattının genel durumunu göster (eligible kart sayısı, aşamalar)."""
    from app.lora.adapter_registry import AdapterRegistry
    from app.memory.sqlite_store import SqliteStore

    store = SqliteStore()
    approved = store.list_approved_cards()
    pending = store.list_pending_cards()
    eligible = [c for c in approved if c.get("lora_eligible")]

    stage_counts: dict[str, int] = {}
    for card in eligible:
        stage = str(card.get("stage") or "(atanmamış)")
        stage_counts[stage] = stage_counts.get(stage, 0) + 1

    table = Table(title="LoRA Durum")
    table.add_column("Metrik")
    table.add_column("Değer", justify="right")
    table.add_row("Onaylı kart", str(len(approved)))
    table.add_row("Eligible kart", str(len(eligible)))
    table.add_row("Bekleyen (pending) kart", str(len(pending)))
    for stage, count in sorted(stage_counts.items()):
        table.add_row(f"stage: {stage}", str(count))

    registry = AdapterRegistry()
    table.add_row("Kayıtlı adapter", str(len(registry.list_adapters())))
    production = registry.get_production()
    table.add_row("Production adapter", production.adapter_name if production else "yok")
    console.print(table)
