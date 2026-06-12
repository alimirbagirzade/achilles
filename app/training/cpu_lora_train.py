"""CPU LoRA training launcher (Windows/Linux — NVIDIA/Apple GPU yok).

PyTorch + PEFT + transformers tabanlı. Apple Silicon (MLX) veya CUDA GPU
bulunmayan makinelerde LoRA eğitimini **CPU** üzerinde yapar. CPU'da pratik
süre için küçük taban model önerilir (ör. ``Qwen/Qwen2.5-0.5B-Instruct``).

``mlx_lora_train`` ile aynı sözleşme:
- Ağır eğitimi ASLA otomatik başlatmaz.
- Girdileri doğrular, planı yazdırır; yalnızca ``run()`` (CLI'da ``--run``)
  çağrılınca gerçekten eğitir.
- Gerçek run sonrası adapter'ı ``AdapterRegistry``'ye kaydeder.

Bu modül torch/transformers/peft kurulu olmayan makinelerde de **import
edilebilir**; ağır importlar yalnızca çalışma anında (run/eval) yapılır.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.training.adapter_registry import AdapterRegistry

# Eğitilecek LoRA hedef modülleri tüm linear katmanlar (Qwen/Llama uyumlu).
_TARGET_MODULES = "all-linear"


@dataclass
class CpuTrainConfig:
    base_model: str
    train_jsonl: Path
    valid_jsonl: Path
    adapter_output_path: Path
    epochs: float = 3.0
    grad_accum: int = 8  # efektif batch (CPU'da mikro-batch daima 1)
    learning_rate: float = 2e-4
    max_seq_len: int = 1024
    lora_r: int = 8
    lora_alpha: int = 16
    lora_dropout: float = 0.05
    seed: int = 13
    max_steps: int = 0  # >0 → epoch yerine adım sınırı (smoke test)


# --------------------------------------------------------------------------
# yardımcılar (torch gerektirmez)
# --------------------------------------------------------------------------
def _read_jsonl(path: Path) -> list[dict]:
    records: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def check_dependencies() -> list[str]:
    """Eksik ağır bağımlılıkları döndür (torch/transformers/peft)."""
    missing: list[str] = []
    for mod in ("torch", "transformers", "peft"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    return missing


def validate(cfg: CpuTrainConfig) -> list[str]:
    problems: list[str] = []
    if not cfg.train_jsonl.exists():
        problems.append(f"train_jsonl yok: {cfg.train_jsonl}")
    elif not _read_jsonl(cfg.train_jsonl):
        problems.append(f"train_jsonl boş: {cfg.train_jsonl}")
    if cfg.grad_accum < 1:
        problems.append("grad_accum >= 1 olmalı")
    if cfg.epochs <= 0 and cfg.max_steps <= 0:
        problems.append("epochs > 0 veya max_steps > 0 olmalı")
    return problems


def build_plan(cfg: CpuTrainConfig) -> str:
    n_train = len(_read_jsonl(cfg.train_jsonl)) if cfg.train_jsonl.exists() else 0
    n_valid = len(_read_jsonl(cfg.valid_jsonl)) if cfg.valid_jsonl.exists() else 0
    if cfg.max_steps > 0:
        steps = cfg.max_steps
    else:
        steps = max(1, math.ceil(n_train * cfg.epochs / cfg.grad_accum))
    missing = check_dependencies()
    dep_line = "tamam" if not missing else f"EKSİK → {', '.join(missing)} (uv add ile kur)"
    return (
        "CPU LoRA eğitim planı (PyTorch + PEFT)\n"
        f"  taban model     : {cfg.base_model}\n"
        f"  train / valid   : {n_train} / {n_valid} örnek\n"
        f"  epoch / accum   : {cfg.epochs} / {cfg.grad_accum} (efektif batch={cfg.grad_accum})\n"
        f"  optim adımı     : ~{steps}\n"
        f"  lr / r / alpha  : {cfg.learning_rate} / {cfg.lora_r} / {cfg.lora_alpha}\n"
        f"  max_seq_len     : {cfg.max_seq_len}\n"
        f"  adapter çıktısı : {cfg.adapter_output_path}\n"
        f"  bağımlılıklar   : {dep_line}\n"
        "  NOT: CPU eğitimi yavaştır; küçük model + az örnekle başlayın."
    )


# --------------------------------------------------------------------------
# tokenizasyon (torch gerektirir — yalnız run/eval içinde çağrılır)
# --------------------------------------------------------------------------
def _encode(
    tokenizer, prompt: str, completion: str, max_seq_len: int
) -> tuple[list[int], list[int]]:
    """prompt+completion'ı input_ids/labels'a çevir; prompt tokenları maskelenir."""
    if getattr(tokenizer, "chat_template", None):
        prompt_ids = tokenizer.apply_chat_template(
            [{"role": "user", "content": prompt}],
            add_generation_prompt=True,
            tokenize=True,
        )
    else:
        prompt_ids = tokenizer(prompt, add_special_tokens=True)["input_ids"]
    completion_ids = tokenizer(completion, add_special_tokens=False)["input_ids"]
    eos = [tokenizer.eos_token_id] if tokenizer.eos_token_id is not None else []
    input_ids = (prompt_ids + completion_ids + eos)[:max_seq_len]
    labels = ([-100] * len(prompt_ids) + completion_ids + eos)[:max_seq_len]
    return input_ids, labels


def run(
    cfg: CpuTrainConfig,
    *,
    content_hash: str | None = None,
    notes: str | None = None,
) -> dict:
    """Gerçek CPU LoRA eğitimi. Eğitim sonunda adapter kaydedilir."""
    missing = check_dependencies()
    if missing:
        raise RuntimeError(
            "Eksik bağımlılık: " + ", ".join(missing) + ". Kur: uv add torch transformers peft"
        )

    import torch
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer

    torch.manual_seed(cfg.seed)
    random.seed(cfg.seed)

    print(f"[1/5] Taban model yükleniyor (CPU, fp32): {cfg.base_model}")
    # Dinamik ML nesneleri (HF/PEFT) — tip denetimi için Any (get_peft_model
    # taban modeli sarmalar, mypy zinciri kopar).
    tokenizer: Any = AutoTokenizer.from_pretrained(cfg.base_model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model: Any = AutoModelForCausalLM.from_pretrained(cfg.base_model, torch_dtype=torch.float32)
    model.to("cpu")
    model.config.use_cache = False

    print("[2/5] LoRA adaptörü ekleniyor")
    lora = LoraConfig(
        r=cfg.lora_r,
        lora_alpha=cfg.lora_alpha,
        lora_dropout=cfg.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=_TARGET_MODULES,
    )
    model = get_peft_model(model, lora)
    model.print_trainable_parameters()
    model.train()

    print("[3/5] Veri kodlanıyor")
    train_records = _read_jsonl(cfg.train_jsonl)
    if not train_records:
        raise ValueError("train.jsonl boş — önce 'achilles dataset' çalıştırın.")
    encoded = [
        _encode(tokenizer, r.get("prompt", ""), r.get("completion", ""), cfg.max_seq_len)
        for r in train_records
    ]

    if cfg.max_steps > 0:
        total_steps = cfg.max_steps
    else:
        total_steps = max(1, math.ceil(len(encoded) * cfg.epochs / cfg.grad_accum))

    optimizer = torch.optim.AdamW(
        (p for p in model.parameters() if p.requires_grad), lr=cfg.learning_rate
    )
    trainable = [p for p in model.parameters() if p.requires_grad]

    print(f"[4/5] Eğitim başlıyor — hedef ~{total_steps} optim adımı")
    rng = random.Random(cfg.seed)
    optimizer.zero_grad()
    step = 0
    micro = 0
    running = 0.0
    last_train_loss = float("nan")
    done = False
    while not done:
        order = list(range(len(encoded)))
        rng.shuffle(order)
        for idx in order:
            input_ids, labels = encoded[idx]
            ii = torch.tensor([input_ids], dtype=torch.long)
            ll = torch.tensor([labels], dtype=torch.long)
            out = model(input_ids=ii, labels=ll)
            (out.loss / cfg.grad_accum).backward()
            running += float(out.loss.item())
            micro += 1
            if micro % cfg.grad_accum == 0:
                torch.nn.utils.clip_grad_norm_(trainable, 1.0)
                optimizer.step()
                optimizer.zero_grad()
                step += 1
                last_train_loss = running / cfg.grad_accum
                running = 0.0
                print(f"  step {step}/{total_steps} | train_loss {last_train_loss:.4f}")
                if step >= total_steps:
                    done = True
                    break

    # valid loss (varsa)
    val_loss = float("nan")
    valid_records = _read_jsonl(cfg.valid_jsonl) if cfg.valid_jsonl.exists() else []
    if valid_records:
        model.eval()
        with torch.no_grad():
            total = 0.0
            for r in valid_records:
                input_ids, labels = _encode(
                    tokenizer, r.get("prompt", ""), r.get("completion", ""), cfg.max_seq_len
                )
                ii = torch.tensor([input_ids], dtype=torch.long)
                ll = torch.tensor([labels], dtype=torch.long)
                total += float(model(input_ids=ii, labels=ll).loss.item())
            val_loss = total / len(valid_records)
        print(f"  valid_loss {val_loss:.4f}")

    print("[5/5] Adapter kaydediliyor")
    cfg.adapter_output_path.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(cfg.adapter_output_path))
    tokenizer.save_pretrained(str(cfg.adapter_output_path))
    AdapterRegistry().register(
        version=cfg.adapter_output_path.name,
        base_model=cfg.base_model,
        adapter_path=cfg.adapter_output_path,
        training_data_hash=content_hash,
        notes=notes or "CPU LoRA (PyTorch+PEFT)",
    )
    print(f"Adapter kaydedildi: {cfg.adapter_output_path}")
    return {
        "adapter_path": str(cfg.adapter_output_path),
        "steps": step,
        "train_loss": last_train_loss,
        "valid_loss": val_loss,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="CPU LoRA training launcher (PyTorch+PEFT)")
    p.add_argument("--base-model", required=True)
    p.add_argument("--train-jsonl", required=True, type=Path)
    p.add_argument("--valid-jsonl", required=True, type=Path)
    p.add_argument("--adapter-output-path", required=True, type=Path)
    p.add_argument("--epochs", type=float, default=3.0)
    p.add_argument("--grad-accum", type=int, default=8)
    p.add_argument("--learning-rate", type=float, default=2e-4)
    p.add_argument("--max-seq-len", type=int, default=1024)
    p.add_argument("--max-steps", type=int, default=0)
    p.add_argument("--run", action="store_true", help="gerçekten eğitimi başlat")
    args = p.parse_args(argv)

    cfg = CpuTrainConfig(
        base_model=args.base_model,
        train_jsonl=args.train_jsonl,
        valid_jsonl=args.valid_jsonl,
        adapter_output_path=args.adapter_output_path,
        epochs=args.epochs,
        grad_accum=args.grad_accum,
        learning_rate=args.learning_rate,
        max_seq_len=args.max_seq_len,
        max_steps=args.max_steps,
    )

    problems = validate(cfg)
    if problems:
        print("DOĞRULAMA HATALARI:")
        for pr in problems:
            print(f"  - {pr}")
        return 1

    if not args.run:
        print("[dry-run] (gerçek eğitim için --run ekleyin)\n" + build_plan(cfg))
        return 0

    run(cfg)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
