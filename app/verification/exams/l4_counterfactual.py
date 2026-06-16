"""L4 CounterfactualExam — KARŞIOLGU sınavı.

Bir parametre (periyot) deterministik biçimde değiştirilir; göstergenin ölçülebilir
bir özelliğinin (ardışık değişimlerin oynaklığı = "pürüzsüzlük") YÖNÜ **koddan**
(ReferenceOracle) türetilir. Sonra modele "periyot artarsa bu oynaklık artar mı /
azalır mı / aynı mı?" sorulur ve cevabı bu deterministik gerçeğe karşı puanlanır.

Referans yön daima koddan gelir, modelden DEĞİL. LLM yoksa 'skipped' (sahte pass yok).
Pürüzsüzlük belirgin değişmiyorsa (yön gürültüde kalıyorsa) 'no_data' döner —
yazı-tura yapılmaz.
"""

from __future__ import annotations

import json
import re

import numpy as np
import pandas as pd

from app.brain.local_llm import LLMUnavailable, LocalLLM
from app.verification.exams.l3_application import ExamResult
from app.verification.exams.reference_oracle import ReferenceOracle
from app.verification.exams.registry import ExamSpec, get_spec

__all__ = ["CounterfactualExam"]

# Normalize edilmiş yön etiketleri
_INCREASE = "artar"
_DECREASE = "azalir"
_SAME = "ayni"

_PROMPT = """\
Bir teknik gösterge düşün: {definition}

Bu göstergeyi aynı fiyat serisine iki kez uyguluyoruz:
  - önce PERİYOT = {p}
  - sonra PERİYOT = {p2}  (daha büyük)

SORU: Periyot {p}'den {p2}'ye ÇIKARSA, göstergenin "oynaklığı" — yani ardışık \
değerleri arasındaki değişimlerin büyüklüğü (pürüzlülük) — nasıl değişir?

Yalnızca şu JSON'u döndür, başka hiçbir şey yazma:
{{"direction": "artar" | "azalir" | "ayni"}}
"""


class CounterfactualExam:
    def __init__(self, llm: LocalLLM | None = None, oracle: ReferenceOracle | None = None) -> None:
        self.llm = llm or LocalLLM()
        self.oracle = oracle or ReferenceOracle()

    def run_by_name(
        self,
        name: str,
        *,
        period: int | None = None,
        factor: int = 2,
        n_points: int = 200,
        seed: int = 0,
    ) -> ExamResult:
        return self.run(get_spec(name), period=period, factor=factor, n_points=n_points, seed=seed)

    def run(
        self,
        spec: ExamSpec,
        *,
        period: int | None = None,
        factor: int = 2,
        n_points: int = 200,
        seed: int = 0,
        eps: float = 1e-6,
    ) -> ExamResult:
        p = period or spec.default_period
        p2 = p * factor
        closes = self.oracle.synthetic_closes(n_points, seed)
        df = pd.DataFrame({"close": closes})

        rough_base = _roughness(spec.reference(df, p).to_numpy(dtype=float))
        rough_pert = _roughness(spec.reference(df, p2).to_numpy(dtype=float))
        if np.isnan(rough_base) or np.isnan(rough_pert):
            return ExamResult(
                "L4", spec.name, False, "no_data", seed, {"reason": "pürüzsüzlük NaN"}
            )

        delta = rough_pert - rough_base
        if abs(delta) <= eps:
            return ExamResult(
                "L4",
                spec.name,
                False,
                "no_data",
                seed,
                {"reason": "yön belirgin değil (gürültü)", "delta": float(delta)},
            )

        truth = _DECREASE if delta < 0 else _INCREASE  # koddan türeyen GERÇEK yön

        if not self.llm.available():
            return ExamResult(
                "L4",
                spec.name,
                False,
                "skipped",
                seed,
                {"reason": "LLM kullanılamıyor — sahte pass üretilmez", "truth": truth},
            )

        prompt = _PROMPT.format(definition=spec.definition, p=p, p2=p2)
        try:
            raw = self.llm.generate(
                prompt, fmt="json", temperature=0.0, max_tokens=64, timeout=60, seed=seed
            )
        except LLMUnavailable:
            return ExamResult("L4", spec.name, False, "skipped", seed, {"reason": "LLMUnavailable"})

        model_dir = _parse_direction(raw)
        if model_dir is None:
            return ExamResult(
                "L4",
                spec.name,
                False,
                "failed",
                seed,
                {"reason": "yön parse edilemedi", "raw": raw[:200], "truth": truth},
            )

        ok = model_dir == truth
        return ExamResult(
            "L4",
            spec.name,
            ok,
            "passed" if ok else "failed",
            seed,
            {
                "period": p,
                "perturbed": p2,
                "truth": truth,
                "model": model_dir,
                "rough_base": float(rough_base),
                "rough_perturbed": float(rough_pert),
            },
        )


def _roughness(series: np.ndarray) -> float:
    """Tanımlı bölgedeki ardışık değişimlerin standart sapması (pürüzlülük)."""
    vals = series[~np.isnan(series)]
    if vals.size < 3:
        return float("nan")
    return float(np.std(np.diff(vals)))


def _parse_direction(raw: str) -> str | None:
    """Model çıktısından yönü çıkar (JSON direction alanı ya da anahtar kelime)."""
    raw = raw.strip()
    obj_match = re.search(r"\{.*\}", raw, re.DOTALL)
    if obj_match:
        try:
            obj = json.loads(obj_match.group())
            if isinstance(obj, dict) and isinstance(obj.get("direction"), str):
                norm = _normalize(obj["direction"])
                if norm:
                    return norm
        except (json.JSONDecodeError, ValueError):
            pass
    return _normalize(raw)


def _normalize(text: str) -> str | None:
    t = text.lower()
    # Türkçe + İngilizce eş anlamlılar; "azal" önce ("artar" da 'art' içerir ama
    # azalma metni 'azal' ile başlar, çakışma yok).
    if "azal" in t or "decreas" in t or "düş" in t or "lower" in t or "smooth" in t:
        return _DECREASE
    if "art" in t or "increas" in t or "yüksel" in t or "higher" in t:
        return _INCREASE
    if "ayn" in t or "değişme" in t or "sabit" in t or "same" in t or "unchang" in t:
        return _SAME
    return None
