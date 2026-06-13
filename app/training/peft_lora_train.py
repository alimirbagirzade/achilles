"""PEFT-based LoRA trainer for Windows and Linux (CPU or CUDA).

Apple Silicon icin mlx_lora_train.py kullanin.
Bu modul Windows AMD64 ve Linux (CPU veya CUDA GPU) icin calisir.

Baslatma: yalnizca --run parametresiyle gercek egitim yapilir (dry-run varsayilan).
"""

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# NOT: HF 'datasets' kütüphanesi kullanılmaz — proje kökündeki yerel 'datasets/'
# klasörü onu gölgeler (ImportError). Tokenizasyon düz Python ile yapılır.
REQUIRED_PACKAGES = ["torch", "transformers", "peft"]


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
    # Dinamik padding ile maliyet gerçek uzunluğa bağlı; 1024 sessiz kırpılmayı önler.
    # RAFT (golden+distractor bağlam) verisine geçişte 2048'e çıkarılmalı.
    max_seq_length: int = 1024


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


def _row_to_messages(row: dict) -> list[dict]:
    """Satırı chat mesaj listesine çevir (messages > system/user/assistant > text)."""
    if "messages" in row:
        return [m for m in row["messages"] if m.get("content")]
    msgs = []
    for role in ("system", "user", "assistant"):
        if row.get(role):
            msgs.append({"role": role, "content": row[role]})
    if msgs:
        return msgs
    if row.get("text"):
        return [{"role": "user", "content": row["text"]}]
    return []


def _row_to_text(row: dict) -> str:
    """Yedek düz-metin formatı (yalnız chat template yoksa kullanılır)."""
    if "text" in row:
        return row["text"]
    return "\n".join(f"<|{m['role']}|>{m['content']}<|end|>" for m in _row_to_messages(row))


def train(cfg: PeftTrainConfig) -> dict:
    missing = _check_deps()
    if missing:
        return {
            "ok": False,
            "error": f"Eksik paketler: {missing}. Kur: uv pip install {' '.join(missing)}",
        }

    import torch
    from peft import LoraConfig, TaskType, get_peft_model
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        DataCollatorForLanguageModeling,
        Trainer,
        TrainingArguments,
    )

    device = "cuda" if torch.cuda.is_available() else "cpu"
    # CPU base dtype: fp32 (varsayılan, kararlı) veya bf16 (ACHILLES_TRAIN_DTYPE=bf16).
    # bf16: model 16→8GB, bellek trafiği yarı → bellek-bağımlı CPU'da potansiyel ~2×.
    # Uyarı: AVX512-BF16'sız CPU'da (örn. Tiger Lake) bf16 emüle edilir; önce ölç.
    _want_bf16 = os.environ.get("ACHILLES_TRAIN_DTYPE", "fp32") == "bf16"
    cpu_dtype = torch.bfloat16 if _want_bf16 else torch.float32
    dtype = torch.float16 if device == "cuda" else cpu_dtype
    logger.info("PEFT LoRA egitimi basladi. Cihaz: %s, dtype: %s", device, dtype)

    tokenizer = AutoTokenizer.from_pretrained(cfg.base_model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        cfg.base_model,
        trust_remote_code=True,
        torch_dtype=dtype,
        device_map="auto" if device == "cuda" else None,
    )

    # target_modules AÇIKÇA sınırlı: Qwen3 tied-embeddings kullanır; lm_head/embed
    # deltaları GGUF dönüşümünde sessizce atlanır ve adapter bozulur. Yalnız
    # attention + MLP projeksiyonları hedeflenir (Ollama/llama.cpp uyumlu).
    peft_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=cfg.lora_r,
        lora_alpha=cfg.lora_alpha,
        lora_dropout=cfg.lora_dropout,
        bias="none",
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
    )
    model = get_peft_model(model, peft_config)  # type: ignore[assignment]
    model.print_trainable_parameters()  # type: ignore[operator]

    train_rows = _load_jsonl(cfg.train_jsonl)

    def _render(r: dict) -> str:
        # Modelin GERÇEK chat şablonu kullanılır (eğitim ↔ çıkarım format eşleşmesi
        # şart; uydurma <|role|> formatı adapter'ı sessizce bozar). Şablon yoksa
        # düz-metin yedeğe düşülür.
        msgs = _row_to_messages(r)
        if msgs and getattr(tokenizer, "chat_template", None):
            try:
                return str(tokenizer.apply_chat_template(msgs, tokenize=False))
            except Exception:
                pass
        return _row_to_text(r).strip()

    def _tokenize(rows: list[dict]) -> list[dict]:
        # Her metni TEK TEK tokenize et (batch yolu transformers'ta overflow
        # edge-case'inde IndexError verebiliyor). Boş örnekleri atla.
        # HIZ: padding YOK — collator dinamik doldurur (batch=1 → sıfır padding,
        # her adım yalnız gerçek token sayısını işler; 512'ye doldurmaktan ~%40 hızlı).
        out: list[dict] = []
        for r in rows:
            text = _render(r)
            if not text:
                continue
            enc = tokenizer(text, truncation=True, max_length=cfg.max_seq_length)
            out.append({"input_ids": enc["input_ids"], "attention_mask": enc["attention_mask"]})
        return out

    # HF Dataset yerine düz liste — Trainer indekslenebilir/sized her şeyi kabul eder.
    train_ds = _tokenize(train_rows)
    if not train_ds:
        return {"ok": False, "error": "Eğitim verisi boş (tokenize sonrası 0 örnek)."}

    steps_per_epoch = max(1, len(train_ds) // cfg.batch_size)
    num_epochs = max(1, cfg.iterations // steps_per_epoch)

    output_dir = str(cfg.adapter_output_path)
    # HIZ ayarları (CPU): eval kapalı (epoch başına ~35sn tasarruf), tek checkpoint,
    # pin_memory kapalı (GPU yok), dinamik padding collator'da.
    args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=num_epochs,
        per_device_train_batch_size=cfg.batch_size,
        learning_rate=cfg.learning_rate,
        fp16=(device == "cuda"),
        logging_steps=5,
        save_strategy="epoch",
        save_total_limit=1,
        eval_strategy="no",
        report_to="none",
        dataloader_pin_memory=False,
    )

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=train_ds,
        data_collator=DataCollatorForLanguageModeling(tokenizer, mlm=False),
    )

    import datetime as _dt

    started_at = _dt.datetime.now().isoformat(timespec="seconds")
    trainer.train()
    finished_at = _dt.datetime.now().isoformat(timespec="seconds")
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)

    # Loss eğrisini reports/training/<adapter>_loss.json'a yaz → web "Eğitim grafiği"
    # bu dosyaları okur (/api/learning/training-runs). CLI eğitimi de artık kaydeder.
    _write_loss_curve(cfg, trainer.state.log_history, started_at, finished_at)

    logger.info("Adapter kaydedildi: %s", output_dir)
    return {"ok": True, "adapter_path": output_dir, "device": device}


