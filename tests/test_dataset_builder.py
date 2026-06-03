"""DatasetBuilder birim testleri — çevrimdışı (in-memory SQLite)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from app.memory.sqlite_store import SqliteStore, TrainingExample
from app.training.dataset_builder import DatasetBuilder


def _make_store_with_examples(n: int) -> SqliteStore:
    tmp = tempfile.mkstemp(suffix=".db")[1]
    store = SqliteStore(db_path=tmp)
    with store.session() as s:
        for i in range(n):
            s.add(
                TrainingExample(
                    example_id=f"ex_{i:04d}",
                    source_paper_id=f"paper_{i % 3}",
                    example_type="summarize",
                    instruction=f"Instruction {i}",
                    input_text=f"Input {i}",
                    output_text=f"Output {i} (unique content to avoid dedup)",
                )
            )
    return store


def _builder_with_store(n: int, tmp_path: Path) -> DatasetBuilder:
    store = _make_store_with_examples(n)
    b = DatasetBuilder(store=store)
    b.settings = type("S", (), {"jsonl_dir": tmp_path})()  # type: ignore[assignment]
    return b


def test_empty_store_produces_empty_files(tmp_path: Path) -> None:
    b = _builder_with_store(0, tmp_path)
    r = b.build()
    assert r.n_train == 0
    assert r.n_valid == 0
    assert r.train_path.exists()


def test_few_examples_bootstrap_valid(tmp_path: Path) -> None:
    # 5 örnek < 8 → bootstrap: train=5, valid=min(4,5)=4 (kopyalama)
    b = _builder_with_store(5, tmp_path)
    r = b.build()
    assert r.n_train == 5
    assert r.n_valid == 4


def test_enough_examples_proper_split(tmp_path: Path) -> None:
    b = _builder_with_store(20, tmp_path)
    r = b.build(valid_ratio=0.15)
    assert r.n_valid >= 4
    assert r.n_train > 0
    assert r.n_train + r.n_valid == 20


def test_valid_set_min_4_enforced(tmp_path: Path) -> None:
    # 20 örnek, ratio=0.05 → int(20*0.05)=1 < 4 → min 4 olmalı
    b = _builder_with_store(20, tmp_path)
    r = b.build(valid_ratio=0.05)
    assert r.n_valid >= 4


def test_files_are_valid_jsonl(tmp_path: Path) -> None:
    b = _builder_with_store(15, tmp_path)
    r = b.build()
    with open(r.train_path, encoding="utf-8") as f:
        lines = [json.loads(line) for line in f if line.strip()]
    assert all("prompt" in rec and "completion" in rec for rec in lines)


def test_deduplication(tmp_path: Path) -> None:
    store = _make_store_with_examples(0)
    with store.session() as s:
        for i in range(3):
            s.add(
                TrainingExample(
                    example_id=f"dup_{i}",
                    source_paper_id="p1",
                    example_type="t",
                    instruction="Same",
                    input_text="Same",
                    output_text="Same",
                )
            )
    b = DatasetBuilder(store=store)
    b.settings = type("S", (), {"jsonl_dir": tmp_path})()  # type: ignore[assignment]
    records = b.collect()
    assert len(records) == 1  # 3 kopya → 1 unique


def test_deterministic_with_seed(tmp_path: Path) -> None:
    b = _builder_with_store(20, tmp_path)
    r1 = b.build(seed=42)
    r2 = b.build(seed=42)
    assert r1.content_hash == r2.content_hash


def test_content_hash_changes_with_different_data(tmp_path: Path) -> None:
    b1 = _builder_with_store(10, tmp_path / "a")
    b2 = _builder_with_store(15, tmp_path / "b")
    r1 = b1.build()
    r2 = b2.build()
    assert r1.content_hash != r2.content_hash
