# HANDOFF — Web Arayüzü Canlılık + Güvenlik Fix (2026-06-20, akşam)

> Bu, ana `HANDOFF.md` için bir oturum eki. Ayrı dosya olmasının nedeni: oturum boyunca eşzamanlı
> bir otonom süreç `HANDOFF.md`'yi + `main`/feature branch'lerini sürekli değiştirdiğinden o dosyaya
> güvenli yazılamadı. Bir sonraki seans bunu `HANDOFF.md`'nin üstüne taşıyabilir.

**Branch durumu:** İş `origin/main`'de. Repo: https://github.com/alimirbagirzade/achilles

---

## Oturum tetikleyici
"web arayüzü canlı değil" → kök neden bulundu+düzeltildi; ayrıca bir güvenlik açığı kapatıldı ve
arayüze canlılık göstergesi eklendi. **Hepsi `origin/main`'de** (eşzamanlı süreç dalları rebase ederken
commit içeriğimi koruyarak taşıdı — orphan commit normal; `git show HEAD:<dosya>` ile doğrula).
**PR AÇILMADI** (kullanıcı kararı: iş zaten main'de).

## LANDED (origin/main)

### 1. Web "canlı değil" — KÖK NEDEN + FIX
`scripts/start-server.ps1` sunucuyu çıplak `uv run achilles-web` ile başlatıyordu → uv her çağrıda
kilitli `.venv\Scripts\achilles-web.exe`'yi yeniden yazmaya çalışıp **"os error 32"** veriyor → sunucu
HİÇ başlamıyordu (`.web.pid` boş kalıyordu). Aynı darboğaz eğitim/loop adımlarını da sessizce çökertiyordu.

- **Fix:** tüm Windows launcher'larda `UV_NO_SYNC=1` / `uv run --no-sync` — `start-server.ps1`,
  `start-train.ps1`, `train-loop.ps1`, `auto-chain.sh` (`continuous-learning.sh` bu fix'i zaten almıştı).
  Bağımlılıklar zaten kurulu; sync'e gerek yok.
- `start-server.ps1 -Stop` artık `taskkill /T` ile **TÜM süreç ağacını** öldürür (eski `Stop-Process`
  yalnız `uv` sarmalayıcısını öldürüp gerçek python+uvicorn'u portta bırakıyordu → temiz restart bozuktu).
- `train-loop.ps1` iki **gerçek parse bug'ı**: `"$cycle:"` → `${cycle}:` (geçersiz değişken referansı,
  script hiç çalışmıyordu) ve em-dash `—` → `-` (BOM'suz UTF-8 dosyada PS 5.1 ANSI okuyunca 0x94 baytı
  akıllı-tırnağa dönüşüp parser'ı bozuyordu).
- **Doğrulama:** düzeltilmiş launcher ile sunucu uçtan uca ayağa kalktı (`/api/status` 200), idempotentlik
  + `-Status` + tree-kill `-Stop` test edildi; üç `.ps1` de ANSI ParseFile ile 0 hata.

### 2. Güvenlik — path-traversal (arbitrary file read)
`app/web/server.py::api_eval_run` — `req.eval_set` kullanıcı girdisi doğrudan dosya yoluna ekleniyordu;
`../../...` ile `evals/` dışındaki herhangi bir `.jsonl` okunabiliyordu (varsayılan yerel modda API token yok).
- **Fix:** mevcut `app/web/security.py::safe_destination` ile yol doğrulanıyor (aşım → 400).
- Offline traversal testi: `tests/test_eval_api.py::test_eval_run_rejects_path_traversal` (5 case).

### 3. Canlılık göstergesi (arayüzde)
- **Tam-ekran izleme sayfası:** `app/web/static/assets/canli.html` (+ `canli.css` / `canli.js`) →
  `http://127.0.0.1:8765/assets/canli.html`. Sekmede açık tut; sunucu ölünce KAPALI'ya döner.
- **Header rozeti:** ana arayüzün header'ında **CANLI/KAPALI** rozeti (`canli-badge.css` / `canli-badge.js`
  + `index.html`'e 3 satır). 4 sn'de bir `/api/status` yoklar (app.js'in 30 sn'lik connDot'undan ayrı/hızlı).
- İkisi de aynı-köken → CORS yok. **CSP-uyumlu** (sunucunun `script-src/style-src 'self'`'i inline'ı
  yasaklar; bu yüzden css+js ayrı dosya, ana arayüzdeki gibi). `/assets` mount + `index()` canlı okur →
  **server restart gerekmez.** Renk-körü güvenli: teal dolu daire = CANLI, turuncu kare = KAPALI.

## Kalan / Notlar (sonraki seans)
- **`gh` kurulu DEĞİL** (Git Bash + Windows). PR gerekirse: `winget install GitHub.cli` ya da hazır
  `compare/main...<branch>?expand=1` linki. (Ana HANDOFF'taki `gho_` GCM-token ipucu yalnız gh KURULUYSA çalışır.)
- **⚠ EŞZAMANLI OTONOM SÜREÇ:** Bu oturumda `main` + feature branch'leri sürekli rebase/checkout edildi;
  HEAD/branch 3× altımdan değişti. Kendi commit nesnen orphan olabilir ama içerik korunur → push sonrası
  daima `git show HEAD:<dosya>` ile doğrula, salt commit-hash'e güvenme. Çalışma ağacında o sürecin
  commit'lenmemiş WIP'i var (`server.py`/`app.js`/`index.html` `ragLoop` + `.pytest_tmp_*` çöp dizinleri) →
  **`git add -A` KULLANMA**, yalnız kendi dosyanı stage et.
- Artık dosya: `.claude/launch.json` (preview-screenshot denemesinden; zararsız, untracked). Silinebilir.
- Web şu an **tek temiz sunucu** olarak canlı (8765, HTTP 200) — `start-server.ps1` ile başlatıldı.

## İlgili hafıza
`web-server-autostart` (uv-sync kilit fix + git-chaos notu işlendi).
