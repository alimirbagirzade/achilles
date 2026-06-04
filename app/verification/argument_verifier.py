"""Argument verifier — checks for premise and conclusion in text.

Searches for premise/conclusion markers in both Turkish and English.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Öncül belirteçleri
_PREMISE_RE = re.compile(
    r"\b(dolayısıyla|bu nedenle|therefore|thus|since|because|çünkü|zira|"
    r"given that|as a result of|since|due to|nedeniyle)\b",
    re.IGNORECASE,
)

# Sonuç belirteçleri
_CONCLUSION_RE = re.compile(
    r"\b(sonuç olarak|hence|therefore|thus|conclude|sonuç|"
    r"bu sonuçta|we conclude|it follows|consequently|accordingly|"
    r"netice itibarıyla|özetle)\b",
    re.IGNORECASE,
)


@dataclass
class ArgumentCheck:
    """Argüman bütünlüğü değerlendirmesi."""

    has_premise: bool
    has_conclusion: bool
    is_complete: bool  # Hem öncül hem sonuç varsa True


class ArgumentVerifier:
    """Metinde öncül ve sonuç yapısını doğrulayan sınıf."""

    def verify(self, text: str) -> ArgumentCheck:
        """Argüman bütünlüğünü kontrol et.

        Args:
            text: İncelenecek metin.

        Returns:
            ArgumentCheck nesnesi.
        """
        has_premise = bool(_PREMISE_RE.search(text))
        has_conclusion = bool(_CONCLUSION_RE.search(text))
        is_complete = has_premise and has_conclusion

        return ArgumentCheck(
            has_premise=has_premise,
            has_conclusion=has_conclusion,
            is_complete=is_complete,
        )
