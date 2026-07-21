"""15 · AJAN HARİTASI — frontend statik-dosya duman testleri (offline).

Frontend için ayrı JS test altyapısı yok → statik dosya içeriğini doğrularız:
sekme + panel var mı, yalnız mevcut salt-okuma/orkestrasyon uçları kullanılıyor mu,
tehlikeli ⚡ tetik execute'tan ÖNCE confirm() istiyor mu (Kural 8), dinamik içerik
esc()/textContent ile kaçırılıyor mu (XSS) ve CSP-güvenli mi (inline style/onclick yok).
Ağ/Ollama gerektirmez. Backend grafik zaten `test_agent_graph.py`'de test'li.
"""

from __future__ import annotations

import re
from pathlib import Path

_STATIC = Path(__file__).resolve().parents[1] / "app" / "web" / "static"
_INDEX = _STATIC / "index.html"
_APPJS = _STATIC / "assets" / "app.js"
_APPCSS = _STATIC / "assets" / "app.css"


def _index() -> str:
    return _INDEX.read_text(encoding="utf-8")


def _appjs() -> str:
    return _APPJS.read_text(encoding="utf-8")


def _appcss() -> str:
    return _APPCSS.read_text(encoding="utf-8")


def _panel_section() -> str:
    """index.html'deki panel-agentmap <section> gövdesi."""
    html = _index()
    start = html.index('id="panel-agentmap"')
    end = html.index("</section>", start)
    return html[start:end]


# ── nav + panel ──────────────────────────────────────────────────────────────
def test_tab_and_panel_present() -> None:
    html = _index()
    assert 'data-tab="agentmap"' in html
    assert 'id="panel-agentmap"' in html
    # Sekme NUMARASINA pinleme yapma: sekme eklenip çıkarıldıkça numara kayar
    # (11 · RLM kaldırılınca 15 → 14 oldu). Etiket sabit, numara değil.
    assert re.search(r'<span class="tab-num">\d+</span> · AJAN HARİTASI', html)


def test_panel_has_all_sections() -> None:
    html = _index()
    for el_id in (
        "amTriggerBtn",
        "amRefreshBtn",
        "amStatusLine",
        "amDryRun",
        "amDryRunCmd",
        "amLegend",
        "amCanvasWrap",
        "amCanvas",
        "amDetail",
    ):
        assert f'id="{el_id}"' in html, f"panel eksik öğe: {el_id}"


def test_assets_cache_busted() -> None:
    # Versiyona-DUYARSIZ: asset'ler cache-bust query'siyle sunuluyor mu (tam numara pinlenmez —
    # her UI değişikliğinde ?v artar; sabit "v7" beklemek kırılgandı, görsel sadeleştirmeyi kırdı).
    html = _index()
    assert "app.js?v=" in html
    assert "app.css?v=" in html


# ── app.js kablolaması ───────────────────────────────────────────────────────
def test_js_wiring_present() -> None:
    js = _appjs()
    assert "function loadAgentMap" in js
    assert 'if (name === "agentmap") loadAgentMap();' in js
    # izleme grubuna eklenmiş
    assert '"about", "agentmap"' in js


def test_js_uses_only_readonly_and_orchestration_endpoints() -> None:
    js = _appjs()
    for token in ('"/agents/graph"', '"/orchestration/start"', "/orchestration/autodrive/"):
        assert token in js, f"app.js eksik uç: {token}"


def test_trigger_confirms_before_execute() -> None:
    """⚡ tetik gerçek `claude -p` (execute:true) spawn'ından ÖNCE confirm() ister (Kural 8)."""
    js = _appjs()
    h = js.index("function amTriggerTraining")
    seg = js[h : js.index("function loadAgentMap")]
    assert "window.confirm(" in seg
    # confirm, autodrive POST'undan ÖNCE gelmeli ve execute değeri confirm sonucu (go) olmalı.
    assert seg.index("window.confirm(") < seg.index("/orchestration/autodrive/")
    assert "execute: go" in seg
    # DRY-RUN yolu: onaylanmazsa komut gösterilir (spawn yok).
    assert "amShowDryRun" in seg


def test_dynamic_content_is_escaped() -> None:
    js = _appjs()
    h = js.index("// ---------- 15 · AJAN HARİTASI")
    seg = js[h : js.index("// ---------- init ----------")]
    # API'den gelen alanlar esc() ile kaçırılmalı (XSS savunması).
    for token in ("esc(n.name", "esc(n.trigger)", "esc(x)", "esc(lm.label)", "esc(e.from)"):
        assert token in seg, f"escape edilmemiş olabilir: {token}"
    # Kuru-çalıştırma komutu innerHTML DEĞİL textContent ile yazılmalı.
    assert "el.textContent = cmd" in seg
    assert seg.count("esc(") >= 12


def test_csp_safe_no_inline_style_or_onclick() -> None:
    # Panel CSP-güvenli olmalı: satır-içi style / onclick yok (style-src 'self').
    section = _panel_section()
    assert "onclick=" not in section
    assert "style=" not in section
    # DRY-RUN gizleme inline style değil `hidden` özniteliği ile.
    assert " hidden>" in section or " hidden " in section


# ── "DERLİ TOPLU" kart yerleşimi (JS + CSS) ──────────────────────────────────
def test_js_card_layout_structure() -> None:
    js = _appjs()
    # kartlar + dik-açılı yol + ana ajan alt buton + aktivasyon yolu
    for token in ("amOrthPath", "am-card", "am-card-edge", "am-mainbar", "am-edge-activate"):
        assert token in js, f"kart-yerleşim eksik: {token}"
    # ana ajan şeritlerden çıkarılıp alt butona alınır + tıkla → ⚡ tetik
    assert "if (n.is_main)" in js
    assert 'closest(".am-mainbar")' in js and "amTriggerTraining()" in js


def test_css_light_path_and_status_colors() -> None:
    css = _appcss()
    # akan kenar ("ışıklı yol") animasyonu + aktivasyon (yeşil "devreye sokar") yolu
    assert ".am-edge.flowing" in css
    assert ".am-edge-activate" in css
    assert "@keyframes am-flow" in css
    # çalışan durum nabzı
    assert "@keyframes am-pulse" in css
    # kart sol-kenar durum rengi + ana ajan yeşil buton + tehlikeli kesik kenarlık
    assert ".am-node.status-running .am-card-edge" in css
    assert ".am-mainbar-box" in css
    assert ".am-node.am-danger .am-card" in css
    # Okabe-Ito CVD-güvenli palet
    assert "var(--pos)" in css and "var(--ok)" in css and "var(--warn)" in css
    # geniş grafik yatay kaydırma kabında
    assert ".am-canvas-wrap" in css and "overflow-x: auto" in css


# ── web ucu (uçtan uca, offline) ─────────────────────────────────────────────
def test_graph_endpoint_shape() -> None:
    import pytest

    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from app.web.server import app

    client = TestClient(app)
    r = client.get("/api/agents/graph")
    assert r.status_code == 200
    body = r.json()
    assert body["main_agent"] == "orchestration-autodrive"
    assert isinstance(body["nodes"], list) and body["nodes"]
    assert isinstance(body["edges"], list)
    assert isinstance(body["groups"], list) and body["groups"]
