#!/usr/bin/env bash
# Achilles Trader AI — TEK KOMUT güncelleme (macOS / Linux; KURULU makinede çalıştır)
#
#   ./update.sh            -- normal: yerel değişiklikleri saklayıp GitHub'dan çek
#   ./update.sh --force    -- yereli AT, origin/main ile birebir eşitle (salt-kopya kurulum)
#
# Yapar: web sunucusunu durdur (port 8765) -> git pull -> uv sync --extra web ->
#        web'i yeniden başlat -> sağlık kontrolü.  EĞİTİME DOKUNMAZ.
#
# Tarayıcıda son halini görmek için sonunda: Cmd+Shift+R (sert yenileme).

set -u

FORCE=0
case "${1:-}" in
  -f|--force) FORCE=1 ;;
  "") ;;
  *) echo "Bilinmeyen argüman: $1 (kullanım: ./update.sh [--force])"; exit 1 ;;
esac

# Proje dizini = bu script'in bulunduğu yer
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
cd "$PROJECT_DIR" || { echo "[HATA] Proje dizinine girilemedi"; exit 1; }

# --- araçları bul ---
UV="$(command -v uv || true)"
[ -z "$UV" ] && [ -x "$HOME/.local/bin/uv" ] && UV="$HOME/.local/bin/uv"
[ -z "$UV" ] && [ -x "$HOME/.cargo/bin/uv" ] && UV="$HOME/.cargo/bin/uv"
GIT="$(command -v git || true)"
[ -z "$UV" ]  && { echo "[HATA] uv bulunamadı (önce setup.sh)."; exit 1; }
[ -z "$GIT" ] && { echo "[HATA] git bulunamadı."; exit 1; }

"$GIT" rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
  echo "[HATA] Bu klasör bir git deposu değil: $PROJECT_DIR"; exit 1;
}

mkdir -p logs
LOG="logs/update.log"
echo "[$(date '+%Y-%m-%d %H:%M')] Güncelleme başlıyor (force=$FORCE)..." >> "$LOG"

# --- 1. Web sunucusunu durdur (port 8765 + achilles-web). EĞİTİME dokunma. ---
stop_web() {
  if [ -f .web.pid ]; then
    pid="$(cat .web.pid 2>/dev/null)"
    case "$pid" in
      ""|*[!0-9]*) ;;
      *) kill "$pid" 2>/dev/null || true ;;
    esac
    rm -f .web.pid
  fi
  # port 8765'i dinleyeni durdur (macOS/Linux: lsof)
  if command -v lsof >/dev/null 2>&1; then
    pids="$(lsof -ti tcp:8765 2>/dev/null || true)"
    [ -n "$pids" ] && kill $pids 2>/dev/null || true
  fi
  # achilles-web süreçleri (EĞİTİM 'achilles train' DEĞİL — ona dokunma)
  pkill -f 'achilles-web' 2>/dev/null || true
}
stop_web
sleep 1

# --- 2. GitHub'dan çek ---
"$GIT" fetch origin main >/dev/null 2>&1
LOCAL="$("$GIT" rev-parse HEAD 2>/dev/null)"
REMOTE="$("$GIT" rev-parse origin/main 2>/dev/null)"

if [ "$FORCE" -eq 1 ]; then
  echo "[!] --force: yerel kod değişiklikleri ATILIYOR, origin/main'e eşitleniyor."
  "$GIT" reset --hard origin/main >/dev/null 2>&1
elif [ "$LOCAL" != "$REMOTE" ]; then
  STASH="$("$GIT" stash 2>&1)"
  DIDSTASH=1
  echo "$STASH" | grep -q "No local changes" && DIDSTASH=0
  if "$GIT" pull origin main >/dev/null 2>&1; then
    [ "$DIDSTASH" -eq 1 ] && "$GIT" stash pop >/dev/null 2>&1 || true
  else
    echo "[HATA] git pull başarısız. Çözüm:  ./update.sh --force"
    [ "$DIDSTASH" -eq 1 ] && "$GIT" stash pop >/dev/null 2>&1 || true
    echo "[$(date '+%Y-%m-%d %H:%M')] pull HATASI" >> "$LOG"
  fi
else
  echo "[OK] Kod zaten güncel (${LOCAL:0:7})."
fi

NEW="$("$GIT" rev-parse HEAD 2>/dev/null)"
UPDATED=0
[ "$NEW" != "$LOCAL" ] && UPDATED=1
[ "$UPDATED" -eq 1 ] && echo "[OK] Kod güncellendi: ${LOCAL:0:7} -> ${NEW:0:7}"

# --- 3. Bağımlılıklar (WEB extra DAHIL — düz 'uv sync' web paketlerini budar) ---
if [ "$UPDATED" -eq 1 ] || [ "$FORCE" -eq 1 ]; then
  echo "[..] Bağımlılıklar eşitleniyor (uv sync --extra web)..."
  "$UV" sync --extra web >/dev/null 2>&1 || true
fi

# --- 4. Web'i yeniden başlat (arka plan) ---
nohup "$UV" run --project "$PROJECT_DIR" achilles-web \
  > logs/achilles-web.log 2> logs/achilles-web-err.log &
echo $! > .web.pid
echo "[$(date '+%Y-%m-%d %H:%M')] Sunucu başlatıldı (PID $(cat .web.pid))." >> "$LOG"

# --- 5. Sağlık kontrolü (port dinliyor mu / status yanıt veriyor mu) ---
OK=0
i=0
while [ "$i" -lt 15 ]; do
  if command -v lsof >/dev/null 2>&1 && lsof -ti tcp:8765 >/dev/null 2>&1; then OK=1; break; fi
  if curl -sf "http://127.0.0.1:8765/api/status" >/dev/null 2>&1; then OK=1; break; fi
  i=$((i + 1))
  sleep 2
done
echo ""
if [ "$OK" -eq 1 ]; then
  echo "[OK] Web çalışıyor: http://127.0.0.1:8765"
  echo "     >> Son halini görmek için tarayıcıda: Cmd+Shift+R (sert yenileme!)"
else
  echo "[UYARI] Web 30 sn'de açılmadı — log: logs/achilles-web-err.log"
fi
