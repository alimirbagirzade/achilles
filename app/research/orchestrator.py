"""Araştırma Orkestratorü — tam döngüyü yönetir.

Döngü:
  soru → sentezle → StrategyIR → backtest → değerlendir
       → verdict == pass? dur
       → değilse: yansıt → iyileştir → tekrar

Her iterasyon SQLite `research_sessions` tablosuna yazılır.
Tüm zincir daha sonra LoRA eğitim verisi olarak kullanılır.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.memory.sqlite_store import SqliteStore
from app.research.reflection_agent import ReflectionAgent
from app.research.synthesis_engine import SynthesisEngine, SynthesisResult
from app.trading.backtester import run_backtest
from app.trading.evaluator import evaluate as eval_strategy
from app.trading.market_data_loader import generate_synthetic_ohlcv
from app.trading.strategy_ir import StrategyIR

logger = logging.getLogger(__name__)


@dataclass
class IterationResult:
    session_id: str
    iteration: int
    indicator_name: str
    verdict: str
    reasons: list[str]
    metrics: dict[str, Any]
    reflection: str | None = None
    improvement_notes: str | None = None


@dataclass
class ResearchResult:
    question: str
    iterations: list[IterationResult] = field(default_factory=list)
    final_verdict: str = "inconclusive"
    best_session_id: str | None = None

    @property
    def converged(self) -> bool:
        return self.final_verdict == "pass"

    def summary(self) -> str:
        lines = [f"Araştırma: {self.question}", f"İterasyon: {len(self.iterations)}"]
        for it in self.iterations:
            lines.append(
                f"  [{it.iteration}] {it.indicator_name} → {it.verdict.upper()} "
                f"({', '.join(it.reasons[:1])})"
            )
        lines.append(f"Sonuç: {self.final_verdict.upper()}")
        return "\n".join(lines)


class ResearchOrchestrator:
    def __init__(
        self,
        store: SqliteStore | None = None,
        synthesis_engine: SynthesisEngine | None = None,
        reflection_agent: ReflectionAgent | None = None,
        max_iterations: int = 3,
        n_bars: int = 2000,
        seed: int = 42,
        market: str = "XAUUSD",
        timeframe: str = "15m",
    ) -> None:
        self.store = store or SqliteStore()
        self.synthesis = synthesis_engine or SynthesisEngine(store=self.store)
        self.reflection = reflection_agent or ReflectionAgent()
        self.max_iterations = max_iterations
        self.n_bars = n_bars
        self.seed = seed
        self.market = market
        self.timeframe = timeframe

    def run(self, question: str, paper_ids: list[str] | None = None) -> ResearchResult:
        """Bir araştırma sorusu için tam döngüyü çalıştır."""
        logger.info("Araştırma başladı: %s", question)
        result = ResearchResult(question=question)
        df = generate_synthetic_ohlcv(n=self.n_bars, seed=self.seed)

        current_indicator: SynthesisResult | None = None
        parent_session_id: str | None = None

        for iteration in range(1, self.max_iterations + 1):
            logger.info("İterasyon %d/%d", iteration, self.max_iterations)
            session_id = f"rs_{uuid.uuid4().hex[:12]}"

            # ---- Sentez / İyileştirme ----
            if iteration == 1 or current_indicator is None:
                synthesized = self.synthesis.synthesize(
                    question,
                    paper_ids=paper_ids,
                    market=self.market,
                    timeframe=self.timeframe,
                )
            else:
                synthesized = current_indicator  # yansıma zaten IR'ı güncelledi

            if synthesized is None:
                logger.warning("Sentez başarısız, döngü durdu.")
                break

            # ---- StrategyIR doğrulama ----
            ir_dict = synthesized.strategy_ir
            try:
                ir = StrategyIR.model_validate(ir_dict)
            except Exception as exc:
                logger.warning("IR doğrulama hatası: %s — varsayılan kullanılıyor", exc)
                from app.trading.strategy_ir import example_ir

                ir = example_ir()

            # ---- Backtest ----
            bt = run_backtest(df, ir)
            ev = eval_strategy(df, ir)
            metrics = bt.metrics.to_dict()

            # ---- Session kaydet ----
            self.store.save_research_session(
                session_id=session_id,
                question=question,
                iteration=iteration,
                parent_session_id=parent_session_id,
                source_paper_ids_json=json.dumps(synthesized.source_papers),
                synthesis_reasoning=synthesized.combination_reasoning,
                proposed_indicator_json=json.dumps(synthesized.to_dict(), ensure_ascii=False),
                strategy_ir_json=json.dumps(ir.model_dump(), ensure_ascii=False),
                backtest_result_json=json.dumps(
                    {
                        "metrics": metrics,
                        "verdict": ev.verdict,
                        "reasons": ev.reasons,
                    },
                    ensure_ascii=False,
                ),
                verdict=ev.verdict,
                status="done",
            )

            iter_result = IterationResult(
                session_id=session_id,
                iteration=iteration,
                indicator_name=synthesized.indicator_name,
                verdict=ev.verdict,
                reasons=ev.reasons,
                metrics=metrics,
            )

            # ---- Yansıma (son iterasyon değilse ve pass değilse) ----
            if ev.verdict != "pass" and iteration < self.max_iterations:
                reflection_data = self.reflection.reflect(
                    indicator=synthesized.to_dict(),
                    backtest_result={"metrics": metrics},
                    verdict=ev.verdict,
                    reasons=ev.reasons,
                )
                if reflection_data:
                    reflection_text = reflection_data.get("failure_analysis", "")
                    improvement_notes = "; ".join(reflection_data.get("changes", []))
                    iter_result.reflection = reflection_text
                    iter_result.improvement_notes = improvement_notes

                    # Yansıma IR'ı mevcut indikatöre aktar
                    new_ir = reflection_data.get("strategy_ir")
                    if new_ir:
                        from copy import deepcopy

                        updated = deepcopy(synthesized)
                        updated.strategy_ir = new_ir
                        updated.indicator_name = new_ir.get("name", synthesized.indicator_name)
                        updated.combination_reasoning = reflection_data.get(
                            "improvement_reasoning", ""
                        )
                        current_indicator = updated
                    # Yansımayı session'a kaydet
                    self.store.save_research_session(
                        session_id=session_id,
                        question=question,
                        iteration=iteration,
                        parent_session_id=parent_session_id,
                        source_paper_ids_json=json.dumps(synthesized.source_papers),
                        synthesis_reasoning=synthesized.combination_reasoning,
                        proposed_indicator_json=json.dumps(
                            synthesized.to_dict(), ensure_ascii=False
                        ),
                        strategy_ir_json=json.dumps(ir.model_dump(), ensure_ascii=False),
                        backtest_result_json=json.dumps(
                            {"metrics": metrics, "verdict": ev.verdict, "reasons": ev.reasons},
                            ensure_ascii=False,
                        ),
                        verdict=ev.verdict,
                        reflection=reflection_text,
                        improvement_notes=improvement_notes,
                        status="done",
                    )

            result.iterations.append(iter_result)
            parent_session_id = session_id

            if ev.verdict == "pass":
                result.final_verdict = "pass"
                result.best_session_id = session_id
                logger.info("PASS — iterasyon %d'de yakınsadı.", iteration)
                break

        if result.final_verdict != "pass" and result.iterations:
            result.final_verdict = result.iterations[-1].verdict
            result.best_session_id = result.iterations[-1].session_id

        logger.info("Araştırma tamamlandı:\n%s", result.summary())
        return result
