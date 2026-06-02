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

## Mimari sözleşmeleri
- `paper_id` içerik hash'inden türer → ingestion **idempotent**.
- Strateji yaşam döngüsü: `hipotez → StrategyIR → backtest → evaluate → verdict`.
  `verdict != pass` ise çıktı "aday"dır, "hazır" değildir.
- Yeni indikatör → `app/trading/indicators.py` registry'sine ekle + test yaz.
- Yeni CLI komutu → `app/main.py` + README tablosu güncelle.

## İlgili skill'ler
`.claude/skills/trading-research`, `backtest-auditor`, `codegen-review` —
ilgili görevde bunlara danış.

## Yapma
- Gizli anahtar/credential commit etme (`.env` ignore'da).
- `data/`, `models/`, `vector_db/`, `storage/` çıktısını commit etme (.gitkeep hariç).
- Stratejiyi backtest+denetimden geçirmeden "kullanıma hazır" sunma.
