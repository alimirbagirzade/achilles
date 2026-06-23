# CLAUDE.md — Achilles Trader AI çalışma kuralları

Bu dosya, bu repoda çalışan Claude (Claude Code) için bağlayıcı yönergeleri içerir.

## Proje nedir
Yerel-öncelikli AI trading **araştırma** sistemi: PDF literatür → RAG/bilgi
kartı → (opsiyonel LoRA) → disiplinli backtest. **Canlı bot değil, tavsiye değil.**

## Mutlak kurallar (asla ihlal etme)
1. **Yatırım tavsiyesi üretme.** Çıktılar her zaman _hipotez_ + _test noktası_.
2. **Test edilmeden "başarılı/çalışıyor" deme.** backtest + out-of-sample şart.
3. **Maliyetleri yok sayma** (komisyon + slippage).
4. **Look-ahead bias yasak** — pozisyon `shift(1)` ile gecikmeli.
5. **`eval`/`exec` yok** — strateji kuralları yalnızca güvenli regex ile parse.
6. **Determinizm** — rastgelelik daima `seed` parametresiyle.
7. **Kaynak uydurma** — retrieval boşsa açıkça belirt.
8. **Otomatik ağır eğitim yok** — `train` varsayılan dry-run; gerçek eğitim
   yalnızca açık `--run` ile.

## Kod stili
- Python ≥ 3.12, `from __future__ import annotations`
- pydantic v2 modelleri; SQLAlchemy 2.0 tipli API
- ruff (line-length 100, target py312), mypy (pydantic plugin)
- Saf pandas/numpy indikatörler (vektörize, döngü değil)
- Kullanıcıya dönük metinler/log/docstring **Türkçe**

## Doğrulama (değişiklik sonrası zorunlu)
```bash
make format && make lint && make typecheck && make test
```
Testler **çevrimdışı** çalışmalı (fake embedding + sentetik veri). Ollama/MLX
gerektiren testler `@pytest.mark.ollama` / `@pytest.mark.slow` ile işaretli.

## 🔁 Bug-avı kadansı (kademeli)

Bug yoğunluğu takvimle değil **kod değişimiyle (churn)** artar; bu yüzden maliyet
seviyesine göre kademeli tarama:

| Kademe | Ne | Tetikleyici | Otonomi |
|--------|-----|-------------|---------|
| **0 — Kapı** | `make format && lint && typecheck && test` (+ pre-commit/CI) | **Her commit** | Otomatik |
| **1 — Hafif tarama** | Tek `claude -p` rapor-only tarama (son diff + çekirdek) | **Haftalık** (yerel Task Scheduler: `scripts/weekly-bug-scan.ps1`) | **Rapor-only** (kod değiştirmez, push etmez) |
| **2 — Derin adversarial av** | Çok-ajan workflow (finder + 2-oylu adversarial doğrulama) | **Ayda 1 + her LoRA eğitiminden ÖNCE (zorunlu)** veya ~25-30 commit'te | **Denetimli** (fix+push insan gözetiminde) |

- **Kademe 2 her eğitimden önce zorunlu** — projenin tüm amacı backtest/eval'e güvenmek;
  v5 regresyonu tam bu yüzden olmuştu. Eğitime başlamadan derin av çalıştır.
- Kademe 1 raporu: `reports/bug-scan/scan-<tarih>.md` + HANDOFF özeti. Bulgular bir sonraki
  **denetimli** seansta düzeltilir (otomatik fix YOK — yanlış fix'i gözetimsiz main'e basma).
- Derin av deseni: alt-sistem başına paralel finder → her bulgu adversarial doğrulama
  (şüpheci, varsayılan çürütülmüş) → yalnız onaylananları düzelt → Kademe 0 kapısı → commit+push.

## Mimari sözleşmeleri
- `paper_id` içerik hash'inden türer → ingestion **idempotent**.
- Strateji yaşam döngüsü: `hipotez → StrategyIR → backtest → evaluate → verdict`.
  `verdict != pass` ise çıktı "aday"dır, "hazır" değildir.
- Yeni indikatör → `app/trading/indicators.py` registry'sine ekle + test yaz.
- Yeni CLI komutu → `app/main.py` + README tablosu güncelle.

## ⚡ YENİ SEANS BAŞLANGICI — ZORUNLU PROTOKOL

Her yeni oturumda Claude şunu yapmalı (sırayla):

### 1. HANDOFF'u oku
```
HANDOFF.md → "YENİ SEANS BAŞLANGICI" bölümünü oku → bekleyen görevleri listele
```

### 2. Ruflo başlat (otomatik)
Ruflo araçları erişilebilir durumdaysa `memory_search` ile son oturum durumunu sorgula:
- namespace: `patterns` — önceki ajan çıktıları
- namespace: `sessions` — oturum geçmişi
Ruflo yoksa: ToolSearch ile `ruflo` araçlarını yükle, `swarm_init` çalıştır.

### 3. Aktif skil'leri hatırlat
Kullanıcıya şu proje skillerini öner (içerik `.claude/skills/` dizininde):

| Skill | Ne zaman | Komut |
|-------|----------|-------|
| `/trading-research` | Araştırma döngüsü başlatılacaksa | formül çıkar → sentez → backtest |
| `/rlm-answer` | Kaynaklı + doğrulanmış cevap / çok-makale sentez gerekiyorsa | çok-tur retrieval → iddia doğrula → çekimser (rlm-answer/rlm-runs) |
| `/backtest-auditor` | Backtest sonucu değerlendirilecekse | look-ahead + OOS + overfit denetle |
| `/codegen-review` | Yeni indikatör/strateji kodu yazıldıysa | ruff+mypy+test kontrol |
| `/health` | Genel kod kalitesi | ruff, mypy, test özeti |
| `/investigate` | Hata/bug ayıklama | kök neden analizi |
| `/deep-research` | Yeni makale/konsept araştırması | web → kaynak → sentez |
| `/claude-mem:make-plan` | Çok adımlı özellik planı | alt ajan destekli plan |
| `/claude-mem:do` | Planı çalıştır | ajan swarm ile uygula |
| `/claude-mem:mem-search` | Önceki oturumda ne yapıldı | geçmiş sorgu |

### 4. Sistem durumu kontrol et
```bash
curl -sf http://localhost:11434/api/tags && echo "Ollama OK" || echo "Ollama KAPALI"
uv run achilles status
```

### 5. /login hakkında
`/login` → claude.ai OAuth MCP sunucularını (Figma/Gmail/Notion) yeniler.
Bu proje için **gerekli değil** (lokal-öncelikli). O serverler kullanılmıyorsa
`/login` atlansa da olur. Gerekli olursa yalnızca ilk komut olarak çalıştır.

---

## İlgili skill'ler
`.claude/skills/trading-research`, `backtest-auditor`, `codegen-review` —
ilgili görevde bunlara danış.

## Yapma
- Gizli anahtar/credential commit etme (`.env` ignore'da).
- `data/`, `models/`, `vector_db/`, `storage/` çıktısını commit etme (.gitkeep hariç).
- Stratejiyi backtest+denetimden geçirmeden "kullanıma hazır" sunma.
