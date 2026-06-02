"""Web güvenlik yardımcıları (FastAPI).

Tehdit modeli: bu yerel-öncelikli bir araştırma aracıdır. Sunucu varsayılan
olarak yalnız ``127.0.0.1``'e bağlanır. Yine de savunmayı katmanlı tutarız:

- İsteğe bağlı bearer-token kimlik doğrulama (ağa açılırsa zorunlu hale gelir).
- IP başına basit hız sınırı (bellekte, bağımlılık gerektirmez).
- Güvenlik başlıkları (CSP, X-Frame-Options, vb.).
- Katı PDF upload doğrulaması (uzantı + sihirli bayt + boyut + dosya adı temizleme).
- Yol-aşımı (path traversal) koruması.

Burada kullanıcı girdisi ASLA çalıştırılmaz; strateji kuralları yalnız güvenli
regex ile ayrıştırılır (bkz. trading/strategy_ir.py).
"""

from __future__ import annotations

import re
import secrets
import time
import unicodedata
from collections import defaultdict, deque
from pathlib import Path

from fastapi import HTTPException, Request, status

from app.config import get_settings

# --- Sabitler ---
_PDF_MAGIC = b"%PDF-"
_ALLOWED_UPLOAD_SUFFIX = ".pdf"
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")

# Güvenlik başlıkları. CSP yalnız kendi kaynaklarımıza + Google Fonts'a izin verir.
SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'"
    ),
}


# --- Kimlik doğrulama ---
def require_auth(request: Request) -> None:
    """API token ayarlıysa geçerli bir bearer token zorunludur.

    Token boşsa (varsayılan yerel mod) doğrulama atlanır — sunucu zaten yalnız
    localhost'a bağlıdır. Ağa açmak için ACHILLES_API_TOKEN ata.
    """
    settings = get_settings()
    token = settings.api_token.strip()
    if not token:
        return

    header = request.headers.get("authorization", "")
    provided = ""
    if header.lower().startswith("bearer "):
        provided = header[7:].strip()
    else:
        provided = request.headers.get("x-api-token", "").strip()

    # sabit-zamanlı karşılaştırma (stdlib; encode ile non-ASCII token güvenli)
    if not secrets.compare_digest(provided.encode("utf-8"), token.encode("utf-8")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz veya eksik API token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


# --- Hız sınırı (bellekte, IP başına kayan pencere) ---
class RateLimiter:
    def __init__(self, per_minute: int) -> None:
        self.per_minute = per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, client_ip: str) -> None:
        if self.per_minute <= 0:
            return
        now = time.monotonic()
        window_start = now - 60.0
        dq = self._hits[client_ip]
        while dq and dq[0] < window_start:
            dq.popleft()
        if len(dq) >= self.per_minute:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Hız sınırı aşıldı; biraz sonra tekrar dene.",
            )
        dq.append(now)


def client_ip(request: Request) -> str:
    # Yerel araç: proxy başlıklarına güvenmeyiz (spoof edilebilir).
    return request.client.host if request.client else "unknown"


# --- PDF upload doğrulama ---
def sanitize_filename(name: str) -> str:
    """Dosya adını güvenli bir tabana indirger (yol-aşımı / kontrol karakteri yok)."""
    name = unicodedata.normalize("NFKD", name)
    stem = Path(name).name  # dizin bileşenlerini at
    stem = _SAFE_NAME_RE.sub("_", stem).strip("._-")
    if not stem:
        stem = "paper"
    if not stem.lower().endswith(".pdf"):
        stem = f"{stem}.pdf"
    return stem[:128]


def validate_pdf_upload(filename: str, content: bytes) -> str:
    """Uzantı + sihirli bayt + boyut doğrular; temiz dosya adını döndürür.

    Hata durumunda HTTPException (400/413) fırlatır.
    """
    settings = get_settings()
    max_bytes = settings.max_upload_mb * 1024 * 1024

    if not filename or not filename.lower().endswith(_ALLOWED_UPLOAD_SUFFIX):
        raise HTTPException(status_code=400, detail="Yalnız .pdf dosyaları kabul edilir.")
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Boş dosya.")
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Dosya çok büyük (> {settings.max_upload_mb} MB).",
        )
    if not content.startswith(_PDF_MAGIC):
        raise HTTPException(status_code=400, detail="Dosya içeriği geçerli bir PDF değil.")
    return sanitize_filename(filename)


def safe_destination(dest_dir: Path, filename: str) -> Path:
    """Hedefin dest_dir içinde kaldığını garanti eder (path traversal koruması)."""
    dest_dir = dest_dir.resolve()
    candidate = (dest_dir / filename).resolve()
    if dest_dir not in candidate.parents and candidate.parent != dest_dir:
        raise HTTPException(status_code=400, detail="Geçersiz hedef yol.")
    return candidate
