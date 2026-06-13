"""Stage 2 bulut-GPU eğitim notebook'u + Ollama Modelfile üretici.

Doğrulanmış unsloth (Qwen3-4B-Instruct-2507 → GGUF Q4_K_M → Ollama) şablonunu
`templates/` altından okur, dinamik değerleri doldurur ve kullanıcının Kaggle/Colab'da
çalıştırabileceği bir `.ipynb` + `Modelfile` yazar.

Şablon, 4-ajan araştırmasıyla doğrulandı (5 bilinen hata düzeltildi: target_modules,
{messages} formatı, apply_chat_template, dinamik padding, GGUF/Ollama export). Detay:
docs/PROTOKOL_BULUT_EGITIM.md. Bu modül EĞİTİM BAŞLATMAZ; yalnız notebook üretir
(CLAUDE.md kural 8 — gerçek eğitim bulutta, kullanıcı tarafından, açıkça).
"""

from __future__ import annotations

import shutil
from pathlib import Path

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
_NOTEBOOK_TEMPLATE = _TEMPLATE_DIR / "stage2_lora_colab.ipynb"
_MODELFILE_TEMPLATE = _TEMPLATE_DIR / "Modelfile.stage2"


def build_stage2_notebook(
    *,
    base_model: str,
    adapter_name: str,
    hf_dataset_repo: str,
    max_seq_length: int,
    lora_r: int,
    learning_rate: float,
    num_epochs: int,
    out_path: Path,
) -> Path:
    """Doğrulanmış Stage 2 notebook şablonunu doldurup `out_path`'e yaz.

    Placeholder değerleri JSON-güvenli düz metindir (model adı/sayı), JSON yapısını
    bozmaz. HF_DATASET_REPO'yu kullanıcı kendi HF kullanıcı adıyla doldurmalı.
    """
    template = _NOTEBOOK_TEMPLATE.read_text(encoding="utf-8")
    replacements = {
        "{BASE_MODEL}": base_model,
        "{ADAPTER_NAME}": adapter_name,
        "{HF_DATASET_REPO}": hf_dataset_repo,
        "{MAX_SEQ_LEN}": str(max_seq_length),
        "{LORA_R}": str(lora_r),
        "{LEARNING_RATE}": str(learning_rate),
        "{NUM_EPOCHS}": str(num_epochs),
    }
    for key, value in replacements.items():
        template = template.replace(key, value)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(template, encoding="utf-8")
    return out_path


def write_modelfile(out_dir: Path) -> Path:
    """Ollama Modelfile şablonunu `out_dir/Modelfile` olarak kopyala.

    İndirilen GGUF ile aynı klasöre konmalı (FROM yolu görelidir:
    `./achilles-Q4_K_M.gguf`).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / "Modelfile"
    shutil.copyfile(_MODELFILE_TEMPLATE, dest)
    return dest
