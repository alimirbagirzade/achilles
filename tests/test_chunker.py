from app.ingestion.chunker import TextChunk, chunk_text


def test_chunk_text_basic():
    text = "Paragraf bir. " * 50 + "\n\n" + "Paragraf iki. " * 50 + "\n\n" + "Paragraf uc. " * 50
    chunks = chunk_text("paper_x", text, chunk_size=300, overlap=50)
    assert len(chunks) >= 2
    assert all(isinstance(c, TextChunk) for c in chunks)
    assert chunks[0].chunk_id == "paper_x_c0000"
    assert all(c.char_count > 0 for c in chunks)


def test_chunk_ids_are_sequential():
    text = "\n\n".join(f"Bolum {i} icerigi burada." * 20 for i in range(5))
    chunks = chunk_text("p", text, chunk_size=200, overlap=20)
    idxs = [c.chunk_index for c in chunks]
    assert idxs == list(range(len(chunks)))


def test_token_estimate():
    c = TextChunk(paper_id="p", chunk_index=0, text="a" * 400)
    assert c.token_estimate == 100


def test_oversized_paragraph_after_small_is_split():
    # Küçük başlık + tek dev (math olmayan) gövde paragrafı: gövde cümle sınırında
    # bölünmeli; eskiden buf doluyken oversized chunk bölünmeden tek parça çıkıyordu.
    big_body = "Bu bir cümledir. " * 400  # ~6800 karakter, formül yok
    text = "Giris\n\n" + big_body
    chunks = chunk_text("p", text, chunk_size=600, overlap=0)
    # chunk_size sözleşmesi: hiçbir chunk limitin makul katından büyük olmamalı
    assert max(len(c.text) for c in chunks) <= 700
    assert len(chunks) >= 5
