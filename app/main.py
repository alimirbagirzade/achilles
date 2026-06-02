"""Achilles Trader AI — command line interface.

Run:  uv run achilles --help

Pipeline order (per spec):
  ingest -> ask (RAG) -> card -> dataset -> train -> eval -> backtest
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


@app.command()
def dataset() -> None:
    """Saklanan training örneklerinden train/valid JSONL üret."""
    from app.training.dataset_builder import DatasetBuilder

    res = DatasetBuilder().build()
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
    iterations: int = typer.Option(600),
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


if __name__ == "__main__":  # pragma: no cover
    app()
