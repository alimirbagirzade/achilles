# RAG Öğrenme Döngüsü — Otonom Çalışma Durumu (2026-06-18)

Kullanıcı işteyken "tüm makaleleri anla" mandası altında otonom çalışıldı. Bu rapor
ne bulunduğunu, ne düzeltildiğini ve sistemin şu anki durumunu özetler.

## TL;DR
- **Kök neden bulundu:** 145 makalenin ~130'unun onaylı kartı **içeriksiz** (`title=None,
  main_claim=""`). İki gerçek hata: (1) builder yalnız ilk 6000 krk okuyor → büyük
  kitaplarda kapak/ön-madde → LLM "..." üretiyor; (2) onay gate'i çok zayıf → dejenere
  "..." kartları onaylayıp coverage'ı ÇÖPLE şişiriyordu (v5-tipi risk).
- **Düzeltildi + push'landı (main):**
  - `is_substantive_card` güçlü gate (anlamlı title≥8 + main_claim≥40) — `00da5eb`
  - builder **orta-kesit** kurtarması (boşsa belge ortasından dene) — `00da5eb`
  - rebuild → içerikliyse **otomatik onay** (güçlü gate) — `00da5eb`
  - `continuous-learning.sh` onay gate'i de güçlü gate'e çevrildi — `d2aeeca`
  - builder **orantılı çoklu-ofset** (%25/%55) — sabit 8000 krk devasa kitaplarda hâlâ
    ön-madde kalıyordu — `41ec184`
  - 4 mevcut dejenere onaylı kart **reddedildi** → coverage 76→72 (honest).
- **DOĞRULAMA (gerçek LLM):** orta-kesit "Machine Learning" kitabını KURTARDI (main_claim
  177 krk, onaylandı); "Mathematical Physics"/"Wilmott" sabit-ofsette başarısızdı → orantılı
  ofsete geçildi. Web loop defteri SIFIRLANDI → tüm boş kitaplar yeni builder'la yeniden denenir.
- **GÜNCEL (rebuild ilerliyor):** coverage **%54 (papers_with_real 79/145)** — 72'den tırmanıyor.
- **Çalışan durum:** web RAG loop muhafazakâr **rebuild moduyla AÇIK** (2 kart/15dk,
  skor kapalı, fetch kapalı). `continuous-learning.sh` (kullanıcının ana döngüsü) skor+synth
  yapmaya devam ediyor. İkisi tek Ollama'yı paylaşır (sıralı; yavaş ama ilerler).

## İş bölümü (çakışmayı önlemek için)
- **continuous-learning.sh** (zaten çalışıyor, 72sa): kartsız makaleye kart + içerik-onay +
  comprehension skor + synth-qa. Boş kartı OLAN makaleleri ATLAR (kör nokta).
- **web RAG loop** (benim, ÖĞRENME sekmesi): YALNIZ **boş-kart rebuild** + güçlü-gate onay
  (benzersiz boşluk). Skorlamayı shell loop'a bıraktım (scores_per_cycle=0).

## Boş kartların doğası (heterojen)
1. **Büyük kitaplar** (ör. "Mathematical Physics" 2745 chunk, "Time Series Analysis" 1801):
   ön-madde sorunu → orta-kesit fix bunları KURTARABİLİR.
2. **Çöp/alakasız PDF'ler** (ör. OEIS ansiklopedisi): gerçek içerik yok → rebuild kurtaramaz,
   güçlü gate doğru şekilde reddeder, defter (`rebuilt_paper_ids`) bir daha denemez.
3. **Geçici LLM hataları:** rebuild kurtarır.

## Coverage matematiği (güçlü gate ile, honest)
- 145 makale · papers_with_real=**72** · empty_cards=130 · coverage **%50** · mastery ~59.
- "Tüm makaleleri anla" üst sınırı: çöp/alakasız PDF'ler çıkınca <%100. Gerçekçi hedef:
  kurtarılabilir (kitap+geçici-hata) makaleleri coverage'a katmak.

## Riskler / kullanıcı kararı gerekenler
- **Eşzamanlı LoRA eğitimi:** oturum sırasında `achilles train --run` görüldü. Web loop,
  gerçek eğitim ADIMLARI (tqdm) başlayınca otomatik DURAKLAR; ama veri-hazırlık (synth-qa)
  fazında DURMAZ → o sırada Ollama çekişmesi olur. **Öneri:** RAG verisi (coverage) tam
  olmadan LoRA eğitmek v5 riskini tekrarlar — önce coverage'ı yükseltmek daha sağlam.
- **Tek Ollama/CPU (GPU yok):** her şey sıralı; ilerleme yavaş (kitap başına dakikalar).
- `continuous-learning.sh` gate fix'i yalnız **bir sonraki restart'ta** geçerli; çalışan
  instance hâlâ eski (zayıf) gate'i kullanıyor (yeni çöp sızabilir; periyodik audit ile
  temizlenebilir: aşağıdaki komut).

## İzleme / müdahale komutları
```bash
# Coverage ilerlemesi
curl -s localhost:8765/api/rag-mastery | python -m json.tool
# Loop durumu (rebuild ilerlemesi)
curl -s localhost:8765/api/rag-loop/status | python -m json.tool
# Yeni çöp onaylı kart denetle + reddet (güçlü gate)
uv run python -c "from app.memory.sqlite_store import SqliteStore as S;from app.lora.dataset_builder import card_to_lora_example as f;from app.research.rag_learning_loop import is_substantive_card as g;s=S();j=[c for c in s.list_approved_cards() if f(c,c.get('paper_id','')) and not g(c.get('card_json') or {})];[s.reject_card(c['card_id']) for c in j];print('reddedilen çöp:',len(j))"
# Loop'u durdur / başlat
curl -s -X POST 'localhost:8765/api/rag-loop/enable?enabled=false'
curl -s -X POST 'localhost:8765/api/rag-loop/enable?enabled=true'
```

## Sonraki adımlar (öneri)
1. Web loop'un coverage'ı kaç makale yükselttiğini izle (kurtarılabilir kitaplar).
2. Coverage platoya oturunca kalan boş kartlar = gerçek çöp PDF'ler → kütüphaneden eleme
   düşünülebilir (kullanıcı kararı).
3. `continuous-learning.sh`'i bir sonraki uygun anda RESTART et → güçlü gate live olsun.
4. LoRA eğitimi: coverage hedefe ulaşınca, Kademe-2 derin av (CLAUDE.md) + eval-harness
   adapter testi ile (v5 dersi).
