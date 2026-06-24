---
name: rlm-integration
description: Achilles RLM, RAG, Paper Mastery, recursive reasoning veya alexzhang13/rlm adapter kodunu değiştirirken kullan. RLM bilgi deposu DEĞİLDİR (RAG odur); alexzhang motoru OPSİYONELDİR; OpenAI default DEĞİL; üretimde local exec yasak.
---

# Achilles RLM Integration Skill

RLM motor-adapter katmanını (native + opsiyonel alexzhang13/rlm) güvenli ve additive
biçimde geliştir. Mimari: `docs/rlm_alexzhang_integration.md` + `docs/rlm_security_model.md`.

## Kurallar (bağlayıcı)

1. RLM bilgi veritabanı DEĞİLDİR. Bilgi hafızası RAG'dir (Chroma + SQLite).
2. alexzhang13/rlm (`rlms`) OPSİYONELDİR. Achilles onsuz tam çalışmalı (native default).
3. OpenAI'yi VARSAYILAN provider yapma. Anthropic/Claude veya yerel Ollama/native.
4. Config açıkça alexzhang demedikçe native adapter tercih edilir.
5. Üretimde local exec / shell / network / filesystem-write YASAK (security guard).
6. RLM yalnız `ALLOWED_TOOL_NAMES`'teki güvenli wrapper'ları çağırabilir.
7. Nihai cevaplar makale chunk'larına dayanmalı; desteklenmeyen iddia çıkarılmalı;
   kanıt yetersizse `insufficient_evidence`.
8. Bu skill'den LoRA eğitimi BAŞLATMA. Production adapter'ı OTOMATİK değiştirme.
9. Secret commit etme. RAG / Paper Mastery / verifier / SQLite / Chroma'yı silme/devre dışı bırakma.
10. Değişiklik sonrası ilgili testleri çalıştır: `uv run pytest tests/test_rlm_*.py`.

## Hızlı referans

```bash
uv run achilles rlm-engine                       # motor config
uv run achilles rlm-test-adapter --adapter native|alexzhang
uv sync --extra rlm                              # opsiyonel rlms paketi
```

İlgili: `/rlm-answer` (kaynaklı cevap), ajanlar `rlm-integration-agent` (uygula),
`rlm-security-reviewer` (güvenlik denetimi).
