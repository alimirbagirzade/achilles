"""UI sadeleştirme regresyon testleri (2026-07-21) — offline, statik dosya.

Kaldırılan yüzeylerin geri sızmadığını doğrular. Arka plan/API tarafı KORUNDU:
- /api/rlm/* uçları ve CLI `achilles rlm-answer` çalışmaya devam eder; yalnız
  arayüz sekmesi kaldırıldı (koşuları zaten yalnız CLI üretebiliyordu).
- ai_brain KORUNDU ve 08·SİSTEM panelinden erişilebilir hale getirildi.
"""

from __future__ import annotations

from pathlib import Path

_STATIC = Path(__file__).resolve().parents[1] / "app" / "web" / "static"


def _index() -> str:
    return (_STATIC / "index.html").read_text(encoding="utf-8")


def _appjs() -> str:
    return (_STATIC / "assets" / "app.js").read_text(encoding="utf-8")


def test_rlm_sekmesi_ve_paneli_yok() -> None:
    html = _index()
    assert 'data-tab="rlm"' not in html
    assert 'id="panel-rlm"' not in html


def test_rlm_js_kalintisi_yok() -> None:
    """Ölü JS bırakma: panel gidince onu besleyen fonksiyonlar da gitmeli."""
    js = _appjs()
    for kalinti in ("loadRlmDashboard", "rlmRunsTable", "rlmEnginePanel", "data-rlm-run"):
        assert kalinti not in js, f"ölü RLM JS kalıntısı: {kalinti}"


def test_rlm_api_uclari_KORUNDU() -> None:
    """Sadece arayüz kaldırıldı — sunucu tarafı ve CLI aynen durmalı."""
    server = (_STATIC.parents[1] / "web" / "server.py").read_text(encoding="utf-8")
    assert "/rlm/answer" in server, "RLM API ucu yanlışlıkla silinmiş"


def test_ulasilamayan_canli_dosyalari_yok() -> None:
    for ad in ("canli.html", "canli.css", "canli.js", "canli-badge.js", "canli-badge.css"):
        assert not (_STATIC / "assets" / ad).exists(), f"{ad} hâlâ duruyor"


def test_header_tek_canlilik_gostergesi() -> None:
    """İki ayrı /api/status yoklayıcısı vardı; biri kaldırıldı."""
    html = _index()
    assert "liveBadge" not in html
    assert 'id="connDot"' in html  # kalan gösterge


def test_yarim_gorev_formu_yok() -> None:
    """params_json backend'de olmadığı için kaldırıldı."""
    html = _index()
    for el in ("agTaskCreateBtn", "agTaskAgent", "agTaskTitle"):
        assert el not in html, f"yarım görev formu kalıntısı: {el}"
    assert 'id="agTasksTable"' in html  # salt-görünüm KALIR


def test_ai_brain_erisilebilir() -> None:
    """Kopuk dashboard'a ana arayüzden bağlantı eklendi (silinmedi)."""
    assert 'href="/ai-brain"' in _index()


def test_sekme_numaralari_kesintisiz() -> None:
    """RLM çıkınca numaralar yeniden dizildi; boşluk kalmamalı."""
    import re

    nums = [int(m) for m in re.findall(r'<span class="tab-num">(\d+)</span>', _index())]
    assert nums == list(range(1, len(nums) + 1)), f"numaralarda boşluk/tekrar: {nums}"
