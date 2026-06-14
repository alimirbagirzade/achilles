"""Detached LoRA eğitim başlatıcı + canlı durum/hazırlık tespiti.

Neden ayrı modül: web sunucusu (veya Claude Code) kapansa da eğitim sürmeli.
`training_manager` eğitimi web süreci içinde subprocess olarak çalıştırır →
web yeniden başlayınca/çökünce eğitim de ölür (storage/auto_lora_state.json'daki
"Eğitim COMPLETED olmadı" hataları bundandı). Bu modül eğitimi **detached** süreç
olarak başlatır: çıktılar log dosyalarına yazılır, ilerleme `training_status()`
tarafından log'dan okunur. start-train.ps1 ile aynı mekanik.

Veri kaynağı tek: `data/lora_sft/lora_sft.jsonl` (sentetik + kart birleşik, ~1266).
Başlatıcı her seferinde bunu train/valid'e böler → `DatasetBuilder` kaynaklı
clobber (train.jsonl'in 0'a düşmesi) başlatmada otomatik onarılır.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from app.config import get_settings

log = logging.getLogger(__name__)

# "HAZIR" rozetinin görünme eşiği (insan yine de tek tıkla onaylar — Kural 8).
MIN_READY_EXAMPLES = 200
# Determinist split (Kural 6) — lora-split ile aynı.
_SPLIT_SEED = 42
_VALID_RATIO = 0.05
# Log'a son yazımdan bu kadar dakika geçmediyse eğitim "canlı" sayılır.
# Yavaş CPU eğitiminde adım ~dakikalar sürer + log seyrek yazılabilir → 45 dk
# (tamamlanma zaten step>=total ile anında algılanır; bu yalnız ara boşluklar için).
_LIVE_LOG_AGE_MIN = 45.0
# Geçerli adapter adı (path traversal/CLI argüman güvenliği): yalnız harf/rakam/_/-.
_ADAPTER_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
# Çift-başlatma yarışını kapatan atomik kilit (log yazılmadan önceki pencere için).
_LAUNCH_LOCK_TTL = 120.0


def _launch_lock_path(root: Path) -> Path:
    return root / "storage" / ".training_launching"


def _acquire_launch_lock(root: Path) -> bool:
    """Atomik kilit al (O_EXCL). Eş-zamanlı ikinci başlatmayı engeller.

    Bayat kilit (> TTL) temizlenir; eğitim sürerken zaten log-tazeliği guard'ı
    (is_running) korur — bu kilit yalnız spawn ile ilk-log arasındaki pencere için.
    """
    lock = _launch_lock_path(root)
    lock.parent.mkdir(parents=True, exist_ok=True)
    if lock.exists() and (time.time() - lock.stat().st_mtime) > _LAUNCH_LOCK_TTL:
        with contextlib.suppress(Exception):
            lock.unlink()
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    try:
        os.write(fd, str(int(time.time())).encode())
    finally:
        os.close(fd)
    return True


def _release_launch_lock(root: Path) -> None:
    with contextlib.suppress(Exception):
        _launch_lock_path(root).unlink()


def _count_lines(path: Path) -> int:
    """Dosyadaki boş-olmayan satır sayısı (yoksa 0)."""
    if not path.exists():
        return 0
    try:
        return sum(1 for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip())
    except Exception:
        return 0


def _combined_source(settings) -> Path:
    return settings.root / "data" / "lora_sft" / "lora_sft.jsonl"


def ensure_train_split(settings=None) -> tuple[int, int]:
    """`lora_sft.jsonl` → `jsonl_dir/{train,valid}.jsonl` (determinist).

    Birleşik kaynak doluysa HER ZAMAN yeniden böler (clobber onarımı). Kaynak
    boş/yoksa mevcut train.jsonl'e dokunmaz. (n_train, n_valid) döndürür.
    """
    import random

    s = settings or get_settings()
    src = _combined_source(s)
    lines = (
        [ln for ln in src.read_text(encoding="utf-8").splitlines() if ln.strip()]
        if src.exists()
        else []
    )
    if not lines:
        # Kaynak yok → eldeki train/valid neyse onu say (bozma).
        return _count_lines(s.jsonl_dir / "train.jsonl"), _count_lines(s.jsonl_dir / "valid.jsonl")

    random.Random(_SPLIT_SEED).shuffle(lines)
    n_valid = max(1, int(len(lines) * _VALID_RATIO)) if len(lines) > 1 else 0
    valid, train = lines[:n_valid], lines[n_valid:]

    jd = s.jsonl_dir
    jd.mkdir(parents=True, exist_ok=True)
    (jd / "train.jsonl").write_text("\n".join(train) + ("\n" if train else ""), encoding="utf-8")
    (jd / "valid.jsonl").write_text("\n".join(valid) + ("\n" if valid else ""), encoding="utf-8")
    log.info("Eğitim verisi bölündü: train=%d valid=%d → %s", len(train), len(valid), jd)
    return len(train), len(valid)


def readiness(settings=None) -> dict:
    """Eğitime hazırlık: gerçek birleşik veri (lora_sft.jsonl) örnek sayısı."""
    s = settings or get_settings()
    n = _count_lines(_combined_source(s))
    if n == 0:  # kaynak yoksa eldeki bölünmüş train'i baz al
        n = _count_lines(s.jsonl_dir / "train.jsonl")
    ready = n >= MIN_READY_EXAMPLES
    if not n:
        label = "veri yok"
    elif ready:
        label = f"{n} örnek hazır"
    else:
        label = f"{n}/{MIN_READY_EXAMPLES} örnek"
    return {"ready": ready, "ready_examples": n, "ready_label": label}


def _detached_status(settings) -> dict | None:
    """Detached/CLI eğitimi log tazeliği + tqdm satırından algıla (yoksa None)."""
    s = settings
    logf = s.root / "logs" / "train-full-err.log"
    if not logf.exists():
        return None
    if (time.time() - logf.stat().st_mtime) / 60.0 >= _LIVE_LOG_AGE_MIN:
        return None
    try:
        txt = logf.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None
    # tqdm örn: "30/1203 [1:28:58<48:43:23, 149.53s/it]"
    m = re.findall(r"(\d+)/(\d+)\s*\[[^<\]]*<([^,\]]*)", txt)
    if not m:
        return None
    step, total, eta = int(m[-1][0]), int(m[-1][1]), m[-1][2].strip()
    if total <= 0 or step >= total:
        return None
    adapter = "LoRA"
    st = s.root / "storage" / "train_status.json"
    if st.exists():
        with contextlib.suppress(Exception):
            adapter = json.loads(st.read_text(encoding="utf-8")).get("adapter", "LoRA")
    return {
        "running": True,
        "source": "detached",
        "adapter": adapter,
        "step": step,
        "total": total,
        "pct": round(step * 100 / total, 1),
        "eta": eta,
    }


def training_status() -> dict:
    """Birleşik eğitim durumu (üst-bar rozeti + sekme için).

    Sıra: web (training_manager) → detached log → çalışmıyorsa hazırlık bilgisi.
    """
    s = get_settings()
    # 1) Web'den başlatılan (legacy in-process yol)
    try:
        from app.web.training_manager import get_training_manager

        prog = get_training_manager().progress
        state = getattr(getattr(prog, "state", None), "value", "")
        if state == "running":
            return {
                "running": True,
                "source": "web",
                "adapter": getattr(prog, "adapter_name", "LoRA"),
                "step": getattr(prog, "current_iter", 0),
                "total": getattr(prog, "total_iters", 0),
                "pct": round(getattr(prog, "pct", 0.0), 1),
                "eta": "",
            }
    except Exception:
        pass
    # 2) Detached/CLI eğitim
    det = _detached_status(s)
    if det:
        return det
    # 3) Çalışmıyor → hazırlık
    return {"running": False, **readiness(s)}


def is_running() -> bool:
    """Herhangi bir eğitim (web veya detached) canlı mı?"""
    return bool(training_status().get("running"))


def _find_achilles(root: Path) -> list[str] | None:
    """`achilles` konsol betiğini bul → komut öneki (yoksa uv run yedeği)."""
    exe = "achilles.exe" if os.name == "nt" else "achilles"
    # 1) Aktif venv (web sunucusunun python'ı) yanındaki Scripts/bin
    cand = Path(sys.executable).parent / exe
    if cand.exists():
        return [str(cand)]
    # 2) Proje .venv
    sub = "Scripts" if os.name == "nt" else "bin"
    cand2 = root / ".venv" / sub / exe
    if cand2.exists():
        return [str(cand2)]
    # 3) PATH
    found = shutil.which("achilles")
    if found:
        return [found]
    # 4) uv run yedeği
    uv = shutil.which("uv") or str(
        Path(os.environ.get("USERPROFILE", "")) / ".local" / "bin" / "uv.exe"
    )
    if uv and Path(uv).exists():
        return [uv, "run", "--project", str(root), "achilles"]
    return None


def launch(
    adapter_name: str = "achilles_lora",
    iterations: int = 0,
    dtype: str = "bf16",
    base_model: str | None = None,
) -> dict:
    """Eğitimi DETACHED başlat (web/terminal kapansa da sürer).

    - Veriyi `lora_sft.jsonl`'den yeniden böler (clobber-proof).
    - iterations<=0 → 1 epoch (train örnek sayısı kadar adım).
    - {ok, message, adapter} döndürür. Eğitimi GERÇEKTEN başlatır (Kural 8: bu
      çağrı yalnızca açık kullanıcı eylemiyle — buton/onay — tetiklenir).
    """
    s = get_settings()
    root = s.root

    # Adapter adı güvenliği (path traversal / CLI argüman): yalnız [A-Za-z0-9_-].
    if not _ADAPTER_RE.match(adapter_name or ""):
        return {
            "ok": False,
            "message": "Geçersiz adapter adı — yalnız harf, rakam, _ ve - (en çok 64).",
            "adapter": "",
        }

    if is_running():
        return {"ok": False, "message": "Zaten eğitim çalışıyor.", "adapter": ""}

    # Atomik kilit: iki eş-zamanlı istek (çift-tık/retry) çift süreç başlatmasın.
    if not _acquire_launch_lock(root):
        return {
            "ok": False,
            "message": "Eğitim şu an başlatılıyor — lütfen birkaç saniye bekle.",
            "adapter": "",
        }

    spawned = False
    try:
        n_train, _n_valid = ensure_train_split(s)
        if n_train <= 0:
            return {
                "ok": False,
                "message": (
                    "Eğitim verisi yok (lora_sft.jsonl boş). "
                    "Önce sentetik veri üret (synth-qa / lora-cloud-prep)."
                ),
                "adapter": "",
            }

        iters = iterations if iterations > 0 else n_train  # 1 epoch
        base = _find_achilles(root)
        if not base:
            return {
                "ok": False,
                "message": "achilles çalıştırıcısı bulunamadı (venv/uv yok).",
                "adapter": "",
            }

        cmd = [
            *base,
            "train",
            "--run",
            "--backend",
            "peft",
            "--adapter-name",
            adapter_name,
            "--iterations",
            str(iters),
        ]
        if base_model:
            cmd += ["--base-model", base_model]

        logs = root / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["ACHILLES_TRAIN_DTYPE"] = dtype

        popen_kwargs: dict = {"cwd": str(root), "env": env, "close_fds": True}
        if os.name == "nt":
            # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
            popen_kwargs["creationflags"] = 0x00000008 | 0x00000200 | 0x08000000
        else:
            popen_kwargs["start_new_session"] = True

        # Log dosyaları child sürece devredilir (with-bloğu kullanılamaz: Popen
        # detached çalışacağı için handle'lar spawn'dan sonra kapatılır).
        out_f = open(logs / "train-full.log", "ab")  # noqa: SIM115
        err_f = open(logs / "train-full-err.log", "ab")  # noqa: SIM115
        try:
            subprocess.Popen(cmd, stdout=out_f, stderr=err_f, **popen_kwargs)
        except (OSError, ValueError) as exc:
            log.exception("Detached eğitim başlatılamadı")
            return {
                "ok": False,
                "message": f"Eğitim başlatılamadı (süreç oluşturulamadı): {exc}",
                "adapter": "",
            }
        finally:
            out_f.close()
            err_f.close()

        (root / "storage").mkdir(parents=True, exist_ok=True)
        (root / "storage" / "train_status.json").write_text(
            json.dumps({"adapter": adapter_name, "dtype": dtype, "iterations": iters}),
            encoding="utf-8",
        )
        spawned = True
        log.info("Detached eğitim başlatıldı: %s (%d adım, dtype=%s)", adapter_name, iters, dtype)
        # Süreç spawn edildi; canlı kalıp kalmadığı üst-bar rozetinden/log'dan izlenir
        # (Kural 2: "başladı" değil "başlatıldı" + nereden doğrulanacağı belirtilir).
        return {
            "ok": True,
            "message": (
                f"Eğitim başlatıldı (detached): {adapter_name} — "
                f"{n_train} örnek, {iters} adım, {dtype}. "
                "İlerlemeyi üst-bar rozetinden izle."
            ),
            "adapter": adapter_name,
        }
    finally:
        # Spawn başarısızsa kilidi hemen bırak; başarılıysa TTL ile (log-tazeliği
        # guard'ı devralana kadar) tutulur.
        if not spawned:
            _release_launch_lock(root)
