"""Late chunking skeleton module.

Placeholder for the large-context embedding → sub-chunk strategy.
Currently delegates to HybridChunker.
"""

from __future__ import annotations

from app.ingestion.chunker import TextChunk
from app.ingestion.hybrid_chunker import HybridChunker


class LateChunker:
    """Geç chunklama modülü (iskelet).

    Geç chunklama prensibi: büyük bağlam embedding'i alındıktan sonra
    alt-chunk'lara bölünür; bu sayede her chunk tüm bağlamı "gördükten"
    sonra temsil edilmiş olur.

    TODO: Büyük bağlam embedding → alt-chunk projeksiyonu uygula.
    Şu an HybridChunker'a delege eder.
    """

    def __init__(self) -> None:
        self._fallback = HybridChunker()

    def chunk(self, paper_id: str, text: str) -> list[TextChunk]:
        """Metni geç chunklama stratejisiyle böl.

        Args:
            paper_id: Makale kimliği.
            text: Ham metin.

        Returns:
            TextChunk listesi.
        """
        # TODO: implement late chunking (large context embedding → sub-chunk)
        return self._fallback.chunk(paper_id, text)
