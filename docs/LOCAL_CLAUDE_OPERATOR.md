# Local Claude Operator — Achilles otomasyon runbook'u (Phase 4E)

## Purpose
Achilles'te Claude otomasyonu **varsayılan olarak lokal Claude Code operatörüyle**
çalışır. GitHub Claude Action (cloud mode) **KAPALIDIR** ve bilinçli olarak kapalı
tutulur. Bu doküman lokal operatör çalışma modelini ve güvenli görev akışını tanımlar.

## Operating Model
- Claude Code **lokal terminalde** çalışır (cloud Action değil).
- Kullanıcı her görev için prompt verir.
- Claude yeni **branch/worktree** açar (izole çalışır).
- Testler **lokal** çalıştırılır (`ruff` · `format` · `mypy` · `pytest -m "not ollama"`).
- Commit **lokal** atılabilir (yalnız açık path ile; `git add -A` yasak).
- **Push / PR / merge tamamen kullanıcı kontrolündedir** — Claude bunları yapmaz.
- Achilles training / LoRA / adapter-terfi aksiyonları **approval gate + STOP_ALL**'a
  bağlıdır; web `/api/training/run` dahil her gerçek eğitim tek-kullanımlık taze onay ister.

## What is disabled (local-first kararı)
- **GitHub Claude Action** (cloud) — `claude-code-task.yml` `main`'de kalır ama inert.
- **`ENABLE_CLAUDE_TASK`** repo variable — set EDİLMEZ.
- **`ANTHROPIC_API_KEY`** GitHub secret — repoya EKLENMEZ.
- **Auto-merge** — yok.
- **Cloud / Kaggle / Colab training** — yok.

> GitHub Claude Action is intentionally disabled for local-first mode.
> Do not set ENABLE_CLAUDE_TASK unless cloud GitHub automation is explicitly desired.
> Local Claude Code operator is the default automation path.

## Safe local task flow
1. Kullanıcı görev prompt'u verir (örn. `tasks/local_dry_run_task.md`).
2. Claude yeni **branch/worktree** açar (`git worktree add ../<dir> -b <branch> <base>`).
3. Yalnız izin verilen dosyalarda kod/doküman değişikliği yapar.
4. **Protected-path guard** çalışır (`scripts/check_protected_paths.py`): korumalı yol
   değişiyorsa exit 2 → DUR.
5. `ruff check` · `ruff format --check` · `mypy app` · `pytest -m "not ollama"` çalışır.
6. Claude **final rapor** verir (değişen dosyalar + guard + CI sonucu).
7. Kullanıcı isterse push/PR yapar — Claude yapmaz.

## Local dry-run task (GitHub issue YERİNE)
GitHub issue açmak yerine lokal görev dosyası kullanılır:

```text
tasks/local_dry_run_task.md
```

Bu dosya **yalnız lokal test içindir; GitHub issue değildir.** İçeriği için o dosyaya bak.

## Emergency stop
- Gerçek training **çalıştırma** (`train --run`, LoRA, adapter promotion) — YOK.
- Tehlikeli bir aksiyon istenirse: **STOP_ALL aktif kalmalı** veya **taze onay**
  zorunlu olmalı (supervisor/approvals). Onaysız tehlikeli aksiyon başlamaz.
- Cloud action'lar kapalı kalır; `ENABLE_CLAUDE_TASK` set edilmez.
- Kontrol yüzeyi: Web UI → **AGENTS / OTOMASYON** sekmesi (STOP_ALL butonu + onaylar).
