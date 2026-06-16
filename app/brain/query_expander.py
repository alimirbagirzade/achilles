"""Rule-based query expander — generates multiple alternative queries.

Works without an LLM; uses finance/trading, math, and philosophy domain dictionaries.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Eş anlamlı / ilgili terimler sözlüğü
# ---------------------------------------------------------------------------
_FINANCE_SYNONYMS: dict[str, list[str]] = {
    "volatility": ["volatilite", "vol", "ATR", "realized vol", "implied vol", "vix proxy"],
    "volatilite": ["volatility", "vol", "ATR", "HV", "historical volatility"],
    "momentum": ["momentum", "rate of change", "ROC", "relative strength", "trend strength"],
    "atr": ["ATR", "average true range", "volatility band", "range filter"],
    "drawdown": ["drawdown", "max drawdown", "underwater", "peak to trough"],
    "sharpe": ["Sharpe ratio", "risk-adjusted return", "Sortino", "calmar"],
    "regime": ["market regime", "trending vs ranging", "volatility regime", "macro regime"],
    "microstructure": [
        "market microstructure",
        "bid-ask spread",
        "order flow",
        "liquidity",
    ],
    "trend": ["trend", "directional movement", "ADX", "moving average crossover"],
    "mean reversion": ["mean reversion", "cointegration", "Bollinger bands", "z-score"],
    "backtest": ["backtest", "historical simulation", "strategy evaluation", "out-of-sample"],
    "overfitting": ["overfitting", "data snooping", "curve fitting", "lookahead bias"],
    "liquidity": ["liquidity", "volume", "depth", "order book", "slippage"],
    "correlation": ["correlation", "covariance", "beta", "factor exposure"],
    "risk": ["risk", "tail risk", "VaR", "expected shortfall", "drawdown"],
    "signal": ["signal", "entry rule", "indicator", "trigger"],
    "filter": ["filter", "regime filter", "noise reduction", "smoothing"],
    "momentum filtreli": ["momentum with regime filter", "regime-filtered momentum"],
    "volatilite filtreli": ["volatility-filtered strategy", "vol-adjusted momentum"],
    "volatilite filtreli momentum": [
        "momentum with ATR regime filter",
        "volatility-adjusted momentum strategy",
        "regime-aware momentum",
        "momentum + volatility clustering",
    ],
}

_MATH_SYNONYMS: dict[str, list[str]] = {
    "stochastic": [
        "stochastic process",
        "random process",
        "Wiener process",
        "Brownian motion",
    ],
    "brownian": ["Brownian motion", "Wiener process", "random walk", "diffusion"],
    "fourier": ["Fourier transform", "spectral analysis", "frequency domain", "DFT"],
    "eigenvalue": ["eigenvalue", "eigendecomposition", "PCA", "principal component"],
    "convex": ["convex optimization", "gradient descent", "saddle point", "Lagrangian"],
    "entropy": [
        "entropy",
        "information content",
        "Shannon entropy",
        "KL divergence",
        "permutation entropy",
        "ordinal pattern",
        "Bandt-Pompe",
    ],
    "regression": ["regression", "OLS", "least squares", "linear model"],
    "covariance": ["covariance matrix", "correlation matrix", "variance-covariance"],
}

_PHILOSOPHY_SYNONYMS: dict[str, list[str]] = {
    "epistemology": [
        "epistemology",
        "theory of knowledge",
        "justified belief",
        "gettier problem",
    ],
    "ontology": ["ontology", "being", "existence", "metaphysics", "substance"],
    "causality": ["causality", "causation", "causal inference", "Hume causation"],
    "determinism": ["determinism", "free will", "compatibilism", "hard determinism"],
    "ethics": [
        "ethics",
        "moral philosophy",
        "normative ethics",
        "deontology",
        "utilitarianism",
    ],
}

_ALL_SYNONYMS: dict[str, list[str]] = {
    **_FINANCE_SYNONYMS,
    **_MATH_SYNONYMS,
    **_PHILOSOPHY_SYNONYMS,
}

# Finans/trading alanı anahtar kelimeleri (alan tespiti için)
_FINANCE_KEYWORDS: set[str] = {
    "volatility",
    "volatilite",
    "momentum",
    "trend",
    "backtest",
    "strategy",
    "atr",
    "drawdown",
    "sharpe",
    "regime",
    "signal",
    "filter",
    "return",
    "risk",
    "alpha",
    "beta",
    "liquidity",
    "microstructure",
}


def _tokenize(text: str) -> list[str]:
    """Küçük harfe çevirip token listesi döndür."""
    return re.findall(r"[a-zçğıöşüA-ZÇĞİÖŞÜ0-9]+", text.lower())


def _is_finance_query(query: str) -> bool:
    tokens = set(_tokenize(query))
    return bool(tokens & _FINANCE_KEYWORDS)


class QueryExpander:
    """Kural tabanlı sorgu genişletici.

    LLM gerektirmez. Alan sözlüğü üzerinden eş anlamlı / ilgili sorgular üretir.
    İsteğe bağlı olarak LocalLLM ile genişletilebilir (gelecek TODO).
    """

    def __init__(self, llm: object | None = None) -> None:
        # llm: opsiyonel LocalLLM; None ise saf kural tabanlı çalışır
        self._llm = llm

    def expand(self, query: str) -> list[str]:
        """Özgün sorgu + 3–5 alan alternatifi döndür.

        Args:
            query: Kullanıcının orijinal sorgusu.

        Returns:
            Özgün sorguyu başa ekleyerek en az 3 alternatif içeren liste.
        """
        alternatives: list[str] = []
        query_lower = query.lower().strip()

        # 1) Tam eşleşme
        if query_lower in _ALL_SYNONYMS:
            alternatives.extend(_ALL_SYNONYMS[query_lower])

        # 2) Alt dize eşleşmesi (sözlük anahtarı sorguda geçiyorsa)
        for key, expansions in _ALL_SYNONYMS.items():
            if len(key) > 3 and key in query_lower and key != query_lower:
                for exp in expansions[:2]:
                    candidate = query_lower.replace(key, exp)
                    if candidate != query_lower:
                        alternatives.append(candidate)

        # 3) Token bazlı eşleşme
        tokens = _tokenize(query)
        for tok in tokens:
            if tok in _ALL_SYNONYMS:
                for syn in _ALL_SYNONYMS[tok][:3]:
                    candidate = re.sub(
                        rf"\b{re.escape(tok)}\b",
                        syn,
                        query,
                        flags=re.IGNORECASE,
                    )
                    if candidate.lower() != query.lower():
                        alternatives.append(candidate)

        # 4) Finans sorgularına jenerik alternatifler ekle
        if _is_finance_query(query):
            alternatives.extend(
                [
                    f"{query} systematic trading",
                    f"{query} quantitative approach",
                    f"{query} risk-adjusted",
                ]
            )

        # Tekrarları temizle, orijinal sorguyu başa koy, en fazla 5 alternatif al
        seen: set[str] = {query.lower()}
        unique: list[str] = []
        for alt in alternatives:
            norm = alt.lower().strip()
            if norm not in seen and norm:
                seen.add(norm)
                unique.append(alt)
                if len(unique) >= 5:
                    break

        # En az 3 alternatif garantisi
        if len(unique) < 3:
            extra_suffixes = [
                " research",
                " methodology",
                " empirical evidence",
                " statistical analysis",
                " literature review",
            ]
            for suffix in extra_suffixes:
                if len(unique) >= 3:
                    break
                candidate = query + suffix
                if candidate.lower() not in seen:
                    unique.append(candidate)
                    seen.add(candidate.lower())

        return [query, *unique]
