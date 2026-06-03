"""Sentez Motoru — tüm formül ve kavramları aynı anda görüp yeni indikatör önerir.

Bu modül projenin kalbidir: LLM'i "trader gibi düşünmeye" zorlar.
Prompt yapısı:
  1. Bilinen formüller (yapısal)
  2. Kavram grafiği
  3. Araştırma sorusu
  4. Zorunlu yapısal çıktı (StrategyIR uyumlu JSON)

Guardrail'ler:
  - "garanti kâr" / "kesin kazandırır" yasak
  - Her öneri "hipotez" olarak etiketlenir
  - Başarısızlık koşulları zorunlu
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from app.brain.local_llm import LLMUnavailable, LocalLLM
from app.memory.sqlite_store import SqliteStore

logger = logging.getLogger(__name__)

_SYNTHESIS_PROMPT = """\
Sen kantitatif bir araştırma asistanısın. Görevin: aşağıdaki bilgi tabanını analiz ederek \
daha önce denenmemiş yaratıcı bir trading indikatörü veya algoritma kombinasyonu önermek.

━━━ MEVCUT FORMÜLLER ━━━
{formulas_text}

━━━ KAVRAM İLİŞKİLERİ ━━━
{concept_graph}

━━━ ARAŞTIRMA SORUSU ━━━
{question}

━━━ KURALLAR ━━━
• Bu bir araştırma hipotezidir. "Garanti kazandırır" veya "kesin çalışır" deme.
• Her önerinin neden BAŞARISIZ olabileceğini açıkla.
• Gerçek formül bileşenlerine dayan, hayal etme.
• Komisyon ve slippage'ı her zaman hesaba kat.

━━━ ÇIKTI FORMATI (JSON) ━━━
{{
  "indicator_name": "VolumeAdjustedMomentum",
  "description": "Kısa açıklama",
  "source_papers": ["paper_abc", "paper_xyz"],
  "formula_components": [
    {{"name": "RSI", "role": "momentum sinyal", "period": 14}},
    {{"name": "ATR", "role": "volatilite filtre", "period": 14}}
  ],
  "combination_reasoning": "Neden bu kombinasyon daha iyi sonuç verebilir?",
  "expected_edge": "Hangi piyasa koşulunda avantaj bekleniyor?",
  "failure_conditions": ["Trend piyasasında sinyal üretemez", "Düşük hacimde gürültü artar"],
  "strategy_ir": {{
    "name": "volume_adj_momentum_v1",
    "market": "XAUUSD",
    "timeframe": "15m",
    "indicators": [
      {{"name": "RSI", "period": 14}},
      {{"name": "ATR", "period": 14}},
      {{"name": "EMA", "period": 20}}
    ],
    "entry_rules": ["rsi_14 > 55", "ema_20 > ema_50"],
    "exit_rules": ["rsi_14 < 45"],
    "risk": {{"stop_loss": "2 * ATR"}},
    "costs": {{"commission": 0.0005, "slippage": 0.0005}}
  }}
}}

Yalnız JSON döndür, başka açıklama ekleme.
"""


@dataclass
class SynthesisResult:
    indicator_name: str
    description: str
    source_papers: list[str]
    formula_components: list[dict[str, Any]]
    combination_reasoning: str
    expected_edge: str
    failure_conditions: list[str]
    strategy_ir: dict[str, Any]
    raw_json: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "indicator_name": self.indicator_name,
            "description": self.description,
            "source_papers": self.source_papers,
            "formula_components": self.formula_components,
            "combination_reasoning": self.combination_reasoning,
            "expected_edge": self.expected_edge,
            "failure_conditions": self.failure_conditions,
            "strategy_ir": self.strategy_ir,
        }


class SynthesisEngine:
    def __init__(
        self,
        store: SqliteStore | None = None,
        llm: LocalLLM | None = None,
    ) -> None:
        self.store = store or SqliteStore()
        self.llm = llm or LocalLLM()

    def synthesize(
        self,
        question: str,
        *,
        paper_ids: list[str] | None = None,
        market: str = "XAUUSD",
        timeframe: str = "15m",
    ) -> SynthesisResult | None:
        """Araştırma sorusuna göre yeni indikatör öner."""
        formulas = self.store.list_formulas()
        if paper_ids:
            formulas = [f for f in formulas if f["paper_id"] in paper_ids]

        if not formulas:
            logger.warning("Formül bulunamadı — önce formula_extractor çalıştır")
            return None

        formulas_text = self._format_formulas(formulas)
        concept_graph = self._format_concept_graph()

        prompt = _SYNTHESIS_PROMPT.format(
            formulas_text=formulas_text,
            concept_graph=concept_graph,
            question=question,
        )

        try:
            raw = self.llm.generate(prompt, fmt="json", timeout=180, max_tokens=2048)
            result = self._parse_result(raw, market, timeframe)
            if result:
                logger.info("Sentez başarılı: %s", result.indicator_name)
                return result
        except LLMUnavailable as exc:
            logger.warning("LLM çevrimdışı: %s", exc)
        except Exception as exc:
            logger.warning("Sentez başarısız: %s", exc)

        return None

    def _format_formulas(self, formulas: list[dict]) -> str:
        lines = []
        by_cat: dict[str, list[dict]] = {}
        for f in formulas:
            cat = f.get("category") or "other"
            by_cat.setdefault(cat, []).append(f)

        for cat, fmls in sorted(by_cat.items()):
            lines.append(f"\n[{cat.upper()}]")
            for f in fmls:
                line = f"  • {f['name']}"
                if f.get("plain"):
                    line += f": {f['plain'][:120]}"
                elif f.get("description"):
                    line += f" — {f['description'][:100]}"
                if f.get("paper_id"):
                    line += f" [{f['paper_id'][:16]}]"
                lines.append(line)
        return "\n".join(lines) if lines else "(formül yok)"

    def _format_concept_graph(self) -> str:
        links = self.store.list_concept_links()
        if not links:
            return "(kavram grafiği boş)"
        lines = [
            f"  {lk['from_concept']} --[{lk['relation']}]--> {lk['to_concept']}"
            for lk in links[:40]
        ]
        return "\n".join(lines)

    def _parse_result(self, raw: str, market: str, timeframe: str) -> SynthesisResult | None:
        raw = raw.strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group())
        except (json.JSONDecodeError, ValueError):
            # Basit onarım dene
            fixed = raw.replace("'", '"')
            match2 = re.search(r"\{.*\}", fixed, re.DOTALL)
            if not match2:
                return None
            try:
                data = json.loads(match2.group())
            except Exception:
                return None

        ir = data.get("strategy_ir") or {}
        ir.setdefault("market", market)
        ir.setdefault("timeframe", timeframe)
        ir.setdefault("name", "synthesized_v1")
        ir.setdefault("indicators", [{"name": "RSI", "period": 14}, {"name": "ATR", "period": 14}])
        ir.setdefault("entry_rules", ["rsi_14 > 55"])
        ir.setdefault("exit_rules", ["rsi_14 < 45"])
        ir.setdefault("risk", {"stop_loss": "2 * ATR"})
        ir.setdefault("costs", {"commission": 0.0005, "slippage": 0.0005})

        return SynthesisResult(
            indicator_name=data.get("indicator_name", "unnamed_indicator"),
            description=data.get("description", ""),
            source_papers=data.get("source_papers", []),
            formula_components=data.get("formula_components", []),
            combination_reasoning=data.get("combination_reasoning", ""),
            expected_edge=data.get("expected_edge", ""),
            failure_conditions=data.get("failure_conditions", []),
            strategy_ir=ir,
            raw_json=data,
        )
