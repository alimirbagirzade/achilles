"""verdict_audit.py — av (hunt) verdict'inin BAĞIMSIZ doğrulaması (Kural 8 sertleştirme).

SORUN (P8, doğrulanmış): `driver.parse_hunt_verdict` verdict'i TAMAMEN motorun kendi
stdout'unun son satırından okur (``ACHILLES_HUNT_VERDICT: PASS``). Bu satır, ZORUNLU
Kademe-2 derin av kapısının (her eğitimden önce, CLAUDE.md Kural 8) TEK dayanağıdır. Motor
derin avı HİÇ yapmadan son satıra ``PASS`` yazsa hat açılırdı → **motor kendi başarısının
tek kaynağı**. Fail-closed korumalar (satır yoksa FAIL, sahte-binary savunması, Write/Edit
yasağı) vardı ama BAĞIMSIZ kanıt yoktu.

ÇÖZÜM: motor artık serbest bir "PASS" değil, YAPILANDIRILMIŞ KANIT üretmek zorunda
(taranan dosyalar + alt-sistemler + bulgular). Bu modül o kanıtı **motordan bağımsız bir
oracle** ile — dosya sisteminin kendisiyle — doğrular:

* Kanıt bloğu yok/bozuk  → PASS reddedilir (öz-beyan tek kanıt olamaz).
* İddia edilen "taranan" dosyalar depoda GERÇEKTEN yoksa sayılmaz; asgari kapsama
  (dosya + alt-sistem sayısı) tutmuyorsa reddedilir → uydurulmuş ya da boş bir taramanın
  "PASS"ı geçemez.
* Motor "PASS" derken kanıtında HIGH/BLOCKER bir bulgu listelemişse (kendi kendiyle
  çelişiyorsa) reddedilir.

Böylece motorun verdict'i tek kanıt olmaktan çıkar: dosya sistemi zorunlu bir teyit
katmanıdır. **Not (dürüstlük):** bu deterministik denetim, motorun listelediği dosyaları
GERÇEKTEN okuduğunu kanıtlayamaz — bu, ikinci bir bağımsız LLM doğrulayıcı gerektirir
(çevrimdışı test edilemez + kota yakar, bu yüzden ayrı/opsiyonel bir katmandır). Buradaki
kapı, "hiç bakmadan PASS yaz" sınıfını ve iç-tutarsız beyanı kapatır.

DETERMİNİZM: saf fonksiyonlar; ağ yok, LLM yok, rastgelelik yok. `root` enjekte edilebilir
→ testler gerçek depo yerleşimine bağlı değildir.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# Depo kökü: app/orchestration/verdict_audit.py → parents[2]. Motorun bildirdiği yollar
# depo köküne GÖRELİdir; iddiaları burada dosya sistemiyle doğrularız.
_REPO_ROOT = Path(__file__).resolve().parents[2]

# Motorun yapılandırılmış kanıt bloğunu başlatan işaretçi. Verdict satırından AYRIDIR:
# verdict son satırdadır (parse_hunt_verdict onu okur), kanıt ondan ÖNCE gelir.
EVIDENCE_MARKER = "ACHILLES_HUNT_EVIDENCE"

# Asgari kapsama eşikleri — "hiç bakmadan PASS yaz" sınıfını yakalamak için taban.
# Derin av alt-sistem başına paralel tarar → gerçek bir av bunların çok üstündedir; bunlar
# yalnız GROSS tembelliği (sıfıra yakın tarama) eler, meşru odaklı bir avı reddetmeyecek
# kadar düşük tutulur. Ayarlanabilir sabitler → tek yerde, testte de kullanılır.
MIN_SCANNED_FILES = 5
MIN_SUBSYSTEMS = 2

# "PASS" beyanıyla ÇELİŞEN bulgu ciddiyetleri (büyük harfe normalize edilerek kıyaslanır).
# Motor bunlardan birini kanıtına yazıp yine de PASS derse iç-tutarsızdır → reddedilir.
_BLOCKING_SEVERITIES = frozenset({"HIGH", "BLOCKER", "CRITICAL", "SEVERE"})


def extract_evidence(output: str | None) -> dict[str, Any] | None:
    """Motor çıktısındaki yapılandırılmış kanıt bloğunu ayıkla (yoksa/bozuksa ``None``).

    ``EVIDENCE_MARKER``dan sonraki İLK JSON nesnesi ``raw_decode`` ile okunur; markdown
    kod-çiti (```json ... ```) gibi arkasındaki metin YOK SAYILIR. Herhangi bir hata
    fail-closed ``None`` döner → çağıran bunu "kanıt yok" olarak reddeder.
    """
    if not output:
        return None
    idx = output.find(EVIDENCE_MARKER)
    if idx == -1:
        return None
    rest = output[idx + len(EVIDENCE_MARKER) :]
    brace = rest.find("{")
    if brace == -1:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(rest[brace:])
    except Exception:
        # FAIL-CLOSED: HERHANGİ bir ayrıştırma hatası → None. `ValueError`/`JSONDecodeError`
        # yetmez: derinden iç-içe JSON (`[[[...`) `RecursionError` fırlatır ve o `ValueError`
        # DEĞİL `RuntimeError` alt sınıfıdır → motorun kontrol ettiği tek bir çıktı sürücüyü
        # çökertirdi (rlm-security-reviewer bulgusu). Geniş yakalama, docstring'in "her hata
        # fail-closed None döner" sözleşmesiyle bilinçli olarak hizalıdır.
        log.debug("Kanıt bloğu ayrıştırılamadı — güvenli tarafta None", exc_info=True)
        return None
    return obj if isinstance(obj, dict) else None


def _resolve_in_root(rel: Any, root: Path) -> Path | None:
    """``rel`` yolunu ``root`` altında güvenle çöz; gerçek bir dosya değilse ``None``.

    Yol-geçişi savunması: çözülen yol kökün DIŞINA çıkıyorsa (``../../etc``) reddedilir.
    Böylece motor, depo dışındaki bir dosyayı "taradım" diye sayamaz.
    """
    if not isinstance(rel, str) or not rel.strip():
        return None
    try:
        candidate = (root / rel).resolve()
        root_resolved = root.resolve()
    except (OSError, ValueError, RuntimeError):
        return None
    try:
        candidate.relative_to(root_resolved)
    except ValueError:
        return None  # kökün dışına taştı → güvenli tarafta reddet
    return candidate if candidate.is_file() else None


def _distinct_existing_files(scanned: Any, root: Path) -> int:
    """Depoda GERÇEKTEN var olan farklı dosyaların sayısı (çözülmüş yola göre tekilleştirir)."""
    if not isinstance(scanned, (list, tuple)):
        return 0
    seen: set[Path] = set()
    for item in scanned:
        resolved = _resolve_in_root(item, root)
        if resolved is not None:
            seen.add(resolved)
    return len(seen)


def _distinct_subsystems(subsystems: Any) -> int:
    """Farklı, boş-olmayan alt-sistem adlarının sayısı (büyük/küçük harf duyarsız)."""
    if not isinstance(subsystems, (list, tuple)):
        return 0
    return len({s.strip().casefold() for s in subsystems if isinstance(s, str) and s.strip()})


def _has_blocking_finding(findings: Any) -> bool:
    """Kanıttaki bulgular arasında PASS ile çelişen (HIGH/BLOCKER…) biri var mı?"""
    if not isinstance(findings, (list, tuple)):
        return False
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        sev = finding.get("severity")
        if isinstance(sev, str) and sev.strip().upper() in _BLOCKING_SEVERITIES:
            return True
    return False


def audit_hunt_evidence(output: str | None, *, root: Path | None = None) -> dict[str, Any]:
    """Motorun av "PASS" beyanını dosya sistemiyle BAĞIMSIZ doğrula.

    Yalnız verdict PASS iken çağrılması ANLAMLIdır (çağıran öyle yapar); FAIL zaten
    deep-hunt'ı bloklu tutar. Döndürülen sözlük:

    * ``ok``            — kanıt bağımsız denetimi geçti mi (PASS'in gerçekten ilerlemesi bu).
    * ``reason``        — geçmediyse Türkçe sebep (geçtiyse "").
    * ``scanned_count`` — depoda var olan farklı dosya sayısı (bağımsızca sayıldı).
    * ``subsystem_count`` — farklı alt-sistem sayısı.
    * ``claimed_files`` — motorun iddia ettiği ham dosya sayısı (var olmayanlar dahil).

    Hiçbir yan etki YOK, ağ YOK: yalnız dosya-var-mı yoklaması (salt-okuma).
    """
    base = root or _REPO_ROOT
    result: dict[str, Any] = {
        "ok": False,
        "reason": "",
        "scanned_count": 0,
        "subsystem_count": 0,
        "claimed_files": 0,
    }

    evidence = extract_evidence(output)
    if evidence is None:
        result["reason"] = (
            "Yapılandırılmış kanıt bloğu (ACHILLES_HUNT_EVIDENCE) yok ya da bozuk — "
            "motorun öz-beyanı tek kanıt olamaz (Kural 8)."
        )
        return result

    scanned = evidence.get("scanned_files")
    result["claimed_files"] = len(scanned) if isinstance(scanned, (list, tuple)) else 0
    scanned_count = _distinct_existing_files(scanned, base)
    subsystem_count = _distinct_subsystems(evidence.get("subsystems"))
    result["scanned_count"] = scanned_count
    result["subsystem_count"] = subsystem_count

    if scanned_count < MIN_SCANNED_FILES:
        result["reason"] = (
            f"Bağımsız denetim: depoda var olan taranmış dosya sayısı yetersiz "
            f"({scanned_count} < {MIN_SCANNED_FILES}) — iddia edilen tarama teyit edilemedi."
        )
        return result

    if subsystem_count < MIN_SUBSYSTEMS:
        result["reason"] = (
            f"Bağımsız denetim: taranan alt-sistem çeşitliliği yetersiz "
            f"({subsystem_count} < {MIN_SUBSYSTEMS}) — derin av kapsaması teyit edilemedi."
        )
        return result

    if _has_blocking_finding(evidence.get("findings")):
        result["reason"] = (
            "Bağımsız denetim: 'PASS' beyanı kanıttaki HIGH/BLOCKER bulguyla ÇELİŞİYOR — "
            "iç-tutarsız verdict reddedildi."
        )
        return result

    result["ok"] = True
    return result
