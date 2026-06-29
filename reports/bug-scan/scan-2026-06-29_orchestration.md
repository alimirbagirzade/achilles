# Kademe-2 Derin Adversarial Av — 2026-06-29 (orkestrasyon alt sistemi)

**Tetik:** Yeni merge olan `app/orchestration` (PR#72, ~2062 satır) — en yüksek churn alanı.
**Yöntem:** Çok-ajan Workflow — 6 paralel finder (boyut başına) → her benzersiz bulgu **3 skeptik
lens** (repro / by-design / severity), **≥2 "real" oyu → onaylı**. 57 ajan, ~1.05M token.
**Sonuç:** 17 ham bulgu → **12 onaylı / 5 reddedildi**. Onaylananlar 3 PR ile düzeltildi
(hepsi CI-yeşil self-merge); reddedilenler tetiklenemez/latent olduğu için bilinçle BIRAKILDI.

---

## Onaylanan bulgular ve düzeltmeleri

### PR#75 — `SqliteStore` WAL + busy_timeout yok (MEDIUM, 3-oy; claimed HIGH)
`SqliteStore` (ana/EN YOĞUN yazan store) `sqlite_file`'ı 4 store ile paylaşıyor ama
`_sqlite_pragmas` listener'ı yoktu → busy_timeout yalnız pysqlite ~5s (diğerleri 30s) + DB'yi
ilk açan SqliteStore olursa WAL hiç set edilmez. **Fix:** rlm/mastery/orchestration ile birebir
aynı desen (WAL + busy_timeout=30000 + connect_args timeout=30.0) + doğrulama testi. Artık 5/5
paylaşan store uyumlu.

### PR#76 — Orkestrasyon durum-makinesi + eşzamanlılık + onay (MEDIUM/LOW küme)
1. **`recover_stale` cancelled koşuyu `failed`'a clobber** (MEDIUM): `find_stale_running_stages`
   run-durumuna bakmıyordu → iptal edilmiş koşunun asılı `running` aşaması, sonraki `/recover`'da
   `cancelled`→`failed` clobber oluyordu. Fix: `OrchestrationRun`'a join + terminal koşular hariç;
   `cancel()` asılı aşamayı `skipped`'e çeker.
2. **`step()` atomik değil → çift-delege** (6 finder aynı kök): FastAPI threadpool'da eşzamanlı
   `/start`+`/resume` aynı aşamayı iki kez delege edebiliyordu. Fix: `claim_stage_running` CAS-claim
   (`consume_fresh_approval` deseni) — yalnız pending/blocked/failed iken `running`, rowcount!=1 → no-op.
3. **cancel-step yarışı**: `step()` artık delege sonrası run durumunu yeniden okur; terminal ise
   sonucu yazmaz (iptal/tamamlanmayı clobber etmez), kapılan aşamayı temizler.
4. **`approval` onayı boşa tüketiyordu + yanıltıyordu** (MEDIUM): tek-kullanımlık onayı TÜKETİP
   "eğitim yetkili" diyordu ama `train` handoff hiçbir eğitim başlatmıyordu + her resume yeni PENDING.
   Fix: gerçek `train --run` yolunun AYNI anahtarını (`lora-trainer/train_run`) **tüketmeden** gözler
   (`has_fresh_approval`). **Kural 8 korunur** (train hâlâ handoff).
5. **`profile` doğrulaması yok** (LOW): serbest-metindi, dry-run komut dizesine gömülüyordu →
   `adapter_name` ile aynı kalıp (`^[A-Za-z0-9_-]{1,64}$`).
6. **`touch_heartbeat` ölü-kod** (LOW, latent): docstring'e gelecek inline-delege sözleşme notu.

### PR#77 — RLM alexzhang yolu degenerate "Kısa cevap: ." (LOW, 3-oy, python-repro)
`_rebuild_from_supported` yalnız uydurma atıftan ibaret iddiayı `s.strip()` ile elemiyordu ('.'
truthy). Native df3ba4e `_has_content` ile kapatmıştı; opt-in alexzhang yolu eksikti (Kural 7).
**Fix:** filtreyi native `_has_content` semantiğine çek + regresyon testi.

---

## Reddedilen bulgular (tetiklenemez/latent — by-design lensi eledi)

| id | neden reddedildi |
|----|------------------|
| `orc-heartbeat-never-touched` / `-refreshed` (×2) | `touch_heartbeat` ölü ama recover_stale yarışı tetiklenemez: tüm delegeler senkron+hızlı, tehlikeli aşamalar handoff; ~30dk yaşayan inline delege YOK → gelecek-kırılganlık, canlı bug değil |
| `orc-unbounded-limit-events` | `limit` üst-sınırı yok ama `LIMIT=1e9` yalnız var olan az satırı döner; events organik büyümez; auth-gate'li tek-kullanıcı → kaynak-tüketim repro'su yok |
| `orc-update-setattr-uncontrolled-fields` | `**fields`+setattr allow-list'siz ama tüm çağıranlar sabit-literal/sunucu-tarafı anahtar geçiriyor; kullanıcı-kontrollü `**` yayma YOK → savunma-derinliği nit'i, tetiklenebilir değil |
| `rag-bm25-cache-count-only-stale` | doğrulama session-limit'e takıldı (0 oy) → ele alınmadı, ileride bakılabilir |

**Not:** Reddedilenlerin çoğu "gelecekte X eklenirse kırılır" türü latent gözlem. by-design +
repro lensleri bunları confirmed-bug'dan ayırdı (yanlış-pozitif gürültüsü engellendi).

---

## Kapı (Kademe-0)
Her PR: `ruff format` + `ruff check` + `mypy` + `pytest` çevrimdışı YEŞİL. Birleşik suite **1350 passed**
(2 skip = ollama/slow). +14 yeni test (WAL doğrulama, CAS atomikliği, cancel-clobber korumaları,
approval peek, unsafe-profile 422, degenerate-strip regresyon).

## Audit izi
PR#75 · PR#76 · PR#77 (hepsi MERGED). Memory: [[orchestration-kademe2-hunt-2026-06-29]],
[[sqlite-shared-file-wal-pragmas]].
