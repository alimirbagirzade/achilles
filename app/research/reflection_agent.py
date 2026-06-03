"""Yansıma Ajanı — backtest sonucunu analiz edip sonraki iterasyon için iyileştirme önerir.

Görevi:
  1. Önceki indikatörü ve backtest sonucunu al
  2. "Neden başarısız?" sorusunu sor
  3. Spesifik iyileştirme öner (parametre değiştir, yeni bileşen ekle, kural gevşet)
  4. Yeni StrategyIR üret
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.brain.local_llm import LLMUnavailable, LocalLLM

logger = logging.getLogger(__name__)

_REFLECTION_PROMPT = """\
Bir trading araştırmacısısın. Aşağıdaki backtest sonucunu analiz et ve daha iyi bir versiyon öner.

━━━ ÖNCEKİ İNDİKATÖR ━━━
{indicator_summary}

━━━ BACKTEST SONUÇLARI ━━━
Yargı: {verdict}
Sebepler: {reasons}

Metrikler:
  İşlem sayısı: {n_trades}
  Toplam getiri: {total_return:.4f}%
  Sharpe: {sharpe}
  Max Drawdown: {max_dd:.4f}%
  Örneklem-dışı getiri: {oos_return}

━━━ ANALİZ VE İYİLEŞTİRME ━━━
Şunları yap:
1. Başarısızlık sebebini analiz et (1-3 cümle)
2. Spesifik neyi değiştireceğini belirt
3. Yeni StrategyIR ver (sadece değişen kısımları değil, tam IR)

Yanıtı JSON formatında ver:
{{
  "failure_analysis": "Neden başarısız oldu...",
  "changes": ["period 14→20 değiştirildi", "hacim filtresi eklendi"],
  "improvement_reasoning": "Bu değişiklikler neden yardımcı olacak...",
  "strategy_ir": {{
    "name": "..._v2",
    "market": "XAUUSD",
    "timeframe": "15m",
    "indicators": [...],
    "entry_rules": [...],
    "exit_rules": [...],
    "risk": {{"stop_loss": "2 * ATR"}},
    "costs": {{"commission": 0.0005, "slippage": 0.0005}}
  }}
}}
"""


class ReflectionAgent:
    def __init__(self, llm: LocalLLM | None = None) -> None:
        self.llm = llm or LocalLLM()

    def reflect(
        self,
        indicator: dict[str, Any],
        backtest_result: dict[str, Any],
        verdict: str,
        reasons: list[str],
    ) -> dict[str, Any] | None:
        """Backtest sonucunu analiz et, iyileştirilmiş IR döndür."""
        metrics = backtest_result.get("metrics", {})
        oos = backtest_result.get("oos_metrics", {})

        prompt = _REFLECTION_PROMPT.format(
            indicator_summary=self._format_indicator(indicator),
            verdict=verdict,
            reasons="; ".join(reasons),
            n_trades=metrics.get("n_trades", 0),
            total_return=metrics.get("total_return_pct", 0.0),
            sharpe=metrics.get("sharpe") or "—",
            max_dd=metrics.get("max_drawdown_pct", 0.0),
            oos_return=oos.get("total_return_pct", "—") if oos else "—",
        )

        try:
            raw = self.llm.generate(prompt, fmt="json", timeout=120, max_tokens=1500)
            return self._parse(raw)
        except LLMUnavailable as exc:
            logger.warning("LLM çevrimdışı: %s", exc)
        except Exception as exc:
            logger.warning("Yansıma başarısız: %s", exc)
        return None

    def _format_indicator(self, indicator: dict[str, Any]) -> str:
        name = indicator.get("indicator_name", "bilinmiyor")
        reasoning = indicator.get("combination_reasoning", "")
        ir = indicator.get("strategy_ir", {})
        entry = ir.get("entry_rules", [])
        return f"Ad: {name}\nMantık: {reasoning[:200]}\nGiriş kuralları: {entry}"

    def _parse(self, raw: str) -> dict[str, Any] | None:
        raw = raw.strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group())
        except (json.JSONDecodeError, ValueError):
            return None

        if not data.get("strategy_ir"):
            return None

        ir = data["strategy_ir"]
        ir.setdefault("costs", {"commission": 0.0005, "slippage": 0.0005})
        ir.setdefault("risk", {"stop_loss": "2 * ATR"})
        return data
