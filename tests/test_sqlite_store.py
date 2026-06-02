from app.memory.sqlite_store import Base


def test_schema_has_expected_tables(store):
    expected = {
        "papers",
        "chunks",
        "summaries",
        "knowledge_cards",
        "training_examples",
        "strategies",
        "backtests",
        "model_evaluations",
        "adapters",
    }
    assert expected.issubset(set(Base.metadata.tables))


def test_upsert_and_get_paper(store):
    store.upsert_paper(
        paper_id="paper_test1",
        file_hash="hashtest1",
        source_path="/tmp/x.pdf",
        title="T",
        year="2020",
    )
    got = store.get_paper_by_hash("hashtest1")
    assert got is not None and got.paper_id == "paper_test1"


def test_add_chunks(store):
    store.upsert_paper(paper_id="paper_c", file_hash="h_c", source_path="x")
    n = store.add_chunks(
        [
            {
                "chunk_id": "paper_c_c0000",
                "paper_id": "paper_c",
                "chunk_index": 0,
                "text": "hello",
                "char_count": 5,
                "token_estimate": 1,
                "embedded": 1,
            },
        ]
    )
    assert n == 1
    assert len(store.list_chunks("paper_c")) == 1
