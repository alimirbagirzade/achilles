"""PEFT-based LoRA trainer for Windows and Linux (CPU or CUDA).

Apple Silicon icin mlx_lora_train.py kullanin.
Bu modul Windows AMD64 ve Linux (CPU veya CUDA GPU) icin calisir.

Baslatma: yalnizca --run parametresiyle gercek egitim yapilir (dry-run varsayilan).
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

REQUIRED_PACKAGES = ["torch", "transformers", "peft", "datasets"]


@dataclass
class PeftTrainConfig:
    base_model: str
    train_jsonl: Path
    valid_jsonl: Path
    adapter_output_path: Path
    iterations: int = 300
    batch_size: int = 1
    learning_rate: float = 2e-4
    lora_r: int = 8
    lora_alpha: int = 16
    lora_dropout: float = 0.05
    max_seq_length: int = 512


def _check_deps() -> list[str]:
    missing = []
    for pkg in REQUIRED_PACKAGES:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    return missing


def dry_run(cfg: PeftTrainConfig) -> dict:
    missing = _check_deps()
    return {
        "dry_run": True,
        "base_model": cfg.base_model,
        "train_jsonl": str(cfg.train_jsonl),
        "valid_jsonl": str(cfg.valid_jsonl),
        "adapter_output": str(cfg.adapter_output_path),
        "iterations": cfg.iterations,
        "missing_packages": missing,
        "install_cmd": f"uv pip install {' '.join(missing)}" if missing else None,
    }


def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _row_to_text(row: dict) -> str:
    if "text" in row:
        return row["text"]
    parts = []
    if row.get("system"):
        parts.append(f"<|system|>{row['system']}<|end|>")
    if row.get("user"):
        parts.append(f"<|user|>{row['user']}<|end|>")
    if row.get("assistant"):
        parts.append(f"<|assistant|>{row['assistant']}<|end|>")
    return "\n".join(parts)


def train(cfg: PeftTrainConfig) -> dict:
    missing = _check_deps()
    if missing:
        return {
            "ok": False,
            "error": f"Eksik paketler: {missing}. Kur: uv pip install {' '.join(missing)}",
        }

    import torch
    from datasets import Dataset
    from peft import LoraConfig, TaskType, get_peft_model
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        DataCollatorForLanguageModeling,
        Trainer,
        TrainingArguments,
    )

    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info("PEFT LoRA egitimi basladi. Cihaz: %s", device)

    tokenizer = AutoTokenizer.from_pretrained(cfg.base_model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        cfg.base_model,
        trust_remote_code=True,
        torch_dtype=torch.float16 if device == "cuda" else torch.float32,
        device_map="auto" if device == "cuda" else None,
    )

    peft_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=cfg.lora_r,
        lora_alpha=cfg.lora_alpha,
        lora_dropout=cfg.lora_dropout,
        bias="none",
    )
    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()

    train_rows = _load_jsonl(cfg.train_jsonl)
    valid_rows = _load_jsonl(cfg.valid_jsonl)

    def tokenize(examples):
        return tokenizer(
            examples["text"],
            truncation=True,
            max_length=cfg.max_seq_length,
            padding="max_length",
        )

    train_ds = Dataset.from_list([{"text": _row_to_text(r)} for r in train_rows])
    valid_ds = Dataset.from_list([{"text": _row_to_text(r)} for r in valid_rows])
    train_ds = train_ds.map(tokenize, batched=True, remove_columns=["text"])
    valid_ds = valid_ds.map(tokenize, batched=True, remove_columns=["text"])

    steps_per_epoch = max(1, len(train_ds) // cfg.batch_size)
    num_epochs = max(1, cfg.iterations // steps_per_epoch)

    output_dir = str(cfg.adapter_output_path)
    args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=num_epochs,
        per_device_train_batch_size=cfg.batch_size,
        learning_rate=cfg.learning_rate,
        fp16=(device == "cuda"),
        logging_steps=10,
        save_strategy="epoch",
        eval_strategy="epoch",
        load_best_model_at_end=True,
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=train_ds,
        eval_dataset=valid_ds,
        data_collator=DataCollatorForLanguageModeling(tokenizer, mlm=False),
    )

    trainer.train()
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)

    logger.info("Adapter kaydedildi: %s", output_dir)
    return {"ok": True, "adapter_path": output_dir, "device": device}


def generate_colab_notebook(cfg: PeftTrainConfig, out_path: Path) -> Path:
    """Kullanici Google Colab'da calistirabilecegi bir .ipynb olusturur."""
    cells = [
        {
            "cell_type": "markdown",
            "source": [
                "# Achilles LoRA Egitimi - Google Colab\n",
                "T4 GPU ile ~30 dakikada tamamlanir. Runtime > Run All ile calistirin.\n",
            ],
        },
        {
            "cell_type": "code",
            "source": ["!pip install -q peft transformers datasets accelerate\n"],
        },
        {
            "cell_type": "code",
            "source": [
                "import json, pathlib\n",
                f"BASE_MODEL = '{cfg.base_model}'\n",
                f"ADAPTER_NAME = '{cfg.adapter_output_path.name}'\n",
                f"MAX_SEQ_LEN = {cfg.max_seq_length}\n",
                f"LORA_R = {cfg.lora_r}\n",
                f"LEARNING_RATE = {cfg.learning_rate}\n",
                f"NUM_EPOCHS = {max(1, cfg.iterations // 10)}\n",
            ],
        },
        {
            "cell_type": "code",
            "source": [
                "# Egitim verisini buraya kopyalayin veya Drive'dan yukleyin\n",
                "TRAIN_DATA = []\n",
                "VALID_DATA = []\n",
                "# Ornek: [{\"text\": \"<|user|>soru<|end|>\\n<|assistant|>cevap<|end|>\"}]\n",
            ],
        },
        {
            "cell_type": "code",
            "source": [
                "import torch\n",
                "from datasets import Dataset\n",
                "from peft import LoraConfig, TaskType, get_peft_model\n",
                "from transformers import (\n",
                "    AutoModelForCausalLM, AutoTokenizer,\n",
                "    DataCollatorForLanguageModeling, Trainer, TrainingArguments\n",
                ")\n",
                "tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)\n",
                "if tokenizer.pad_token is None:\n",
                "    tokenizer.pad_token = tokenizer.eos_token\n",
                "model = AutoModelForCausalLM.from_pretrained(\n",
                "    BASE_MODEL, trust_remote_code=True,\n",
                "    torch_dtype=torch.float16, device_map='auto'\n",
                ")\n",
                "peft_cfg = LoraConfig(\n",
                "    task_type=TaskType.CAUSAL_LM, r=LORA_R,\n",
                "    lora_alpha=LORA_R*2, lora_dropout=0.05, bias='none'\n",
                ")\n",
                "model = get_peft_model(model, peft_cfg)\n",
                "model.print_trainable_parameters()\n",
                "def tokenize(ex):\n",
                "    return tokenizer(ex['text'], truncation=True,\n",
                "                      max_length=MAX_SEQ_LEN, padding='max_length')\n",
                "train_ds = Dataset.from_list(TRAIN_DATA).map(tokenize, batched=True, remove_columns=['text'])\n",
                "valid_ds = Dataset.from_list(VALID_DATA).map(tokenize, batched=True, remove_columns=['text'])\n",
                "args = TrainingArguments(\n",
                "    output_dir=ADAPTER_NAME, num_train_epochs=NUM_EPOCHS,\n",
                "    per_device_train_batch_size=4, learning_rate=LEARNING_RATE,\n",
                "    fp16=True, logging_steps=5, save_strategy='epoch',\n",
                "    eval_strategy='epoch', report_to='none'\n",
                ")\n",
                "trainer = Trainer(\n",
                "    model=model, args=args,\n",
                "    train_dataset=train_ds, eval_dataset=valid_ds,\n",
                "    data_collator=DataCollatorForLanguageModeling(tokenizer, mlm=False)\n",
                ")\n",
                "trainer.train()\n",
                "model.save_pretrained(ADAPTER_NAME)\n",
                "tokenizer.save_pretrained(ADAPTER_NAME)\n",
                "print('Adapter kaydedildi:', ADAPTER_NAME)\n",
            ],
        },
    ]

    notebook = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}
        },
        "cells": [
            {
                **c,
                "metadata": {},
                "id": f"cell_{i}",
                "outputs": [],
                "execution_count": None,
            }
            if c["cell_type"] == "code"
            else {**c, "metadata": {}, "id": f"cell_{i}"}
            for i, c in enumerate(cells)
        ],
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(notebook, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Colab notebook olusturuldu: %s", out_path)
    return out_path


def build_command(cfg: PeftTrainConfig) -> list[str]:
    """TrainingManager.start() için subprocess komutu üretir."""
    return [
        sys.executable,
        str(Path(__file__).resolve()),
        "--train", str(cfg.train_jsonl),
        "--valid", str(cfg.valid_jsonl),
        "--output", str(cfg.adapter_output_path),
        "--model", cfg.base_model,
        "--iters", str(cfg.iterations),
        "--run",
    ]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="PEFT LoRA trainer (Windows/Linux)")
    parser.add_argument("--model", default="Qwen/Qwen2.5-1.5B-Instruct")
    parser.add_argument("--train", required=True)
    parser.add_argument("--valid", required=True)
    parser.add_argument("--output", default="models/adapters/achilles_lora_peft")
    parser.add_argument("--iters", type=int, default=300)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--colab", action="store_true")
    parsed = parser.parse_args()

    cfg = PeftTrainConfig(
        base_model=parsed.model,
        train_jsonl=Path(parsed.train),
        valid_jsonl=Path(parsed.valid),
        adapter_output_path=Path(parsed.output),
        iterations=parsed.iters,
    )

    if parsed.colab:
        nb = generate_colab_notebook(cfg, Path(parsed.output) / "achilles_colab.ipynb")
        print(f"Colab notebook: {nb}")
        sys.exit(0)

    if not parsed.run:
        result = dry_run(cfg)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result["missing_packages"]:
            print(f"\nKur: {result['install_cmd']}")
        sys.exit(0)

    result = train(cfg)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result.get("ok") else 1)
