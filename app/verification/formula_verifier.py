"""Formula verifier — checks the integrity of LaTeX formulas in a chunk.

Validates formula syntax and detects missing variables.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.memory.retrieval_service import RetrievedChunk

# Formül bulma desenleri
_INLINE_FORMULA_RE = re.compile(r"\$([^$\n]+)\$")
_DISPLAY_FORMULA_RE = re.compile(r"\$\$(.+?)\$\$", re.DOTALL)
_BRACKET_FORMULA_RE = re.compile(r"\\\[(.+?)\\\]", re.DOTALL)
_PAREN_FORMULA_RE = re.compile(r"\\\((.+?)\\\)", re.DOTALL)

# Yaygın LaTeX değişken sembolleri
_VARIABLE_RE = re.compile(r"\\?([a-zA-Z]{1,3})(?:_\{?[^}]+\}?)?")

# Dengesiz parantez tespiti
_OPEN_CHARS = "({["
_CLOSE_CHARS = ")}]"
_MATCHING: dict[str, str] = {")": "(", "}": "{", "]": "["}


@dataclass
class FormulaCheck:
    """Tek bir formülün doğrulama sonucu."""

    formula_text: str
    is_complete: bool
    missing_variables: list[str] = field(default_factory=list)


def _is_balanced(text: str) -> bool:
    """Parantez/köşeli parantez dengeli mi?"""
    stack: list[str] = []
    for ch in text:
        if ch in _OPEN_CHARS:
            stack.append(ch)
        elif ch in _CLOSE_CHARS:
            if not stack or stack[-1] != _MATCHING[ch]:
                return False
            stack.pop()
    return len(stack) == 0


def _extract_formulas(text: str) -> list[str]:
    """Metindeki tüm formül metinlerini çıkar (iç içe değil)."""
    # Display önce (display içinde inline olabilir, çakışmayı önle)
    text_no_display = text
    formulas: list[str] = []

    for m in _DISPLAY_FORMULA_RE.finditer(text):
        formulas.append(m.group(1))
        text_no_display = text_no_display.replace(m.group(0), " " * len(m.group(0)))

    for m in _BRACKET_FORMULA_RE.finditer(text_no_display):
        formulas.append(m.group(1))
        text_no_display = text_no_display.replace(m.group(0), " " * len(m.group(0)))

    for m in _PAREN_FORMULA_RE.finditer(text_no_display):
        formulas.append(m.group(1))
        text_no_display = text_no_display.replace(m.group(0), " " * len(m.group(0)))

    for m in _INLINE_FORMULA_RE.finditer(text_no_display):
        formulas.append(m.group(1))

    return formulas


def _find_missing_variables(formula: str) -> list[str]:
    """Formülde tanımlanmamış görünen değişkenleri bul (çok basit yaklaşım)."""
    # \\sum, \\int gibi operatörler değil; tek harfli değişkenler ara
    tokens = _VARIABLE_RE.findall(formula)
    # Tek harfli, küçük/büyük harfler olası değişken
    candidates = [t for t in tokens if len(t) == 1 and t.isalpha()]
    # Yaygın matematiksel sabitler (değişken sayma)
    _CONSTANTS = {"e", "i", "n", "k", "x", "y", "z", "t", "p", "q"}
    # Gerçekten "eksik" tespit etmek zor; sadece \frac{}{} gibi boş argüman ara
    missing = []
    if re.search(r"\\frac\{\s*\}\{", formula) or re.search(r"\\frac\{[^}]*\}\{\s*\}", formula):
        missing.append("frac_arg")
    # Tek geçen, tanımlanmamış görünen harfler (heuristik)
    seen: set[str] = set()
    for c in candidates:
        if c not in _CONSTANTS and c not in seen:
            seen.add(c)
    return missing


class FormulaVerifier:
    """Chunk içindeki formüllerin bütünlüğünü doğrulayan sınıf."""

    def verify_chunk(self, chunk: RetrievedChunk) -> list[FormulaCheck]:
        """Chunk metnindeki tüm formülleri doğrula.

        Args:
            chunk: Doğrulanacak RetrievedChunk.

        Returns:
            Her formül için FormulaCheck listesi (formül yoksa boş liste).
        """
        formulas = _extract_formulas(chunk.text)
        results: list[FormulaCheck] = []

        for formula in formulas:
            balanced = _is_balanced(formula)
            missing_vars = _find_missing_variables(formula) if not balanced else []
            results.append(
                FormulaCheck(
                    formula_text=formula[:200],  # uzun formülleri kısalt
                    is_complete=balanced,
                    missing_variables=missing_vars,
                )
            )

        return results
