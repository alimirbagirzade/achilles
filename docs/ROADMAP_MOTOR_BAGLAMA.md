# ROADMAP — Yerel Motor Bağlama & Tek-Tık RUN

_Oluşturma: 2026-07-21 · Kaynak oturum: `claude/local-system-research-ed8535` (araştırma, kod yazılmadı)_

## Amaç

Kullanıcı Achilles'i yerelde açar, **RUN**'a basar; makinede kurulu ve **aboneliğiyle
girişli** bir motor (Claude Code / Codex / Gemini CLI) alt-süreç olarak doğar, MCP
üzerinden Achilles'in ajanlarını sürer. Eğitim, Kural-8 taze insan onayında durur.

**API anahtarı YOK** — motorlar kendi CLI oturumlarını kullanır. Achilles hiçbir
kimlik bilgisi toplamaz, saklamaz, göstermez.

## Mevcut durum (2026-07-21 taraması)

| Parça | Durum | Konum |
|---|---|---|
| MCP sunucusu (OpenAPI→tool proxy) | ✅ var | `mcp_server/achilles_mcp.py` |
| `claude -p` alt-süreç sürücüsü | ✅ var, salt-rapor | `app/orchestration/driver.py:37,56,78` |
| Autodrive ucu | ✅ var, `execute=false` kilidi | `app/web/orchestration_routes.py:132` |
| Onay kapısı + taze onay TTL | ✅ var | `app/agents/runtime/approvals.py:162` |
| STOP_ALL kill-switch | ✅ var | `app/agents/runtime/supervisor.py:70` |
| Çok-sağlayıcılı LLM katmanı | ✅ var | `app/brain/local_llm.py:27` |
| ⚡ RUN butonu | 🟡 dry-run | 15·AJAN HARİTASI sekmesi |
| **Onay/kill-switch izolasyonu** | ❌ **YOK — bloklayıcı** | aşağıda P1 |
| Motor kayıt tablosu (çok motor) | ✅ **P2 TAMAM** (PR #112) | `app/orchestration/engines.py` |
| Sür-modu prompt | ❌ yok (yalnız av-modu) | P3 |
| MCP allow-list + token iletimi | ❌ yok | P4 |

## 🔴 Bloklayıcı güvenlik açığı (P1'in gerekçesi)

Bugün RUN açılırsa: doğan motor, Achilles API'sine **insanla aynı yetkiyle** erişir.
Yani kendi eğitimini kendisi onaylayabilir (`POST /api/approvals/{id}/approve`) ve
kill-switch'i temizleyebilir (`POST /api/supervisor/clear-stop-all`).
Üstelik `api_token` varsayılan boş → doğrulama tümüyle atlanıyor
(`app/web/security.py:66`). **Kural-8 bu kurulumda kâğıt üstünde kalır.**

Çözüm: iki kimlik. Sürücü motoruna verilen kimlik onay/stop-all uçlarını *görmez*;
onay yalnız insan yüzeyinden (UI / CLI) gelir.

---

## Faz planı ve paralellik

```
        ┌──────────────── ŞERİT A (güvenlik) ────────────────┐
Faz 0 → │ P1 onay izolasyonu → P4 MCP allow-list + token     │ ┐
        └────────────────────────────────────────────────────┘ ├→ P5 UI/RUN → P6 kapanış
        ┌──────────────── ŞERİT B (motor) ───────────────────┐ │
        │ P2 motor tablosu → P3 sür-modu prompt + MCP geçişi │ ┘
        └────────────────────────────────────────────────────┘
```

- **P1 ve P2 aynı anda başlatılabilir** (farklı dosyalar, çakışma yok).
- **P4, P1'i bekler** (token modeli netleşmeden allow-list yazılamaz).
- **P3, P2'yi bekler.**
- **P5 birleşme noktası** — A ve B şeridinin ikisi de bitmeden başlamaz.
- **P6 kapanış** — hepsinden sonra, tek başına.

Tahmini net kod: ~150-200 satır. Yeni bağımlılık yok, yeni protokol yok.

---

## Her pakette geçerli ortak kurallar

Her prompt'un başına şunlar zaten gömülü, ama insan gözüyle de bil:

1. **Gerçek worktree kur** — `git rev-parse --show-toplevel` cwd'yi vermiyorsa
   ana repo'da çalışıyorsundur, DUR. Bkz `HANDOFF.md` worktree hazard bölümü.
2. **`uv sync --extra dev`** — pytest/ruff/mypy `dev` extra'sında.
3. **Kapı zorunlu:** `make format && make lint && make typecheck && make test`
4. **PR aç, CI yeşilse kendin merge et** (`gh pr merge --merge --delete-branch`).
5. **`git add -A` ASLA** — eşzamanlı oturumların WIP'ini süpürür. Dar `git add <dosya>`.
6. **Kural-8:** hiçbir paket gerçek eğitim başlatmaz.

---

# PAKETLER

## P1 — Onay & kill-switch izolasyonu 🔴 BLOKLAYICI

**Şerit:** A · **Bağımlılık:** yok · **Paralel:** P2 ile aynı anda başlatılabilir

```
Achilles'te sürücü-motor ile insan yetkisini ayıran "scope" katmanını tasarla ve uygula.

ÖNCE OKU: HANDOFF.md worktree hazard bölümü. `git rev-parse --show-toplevel` cwd'ni
vermiyorsa gerçek worktree kur:
  git worktree add "<ayrı-dizin>" -b claude/scope-isolation origin/main
Orada `uv sync --extra dev` çalıştır.

SORUN (doğrulanmış):
- app/web/security.py:66 — settings.api_token boşsa doğrulama TAMAMEN atlanıyor.
- POST /api/approvals/{id}/approve (server.py:1917) ve
  POST /api/supervisor/clear-stop-all (server.py:1971) insanla aynı yetkide.
- Sonuç: Achilles'in kendi doğurduğu `claude -p` süreci kendi eğitimini onaylayabilir
  ve kill-switch'i temizleyebilir. CLAUDE.md Kural-8 bu kurulumda etkisiz.

İSTENEN:
1. İki kimlik seviyesi: "human" (UI/CLI) ve "driver" (spawn edilen motor).
2. Onay uçları + stop-all temizleme + eğitim başlatma YALNIZ human scope'a açık.
   Driver scope bu uçlarda 403 alır — ve OpenAPI'de görünmemesi tercih edilir.
3. Driver token'ı kısa ömürlü, run_id'ye bağlı, tek-koşuluk olsun.
4. api_token boşken davranış: en azından bir başlangıç uyarısı logla; sessiz
   "auth kapalı" durumunu belirgin hale getir.
5. Mevcut insan akışlarını (web UI, CLI) BOZMA — geriye dönük uyumlu kal.

KULLAN:
- `rlm-security-reviewer` ajanı — tasarımı ve sonra uygulamayı PASS/FAIL denetlesin.
  Kendi yazdığın kodu kendin onaylama; ajanın raporu olmadan PR açma.
- `/codegen-review` skill'i — ruff+mypy+test kapısı.

TESTLER (zorunlu, çevrimdışı):
- driver scope ile approve → 403
- driver scope ile clear-stop-all → 403
- human scope ile ikisi de → 200
- driver token'ın run_id dışında kullanımı → reddedilir
- api_token boşken uyarı loglanıyor

KAPI: make format && make lint && make typecheck && make test
Sonra PR aç, CI yeşilse merge et. Gerçek eğitim BAŞLATMA.
```

---

## P2 — Motor kayıt tablosu ✅ TAMAMLANDI (PR #112, 2026-07-21)

> **Teslim:** `app/orchestration/engines.py` — `Engine` frozen dataclass + `_ENGINES` tablosu
> (claude / codex / gemini / local); yeni motor = **tek satır**. `driver.py` tabloya bağlandı:
> `build_hunt_command(run, engine)` + `engine_available(engine)`; `claude_available()` geriye
> dönük korundu. Prompt, `PROMPT` sentinel'inin yerine **tek argv öğesi** olarak konur (shell yok).
> PATH yoklaması TTL'li (`PROBE_TTL_S=60`); `which`/`clock` enjekte edilebilir → offline test.
> Kota uyarısı her motorda taşınıyor → **P5 UI bunu `describe_all()`'dan okuyacak.**
> Kimlik bilgisi alanı yok; yalnız API-key'le çalışan motor tabloya alınmadı (test bekçiliğinde).
> +27 test. **P3 artık başlatılabilir.**

**Şerit:** B · **Bağımlılık:** yok · **Paralel:** P1 ile aynı anda

```
Achilles'in birden fazla yerel "motor"u (abonelikli CLI ajanı) tanımasını sağla.

ÖNCE OKU: HANDOFF.md worktree hazard bölümü; gerçek worktree kur
(`-b claude/engine-registry`), `uv sync --extra dev`.

BAĞLAM: app/orchestration/driver.py şu an SADECE `claude`'u biliyor
(build_hunt_command():55 → ["claude","-p",prompt]; claude_available():78 → which).
Bunu küçük bir kayıt tablosuna genelleştir.

İSTENEN — app/orchestration/engines.py (YENİ, küçük tut):
Her motor için: ad, probe komutu, argv şablonu, insan-okur etiket.
  claude  → `claude -p <prompt>`        (abonelik OAuth)
  codex   → `codex exec <prompt>`       (ChatGPT plan girişi)
  gemini  → `gemini -p <prompt>`        (Google hesabı)
  local   → motor yok, doğrudan Ollama hattı (spawn yok)
Yeni motor eklemek TEK SATIR olmalı.

KRİTİK KISITLAR:
- Achilles kimlik bilgisi TOPLAMAZ/SAKLAMAZ/İSTEMEZ. Mail, şifre, API key yok.
  Motorlar kendi CLI oturumlarıyla girişli. Bizim işimiz sadece "kurulu mu / girişli mi"
  tespiti. Kimlik formu tasarlama.
- API key yolu kalıcı olarak yasak (CLAUDE.md + memory: no-api-local-subscription-only).
  Bir motor yalnız API key ile çalışıyorsa onu tabloya EKLEME.
- shell=True YOK — argv listesi. Prompt asla shell'e string olarak geçmez.
- Determinizm: probe sonuçları cache'lenecekse TTL açık olsun.

AYRICA: her motor için "abonelik kotası uyarısı" metni taşı — headless koşular
interaktif kullanımla aynı pencereyi tüketiyor (Codex'te 5 saatlik yuvarlanan pencere).
P5'te UI bunu gösterecek.

KULLAN: `/codegen-review` skill'i.

TESTLER: motor bulunamadığında davranış; argv şablonu doğru kuruluyor;
bilinmeyen motor adı reddediliyor; shell enjeksiyonu imkânsız.

KAPI: make format && make lint && make typecheck && make test → PR → merge.
```

---

## P3 — Sür-modu prompt + MCP geçişi

**Şerit:** B · **Bağımlılık:** P2 · **Paralel:** P4 ile

```
Spawn edilen motora "sür" modu prompt'u ve Achilles MCP araçlarına erişim ver.

ÖNCE: worktree kontrolü (HANDOFF.md), `-b claude/drive-mode`, `uv sync --extra dev`.
P2 (app/orchestration/engines.py) merged olmalı — üzerine kur.

BAĞLAM: app/orchestration/driver.py:37 build_hunt_prompt() SABİT ve SALT-RAPOR
(bug avı için). Kod değiştirmeyi/eğitimi açıkça yasaklıyor. RUN akışı için ikinci
bir mod gerekiyor.

İSTENEN:
1. build_drive_prompt() — "sür" modu şablonu. İçeriği:
   - Achilles MCP araçlarını kullan, doğrudan dosya düzenleme yapma
   - hedef: veri hattı adımlarını sırayla ilerlet (carding → RLM → curate → assemble)
   - EĞİTİM BAŞLATMA; taze insan onayı gerektiren her adımda DUR ve raporla
   - çıktının son satırı makine-okunur verdict olsun (mevcut
     parse_hunt_verdict():60 desenini AYNALA, yeni bir format icat etme)
2. Alt sürece MCP erişimi: mcp_server/achilles_mcp.py'yi --mcp-config ile geçir.
   Kullanıcı-düzeyi `claude mcp add` kaydına BAĞIMLI OLMA — spawn kendi kendine yetsin.
3. Timeout: mevcut HUNT_TIMEOUT_S=1800 sür-modu için yeniden değerlendir, sabiti ayır.
4. Alt sürece P1'in "driver" scope token'ı geçirilir — human token ASLA.

KULLAN:
- `rlm-integration-agent` — MCP geçiş yolunu gözden geçirsin.
- `/codegen-review`.

TESTLER: prompt şablonu eğitim-yasağı ibaresini içeriyor; verdict parse'ı
bozulmamış; MCP config yolu üretiliyor; driver token geçiyor, human token geçmiyor.

KAPI: make format && make lint && make typecheck && make test → PR → merge.
Gerçek spawn ile canlı deneme YAPMA (P6'da).
```

---

## P4 — MCP araç allow-list + token iletimi

**Şerit:** A · **Bağımlılık:** P1 · **Paralel:** P3 ile

```
Achilles MCP yüzeyini daralt ve token kısır döngüsünü çöz.

ÖNCE: worktree kontrolü (HANDOFF.md), `-b claude/mcp-allowlist`, `uv sync --extra dev`.
P1 (scope izolasyonu) merged olmalı.

İKİ SORUN (doğrulanmış):
1. mcp_server/achilles_mcp.py:43 — httpx.AsyncClient hiçbir Authorization başlığı
   set etmiyor. ACHILLES_API_TOKEN ayarlıysa TÜM MCP tool çağrıları 401 alır.
   Yani "token aç → MCP kırılır / MCP çalışsın → kapı açık kalır" kısır döngüsü.
2. FastMCP.from_openapi() ~110 endpoint'in HEPSİNİ tool yapıyor — eğitim başlatma,
   onay verme, stop-all dahil. Dış bir ajanın görmemesi gereken uçlar görünüyor.

İSTENEN:
1. Token iletimi: MCP proxy'si scope'lu token'ı Authorization başlığında geçirsin.
2. Allow-list: from_openapi bir filtreden geçsin.
   - SERBEST (okuma): rag/ask, cards, backtest okuma, status, sentinel, agents/graph
   - HİÇ SUNULMAZ: approvals/*, supervisor/stop-all, training/run, autodrive execute
   Liste açık ve tek yerde dursun; "varsayılan kapalı, açıkça izin ver" yaklaşımı.
3. /api/openapi.json ve /api/docs auth'suz (server.py:145) — dış keşif yüzeyi.
   Bunu daraltmayı DEĞERLENDİR, ama web UI'yi kırıyorsa dokunma; kararı yaz.
4. 2026-07-28 MCP spec'i (stateless çekirdek, session'ların kaldırılması, SSE'nin
   ölmesi, Roots/Sampling/Logging deprecation) yakın. Session-tabanlı YENİ bir şey
   EKLEME. Mevcut FastMCP sürümünün spec durumunu kontrol et ve bulguyu yaz.

KULLAN:
- `rlm-security-reviewer` — allow-list'i denetlesin, PASS almadan PR açma.
- `/codegen-review`.

TESTLER: yasak uçlar tool listesinde YOK; izinli uçlar VAR; token başlığı geçiyor;
token'lı modda MCP çağrısı 200 dönüyor.

KAPI: make format && make lint && make typecheck && make test → PR → merge.
```

---

## P5 — Motor durum API'si + ⚡ RUN butonu

**Şerit:** birleşme · **Bağımlılık:** P1 + P2 + P3 + P4 (hepsi merged)

```
Kullanıcının "RUN'a bas, çalışsın" deneyimini tamamla.

ÖNCE: worktree kontrolü (HANDOFF.md), `-b claude/run-button`, `uv sync --extra dev`.
P1-P4 merged olmalı.

İSTENEN — BACKEND:
GET /api/engines → her motor için: ad, etiket, kurulu mu, girişli mi, kota uyarısı.
Salt-okuma, hiçbir şey tetiklemez. Kimlik bilgisi DÖNDÜRMEZ (token/mail/key asla).

İSTENEN — FRONTEND (15·AJAN HARİTASI sekmesi):
1. Motor seçici — kurulu olmayanlar gri, "nasıl kurulur" ipucu (kimlik formu DEĞİL).
2. Mevcut ⚡ butonu şu an execute=false dry-run. Onay diyaloğuyla execute=true'ya bağla.
3. Diyalogda AÇIKÇA göster:
   - hangi motor çalışacak
   - abonelik kotası uyarısı (headless koşu interaktif kullanımınla aynı pencereyi yer)
   - "eğitim BAŞLAMAZ, taze insan onayında durur" güvencesi
4. Koşu sırasında canlı durum + görünür DURDUR (stop-all) butonu.
5. Tek-tık ile geri alınamaz iş başlamasın — onay diyaloğu atlanamaz olsun.

TASARIM KISITI: mevcut kart yerleşimini (PR#105 derli-toplu şeritler) BOZMA.
Dekoratif öğe ekleme — PR#103 declutter kararına sadık kal.

KULLAN: `/achilles-web` skill'i; UI doğrulaması için preview araçları (dev server →
ekran görüntüsü). Kullanıcıya "sen kontrol et" deme, kendin doğrula.

TESTLER: /api/engines kimlik sızdırmıyor; execute=true onaysız çağrılamıyor;
kurulu-değil motor seçilemiyor.

KAPI: make format && make lint && make typecheck && make test → PR → merge.
```

---

## P6 — Uçtan uca duman testi + Kademe-2 derin av

**Şerit:** kapanış · **Bağımlılık:** P5 · **Paralel:** yok

```
Yeni RUN hattını uçtan uca doğrula ve eğitim öncesi zorunlu derin avı çalıştır.

ÖNCE: worktree kontrolü (HANDOFF.md), `-b claude/run-e2e`, `uv sync --extra dev`.
P1-P5 merged olmalı.

BÖLÜM 1 — DUMAN TESTİ:
`uv run achilles orchestrate-smoke` hattını yeni RUN akışını kapsayacak şekilde
kullan/genişlet. Kanıtlanacaklar:
- RUN → motor spawn → MCP araçları görünüyor → ajanlar sürülüyor
- eğitim adımına gelince DURUYOR (taze onay yok)
- driver scope onay veremiyor (403) ve stop-all temizleyemiyor (403)
- DURDUR butonu koşan motoru gerçekten kesiyor
- motor kurulu değilken temiz hata, sessiz başarısızlık yok

BÖLÜM 2 — KADEME-2 DERİN AV (CLAUDE.md kadansı gereği zorunlu):
Alt-sistem başına paralel finder → her bulgu için adversarial doğrulama
(şüpheci, varsayılan "çürütülmüş") → yalnız ONAYLANANLARI düzelt.
Odak alanları: scope izolasyonu bypass'ları, MCP allow-list kaçakları,
alt-süreç enjeksiyonu, token sızıntısı (log/hata mesajı/OpenAPI dahil).
KULLAN: `lora-safety-secret-scanner` (sır/PII taraması), `rlm-security-reviewer`.

BÖLÜM 3 — DOKÜMAN:
README motor bağlama bölümü (sıfır-varsayım, numaralı, kopyala-yapıştır — memory:
readme-beginner-friendly). HANDOFF.md güncelle. Bu roadmap'i "TAMAMLANDI" işaretle.

ÇIKTI: raporda "başarılı" demeden önce KANIT göster (test çıktısı, log).
Test geçmiyorsa geçmiyor de.

KAPI: make format && make lint && make typecheck && make test → PR → merge.
Gerçek LoRA eğitimi BU PAKETTE BAŞLATILMAZ (Kural-8, insan onayı ayrı).
```

---

## Sonraki chat'e devir notu

Yeni bir oturuma şunu yapıştır:

```
docs/ROADMAP_MOTOR_BAGLAMA.md dosyasını oku. Tamamlanmamış ilk paketi bul,
o paketin prompt'unu uygula. Paralel şeritte iş varsa söyle.
```

## Kapsam dışı (bilinçli erteleme)

- **A2A protokolü** — kurumlar-arası/çok-makineli. Local-first kurulumda gereksiz.
- **AGENTS.md + SKILL.md taşınabilirliği** — ucuz kazanç ama RUN akışını bloklamıyor;
  P6'dan sonra ayrı küçük paket.
- **LiteLLM ağ geçidi** — `openai_base_url` (`app/config/settings.py:52`) kancası
  zaten var; ihtiyaç doğmadan katman ekleme.
- **MCP 2026-07-28 stateless göçü** — P4'te sadece "yeni session bağımlılığı ekleme"
  kısıtı var; asıl göç FastMCP sürümü hazır olunca ayrı paket.
