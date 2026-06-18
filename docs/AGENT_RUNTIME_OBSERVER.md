# Achilles — Agent Runtime Observer (tasarım + Phase 1 durumu)

Hedef: "hangi ajan, ne zaman başladı, ne yaptı, nerede düştü, hangi run_id" sorularını
yanıtlayan **gözlemlenebilir ve güvenli** bir temel. Bu belge tüm tasarımı anlatır ve
hangi parçanın **şimdi (Phase 1)** geldiğini, hangisinin **ertelendiğini (Phase 2+)** işaretler.

```
app/agents/runtime/
├── __init__.py     [Phase 1] public API
├── schemas.py      [Phase 1] AgentSpec / AgentRun / AgentEvent + enum'lar
├── registry.py     [Phase 1] automation_manifest.yaml okuyucu/sorgulayıcı
├── tracker.py      [Phase 1] koşu + olay kaydedici (SQLite + JSONL), @tracked
├── task_queue.py   [Phase 2] ❌ henüz yok
├── approvals.py    [Phase 2] ❌ henüz yok
└── supervisor.py   [Phase 2] ❌ henüz yok
```

## 1. Registry  ✅ Phase 1

`automation_manifest.yaml` → `dict[str, AgentSpec]`. Bozuk/eksik YAML'da **açık**
`ManifestError`. API: `load_agent_registry()`, `list_agents()`, `get_agent(id)`,
`dangerous_agents()`, `agents_requiring_approval()`.
Bu, ajanların tek bildirimsel kaynağıdır (kod değil, veri).

## 2. Tracker + run_id  ✅ Phase 1

Her ajan koşusu `start_run → log_event* → finish_run` yaşam döngüsünden geçer.
- `run_id` formatı: `arun_YYYYMMDD_HHMMSS_<8hex>` (benzersiz + okunur).
- Çift yazım: SQLite (`agent_runs`, `agent_events`) **ve** `reports/agent_runs/<run_id>.jsonl`.
- **Davranış değiştirmez, hata fırlatmaz**: tracking hatası sessizce yutulur, ajan akışı sürer.
- `{"ok": False}` dönen ajanlar (rag-loop, auto-lora) `failed` olarak işaretlenir.

Sarmalama yolları:
- `@tracked("agent-id", trigger_type=...)` — async-farkında dekoratör (hafif; mevcut 4 ajanda).
- `with track_agent_run("agent-id") as run:` — elle blok sarmalama.
- `log_step("...")` — mevcut (context) koşuya ara-adım olayı.

**Phase 1'de sarılan ajanlar:** `rag-learning-loop` (run_one_cycle), `auto-lora-pipeline`
(check_and_prepare), `research-orchestrator` (run), `arxiv-fetcher` (fetch_arxiv_papers).

## 3. Event log  ✅ Phase 1

`AgentEvent{event_id, run_id, ts, kind, level, message, payload}`. `kind ∈ {start, step,
info, output, warning, error, finish}`. SQLite + JSONL'e yazılır.
**Retention (kullanıcı kararı): 30 gün VEYA en çok 50.000 son olay** —
`SqliteStore.prune_agent_events` her `finish_run`'da (savunmacı) çağrılır.
JSONL dosyaları şimdilik budanmaz (Phase 2 notu).

## 4. Görüntüleme  ✅ Phase 1 (salt-okuma)

- CLI: `achilles agents-list`, `agents-runs [--limit --agent --status]`, `agents-log <run_id>`.
- Web (salt-okuma): `GET /api/agents`, `GET /api/agents/runs`, `GET /api/agents/runs/{run_id}`.
- Dashboard: mevcut Achilles Web UI'a **ileride** "Agents" sekmesi (ayrı uygulama YOK — kullanıcı kararı).

## 5. Task queue  ❌ Phase 2

