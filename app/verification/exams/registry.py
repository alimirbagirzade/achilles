"""Sınav registry'si — her gösterge için referans + sınav parametreleri.

Her ``ExamSpec``:
  - ``definition``: modele gösterilecek KESİN convention (belirsizlik olmasın diye;
    sınav "hangi formül" tahminini değil, UYGULAMAYI ölçer),
  - ``reference``: ``compute_indicator`` üzerinden güvenli referans seri,
  - ``rtol``/``atol``: kayan-nokta toleransı (np.allclose),
  - ``monotonic``: L4 karşıolgu için "parametre artarsa beklenen yön" kuralı.

Sadece close-only registry indikatörleri (SMA/EMA/RSI) ilk turda; ATR/Bollinger
OHLC/çok-çıktı gerektirir, sonraki turda eklenir.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app.trading.indicators import compute_indicator

__all__ = ["ExamSpec", "get_spec", "list_specs"]


@dataclass(frozen=True)
class ExamSpec:
    name: str
    definition: str
    default_period: int = 14
    rtol: float = 1e-3
    atol: float = 1e-4
    needs_ohlc: bool = False
    # L4 için: parametre adı -> beklenen monoton yön (insan-okur + işaret testi notu)
    monotonic: dict[str, str] = field(default_factory=dict)

    def reference(self, df: pd.DataFrame, period: int) -> pd.Series:
        """Referans seri — daima güvenli compute_indicator registry'si."""
        return compute_indicator(self.name, df, period)


_SPECS: dict[str, ExamSpec] = {
    "SMA": ExamSpec(
        name="SMA",
        definition=(
            "SMA(p): basit hareketli ortalama. Her bar için, o bar dahil son p kapanış "
            "değerinin aritmetik ortalaması = (x[t-p+1] + ... + x[t]) / p."
        ),
        default_period=3,
        rtol=1e-6,
        atol=1e-6,
        monotonic={"period": "periyot artarsa seri daha pürüzsüz (daha az oynak) olur"},
    ),
    "EMA": ExamSpec(
        name="EMA",
        definition=(
            "EMA(p): üssel hareketli ortalama, alpha = 2/(p+1), adjust=False. "
            "İlk değer EMA[0] = x[0]; sonraki her bar EMA[t] = alpha*x[t] + (1-alpha)*EMA[t-1]."
        ),
        default_period=3,
        rtol=1e-6,
        atol=1e-6,
        monotonic={"period": "periyot artarsa daha pürüzsüz / daha çok gecikme"},
    ),
    "RSI": ExamSpec(
        name="RSI",
        definition=(
            "RSI(p) = 100 - 100/(1+RS). RS = Wilder ortalama kazanç / ortalama kayıp; "
            "kazanç/kayıp serileri ardışık close farklarından, ewm(alpha=1/p, adjust=False) ile."
        ),
        default_period=14,
        rtol=1e-2,
        atol=1e-2,
        monotonic={"period": "periyot artarsa daha az uç değer (daha pürüzsüz)"},
    ),
    "ENTROPY": ExamSpec(
        name="ENTROPY",
        definition=(
            "ENTROPY(p): yönsel ikili Shannon entropisi. Her bar için son p kapanış FARKINA bak; "
            "yukarı-hareket (fark>0) oranı q ise H = -(q·log2(q) + (1-q)·log2(1-q)); q=0 veya 1 "
            "iken H=0, q=0.5 iken H=1. Aralık [0,1]."
        ),
        default_period=4,
        rtol=1e-3,
        atol=1e-3,
        monotonic={"period": "periyot artarsa daha pürüzsüz (daha az oynak)"},
    ),
    "PERMENTROPY": ExamSpec(
        name="PERMENTROPY",
        definition=(
            "PERMENTROPY(p): Bandt-Pompe permütasyon entropisi (gömme boyutu order=3), "
            "[0,1] normalize. Son p bar üzerinde, ardışık 3'lü kapanış pencerelerinin "
            "SIRALAMA (ordinal) desenleri sayılır; desen dağılımının Shannon entropisi "
            "log2(3!)=log2(6) ile bölünür. Monoton seri → tek desen → 0; tüm desenler "
            "eşit olasılıkta → 1. Yalnız geçmiş pencere (look-ahead yok)."
        ),
        default_period=8,
        rtol=1e-3,
        atol=1e-3,
        monotonic={"period": "periyot artarsa daha pürüzsüz (daha kararlı tahmin)"},
    ),
}


def get_spec(name: str) -> ExamSpec:
    key = name.upper()
    if key not in _SPECS:
        raise KeyError(f"Sınav tanımı yok: {name!r} (mevcut: {sorted(_SPECS)})")
    return _SPECS[key]


def list_specs() -> list[ExamSpec]:
    return list(_SPECS.values())