def _write_loss_curve(
    cfg: PeftTrainConfig, log_history: list[dict], started_at: str, finished_at: str
) -> None:
    """Trainer log_history'den loss eğrisi çıkar; web grafiğinin okuduğu JSON'u yaz."""
    curve: list[dict] = []
    for entry in log_history:
        if "loss" in entry:  # eğitim loss'u (logging_steps'te)
            curve.append(
                {
                    "step": int(entry.get("step", len(curve) + 1)),
                    "train_loss": round(float(entry["loss"]), 4),
                    "val_loss": (
                        round(float(entry["eval_loss"]), 4) if "eval_loss" in entry else None
                    ),
                }
            )
    report = {
        "adapter_name": cfg.adapter_output_path.name,
        "started_at": started_at,
        "finished_at": finished_at,
        "total_iters": cfg.iterations,
        "base_model": cfg.base_model,
        "curve": curve,
    }
    out_dir = Path("reports/training")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{cfg.adapter_output_path.name}_loss.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def generate_colab_notebook(
    cfg: PeftTrainConfig,
    out_path: Path,
    *,
    hf_dataset_repo: str = "KULLANICI/achilles-lora-sft",
    num_epochs: int = 2,
) -> Path:
    """Stage 2 bulut-GPU (Kaggle/Colab) eğitim notebook'u + Ollama Modelfile üretir.

    Doğrulanmış unsloth şablonunu (Qwen3-4B-Instruct-2507 → GGUF Q4_K_M → Ollama)
    `app/training/cloud_notebook.py` üzerinden doldurur. Eski düz-transformers
    notebook'u (5 bilinen hata: target_modules eksik, {messages} okunmuyor, uydurma
    chat formatı, padding='max_length', GGUF export yok) tamamen değiştirildi.
    Detay: docs/PROTOKOL_BULUT_EGITIM.md.
    """
    from app.training.cloud_notebook import build_stage2_notebook, write_modelfile

    build_stage2_notebook(
        base_model=cfg.base_model,
        adapter_name=cfg.adapter_output_path.name,
        hf_dataset_repo=hf_dataset_repo,
        max_seq_length=cfg.max_seq_length,
        lora_r=cfg.lora_r,
        learning_rate=cfg.learning_rate,
        num_epochs=num_epochs,
        out_path=out_path,
    )
    write_modelfile(out_path.parent)
    logger.info("Stage 2 bulut notebook + Modelfile olusturuldu: %s", out_path)
    return out_path


def build_command(cfg: PeftTrainConfig) -> list[str]:
    """TrainingManager.start() için subprocess komutu üretir."""
    return [
        sys.executable,
        str(Path(__file__).resolve()),
        "--train",
        str(cfg.train_jsonl),
        "--valid",
        str(cfg.valid_jsonl),
        "--output",
        str(cfg.adapter_output_path),
        "--model",
        cfg.base_model,
        "--iters",
        str(cfg.iterations),
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
