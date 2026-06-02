from app.memory.chroma_store import ChromaStore
from app.memory.embedding_service import EmbeddingService


def test_fake_embedding_deterministic():
    e = EmbeddingService(allow_fake=True)
    e._mode = "fake"
    a = e.embed_one("merhaba dunya")
    b = e.embed_one("merhaba dunya")
    assert a == b
    assert len(a) == 256
    # roughly unit norm
    norm = sum(x * x for x in a) ** 0.5
    assert abs(norm - 1.0) < 1e-6


def test_chroma_add_and_query():
    e = EmbeddingService(allow_fake=True)
    e._mode = "fake"
    chroma = ChromaStore(collection="test_collection")
    texts = ["volatilite kumelenmesi", "momentum stratejisi", "tahvil getirisi"]
    ids = [f"t_{i}" for i in range(3)]
    embs = e.embed(texts)
    chroma.add(ids, embs, texts, [{"paper_id": "p", "page_number": 1} for _ in texts])
    assert chroma.count() >= 3
    q = e.embed_one("volatilite kumelenmesi")
    res = chroma.query(q, top_k=3)
    assert res[0]["chunk_id"] in ids
