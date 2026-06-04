"""Table verifier — parses markdown table syntax and checks completeness.

Supports the markdown pipe table format.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Markdown tablo satırı deseni
_TABLE_ROW_RE = re.compile(r"^\s*\|.+\|\s*$", re.MULTILINE)
_SEPARATOR_ROW_RE = re.compile(r"^\s*\|[-| :]+\|\s*$", re.MULTILINE)


@dataclass
class TableCheck:
    """Tablo bütünlüğü değerlendirmesi."""

    has_header: bool
    row_count: int
    col_count: int
    is_complete: bool  # Başlık + ayırıcı + en az bir veri satırı


def _count_cols(row: str) -> int:
    """Bir tablo satırındaki sütun sayısını say."""
    parts = row.strip().strip("|").split("|")
    return len(parts)


class TableVerifier:
    """Markdown tablo sözdizimini doğrulayan sınıf."""

    def verify(self, text: str) -> TableCheck | None:
        """Metindeki tabloyu doğrula.

        Args:
            text: İncelenecek metin.

        Returns:
            Tablo bulunursa TableCheck, bulunamazsa None.
        """
        rows = _TABLE_ROW_RE.findall(text)
        if not rows:
            return None

        has_header = False
        has_separator = False
        data_rows = 0
        col_count = 0

        for i, row in enumerate(rows):
            # Ayırıcı satır (--- | --- formatı)
            if _SEPARATOR_ROW_RE.match(row):
                has_separator = True
                if i > 0 and not has_header:
                    has_header = True  # Ayırıcıdan önce başlık var
            else:
                if not has_header and not has_separator:
                    has_header = True
                    col_count = _count_cols(row)
                elif has_separator:
                    data_rows += 1
                    if col_count == 0:
                        col_count = _count_cols(row)

        is_complete = has_header and has_separator and data_rows >= 1

        return TableCheck(
            has_header=has_header,
            row_count=data_rows,
            col_count=col_count,
            is_complete=is_complete,
        )
