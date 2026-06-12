#!/usr/bin/env bash
# Achilles SÜREKLİ ÖĞRENME DÖNGÜSÜ — "trader uzmanı" protokolü.
#
#   ZENGİNLEŞTİR (arXiv: psikoloji/belirsizlik/felsefe/trading, dönüşümlü konu)
#     → KAVRA (kart üret + içerikli onayla + anlama skorla)
#     → SENTEZLE (her 3 turda: research hipotezi + sentez makalesi)
#     → EĞİT (LoRA, 2 koşu × 40 iter)
#     → tekrar.
#
# RAM disiplini: LLM fazları ile eğitim fazı ASLA çakışmaz (sıralı).
# Devralma: başka bir eğitim döngüsü çalışıyorsa STOP_TRAINING ile nazikçe
# durdurur, mevcut koşunun bitmesini bekler, sonra kendisi başlar.
# Durdurma: storage/STOP_LEARNING dosyası (tur sonunda temiz çıkar).
#
# Kullanım:  bash scripts/continuous-learning.sh [MAX_SAAT (vars. 72)]
set -u
cd "$(dirname "$0")/.." || exit 1
MAX_HOURS="${1:-72}"
LOG=logs/continuous-learning.log
STATE=storage/learning_topic_index
STOP=storage/STOP_LEARNING
mkdir -p logs storage
log(){ echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG"; }

log "=== SÜREKLİ ÖĞRENME BAŞLADI (max ${MAX_HOURS}sa) ==="

# --- Devralma: eski eğitim döngüsünü nazikçe durdur -------------------------
touch storage/STOP_TRAINING
log "Devralma: STOP_TRAINING bırakıldı; mevcut eğitim koşusunun bitmesi bekleniyor"
for i in $(seq 1 160); do  # max ~40 dk
  if ! powershell -NoProfile -Command \
      "if (Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -like '*peft_lora_train*' }) { exit 1 } else { exit 0 }" \
      >/dev/null 2>&1; then
    sleep 15
  else
    break
  fi
done
# Eski döngünün cooldown'da STOP'u görüp temiz çıkması için ek bekleme
sleep 150
rm -f storage/STOP_TRAINING
log "Devralma tamam — döngü başlıyor"

END=$(( $(date +%s) + MAX_HOURS*3600 ))
round=0
while [ ! -f "$STOP" ] && [ "$(date +%s)" -lt "$END" ]; do
  round=$((round+1))
  log "──── TUR $round ────"

  # --- 1) ZENGİNLEŞTİR: sıradaki konudan 3 makale --------------------------
  IDX=$(cat "$STATE" 2>/dev/null || echo 0)
  mapfile -t TOPICS < <(grep -v '^#' scripts/enrichment-topics.txt | grep -v '^[[:space:]]*$')
  NT=${#TOPICS[@]}
  TOPIC="${TOPICS[$((IDX % NT))]}"
  echo $(( (IDX + 1) % NT )) > "$STATE"
  log "1) Zenginleştir: '$TOPIC'"
  timeout 1200 uv run achilles arxiv "$TOPIC" --max-results 3 --auto-ingest >> "$LOG" 2>&1 \
    || log "   arxiv HATA/timeout (devam)"

  # --- 2) KAVRA: kartsızlara kart + içerikli onay + anlama skoru -----------
  PIDS=$(uv run python -c "
from app.memory.sqlite_store import SqliteStore
s = SqliteStore()
for p in s.list_papers():
    if not s.has_knowledge_card(p.paper_id):
        print(p.paper_id)
" 2>/dev/null)
  log "2) Kartsız makale: $(printf '%s' "$PIDS" | grep -c . || true)"
  for pid in $PIDS; do
    timeout 900 uv run achilles card "$pid" >> "$LOG" 2>&1 || log "   kart HATA: $pid"
  done
  uv run python -c "
from app.memory.sqlite_store import SqliteStore
s = SqliteStore()
a = k = 0
for c in s.list_pending_cards():
    cj = c.get('card_json') or {}
    if str(cj.get('title') or '').strip() and str(cj.get('main_claim') or '').strip():
        s.approve_card(c['card_id']); a += 1
    else:
        k += 1
print(f'   onay: {a} onaylandı, {k} içeriksiz atlandı')
" >> "$LOG" 2>&1

  # İçerikli (örnek üreten) makalelerden skoru olmayanları skorla — LLM.
  PIDS2=$(uv run python -c "
from app.memory.sqlite_store import SqliteStore
from app.lora.dataset_builder import build_dataset
s = SqliteStore()
pids = {str(e.metadata.get('paper_id','')) for e in build_dataset(s.list_approved_cards())}
for pid in sorted(p for p in pids if p):
    if s.get_comprehension_score(pid) is None:
        print(pid)
" 2>/dev/null)
  N2=$(printf '%s' "$PIDS2" | grep -c . || true)
  log "   anlama skorlanacak: $N2"
  for pid in $PIDS2; do
    RESP=$(curl -s -m 600 -X POST "http://127.0.0.1:8765/api/papers/$pid/comprehension" 2>&1)
    log "   anlama[$pid]: $(printf '%s' "$RESP" | head -c 160)"
  done

  # --- 3) SENTEZLE: her 3 turda hipotez + makale ----------------------------
  if [ $(( round % 3 )) -eq 1 ]; then
    log "3) Research + sentez makalesi"
    timeout 3600 uv run achilles research \
      "Davranissal yanlilik (asiri guven, kayip kacinma), belirsizlik ve rejim degisimi kavramlarini birlestirerek yeni bir trading indikatoru veya filtre oner ve test et." \
      --iterations 1 >> "$LOG" 2>&1 || log "   research HATA/timeout"
    uv run achilles synth-paper >> "$LOG" 2>&1
  fi

  # --- 4) EĞİT: dataset tazele + 2 koşu × 40 iter ---------------------------
  log "4) Dataset + eğitim (2×40 iter)"
  uv run achilles lora-dataset >> "$LOG" 2>&1
  for t in 1 2; do
    [ -f "$STOP" ] && break
    uv run achilles train --run --backend peft \
      --adapter-name achilles_auto --iterations 40 >> "$LOG" 2>&1 \
      || log "   eğitim HATA (koşu $t)"
  done

  # Tur özeti (rag-mastery LLM'siz)
  uv run achilles rag-mastery >> "$LOG" 2>&1
  log "──── TUR $round bitti — 120sn dinlenme ────"
  for i in $(seq 1 24); do [ -f "$STOP" ] && break; sleep 5; done
done

log "SÜREKLİ ÖĞRENME DURDU ($round tur; STOP veya süre doldu)."
rm -f "$STOP"