`automation_tasks` tablosu + enqueue/claim/complete. Windows Task Scheduler şimdilik
dış cron olarak kalır; Achilles önce bu görevleri **izler**, sonra zamanlamayı içeri taşır.

## 6. Approvals  ❌ Phase 2

`approval_requests` tablosu + `request/approve/reject`. Tehlikeli adımlar (gerçek eğitim,
adapter terfisi, rules-updater uygula) **bloke** edilip insan onayı bekler.
Kullanıcı kararı: **`train --run` her zaman ayrı manuel onay** (otomatik tam-otonomi YOK).

## 7. Supervisor  ❌ Phase 2

Tehlikeli ajanları başlatabilen TEK nokta; `approval_requests` + global `STOP_ALL`
kill-switch'i uygular. Ayrıca **detached eğitim durdurma** açığını giderir
(`/api/training/stop` şu an detached koşuyu durduramıyor).

## 8. GitHub + Claude Code automation  ❌ sonraki faz (Phase 4)

Şimdilik KAPALI (kullanıcı kararı: önce runtime'ı lokalde kanıtla). İleride:
etiketli issue → Claude Code branch → CI kapısı → PR (asla `main`'e push / auto-merge yok,
`data/storage/models` asla dokunulmaz). CI (`ci.yml`) zaten mevcut ve test kapısı olarak kullanılır.

---

### Phase 1 kapsam özeti

| Bileşen | Durum |
|---------|-------|
| schemas / registry / tracker | ✅ yapıldı (Phase 1) |
| SQLite `agent_runs` + `agent_events` (+ retention) | ✅ yapıldı (Phase 1) |
| 4 ajan hafif sarmalama (davranış değişmeden) | ✅ yapıldı (Phase 1) |
| CLI agents-list/runs/log | ✅ yapıldı (Phase 1) |
| Web GET /api/agents[/runs[/{id}]] | ✅ yapıldı (Phase 1) |
| task_queue (`automation_tasks`) | ✅ yapıldı (Phase 2) |
| approvals (`approval_requests`, tek kullanımlık taze onay) | ✅ yapıldı (Phase 2) |
| supervisor + STOP_ALL kill-switch | ✅ yapıldı (Phase 2) |
| detached training stop fix (pid + STOP_TRAINING) | ✅ yapıldı (Phase 2) |
| startup sweep (bayat running → cancelled) | ✅ yapıldı (Phase 2) |
| tehlikeli aksiyon entegrasyonu (train/promote/rules) | ✅ yapıldı (Phase 2) |
| CLI task/approval/stop-all + web /automation,/approvals,/events,/healthz,/supervisor | ✅ yapıldı (Phase 2) |
| dashboard sekmesi (mevcut Web UI içinde) | ❌ Phase 3 |
| GitHub Claude Code PR automation | ❌ Phase 4 |

## Phase 2 API yüzeyi (özet)

**Yeni SQLite tabloları:** `automation_tasks`, `approval_requests`.

**Yeni CLI:** `task-create`, `tasks-list`, `task-cancel`, `approvals-list`,
`approval-approve`, `approval-reject`, `stop-all`, `clear-stop-all`.

**Yeni web (api_auth korumalı):** `GET/POST /api/automation/tasks`,
`POST /api/automation/tasks/{id}/cancel`, `GET /api/approvals`,
`POST /api/approvals/{id}/approve|reject`, `GET /api/events`, `GET /api/healthz`,
`POST /api/supervisor/stop-all`, `POST /api/supervisor/clear-stop-all`,
`GET /api/supervisor/status` + `/api/training/stop` artık detached'i de durdurur.

**Politika:** her gerçek eğitim ve her adapter terfisi AYRI manuel onay ister
(tek kullanımlık taze onay; standing yetki yok). STOP_ALL tüm tehlikeli aksiyonları bloklar.
Tam otomasyon hâlâ kapalı; GitHub PR otomasyonu Phase 4'e kadar kapalı; dashboard Phase 3'te.
