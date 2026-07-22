"""verdict_audit — av verdict'inin bağımsız doğrulaması (P8, Kural 8).

Çevrimdışı + deterministik: `root` enjekte edilir → gerçek depo yerleşimine bağlı değil.
Kritik iddia: motorun 'PASS' beyanı TEK kanıt olamaz; yapısal kanıt dosya sistemiyle teyit
edilmeli. Sahte/eksik/iç-tutarsız kanıt reddedilir; gerçek kanıt geçer.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.orchestration import verdict_audit


def _make_files(root: Path, n: int, subdir: str = "sub") -> list[str]:
    """`root/subdir` altında `n` gerçek dosya yarat, depo-göreli yollarını döndür."""
    d = root / subdir
    d.mkdir(parents=True, exist_ok=True)
    rels = []
    for i in range(n):
        f = d / f"f{i}.py"
        f.write_text("# saf içerik\n", encoding="utf-8")
        rels.append(f"{subdir}/f{i}.py")
    return rels


def _evidence(scanned: list[str], subsystems: list[str], findings: list[dict] | None = None) -> str:
    payload = {"scanned_files": scanned, "subsystems": subsystems, "findings": findings or []}
    return (
        "denetim raporu...\n"
        f"{verdict_audit.EVIDENCE_MARKER}\n```json\n{json.dumps(payload)}\n```\n"
        "ACHILLES_HUNT_VERDICT: PASS\n"
    )


# ── extract_evidence ──────────────────────────────────────────────────────────


def test_extract_evidence_fenced_and_plain() -> None:
    payload = {"scanned_files": ["a.py"], "subsystems": ["x"], "findings": []}
    fenced = f"{verdict_audit.EVIDENCE_MARKER}\n```json\n{json.dumps(payload)}\n```\nson"
    plain = f"{verdict_audit.EVIDENCE_MARKER} {json.dumps(payload)} kuyruk metni"
    assert verdict_audit.extract_evidence(fenced) == payload
    assert verdict_audit.extract_evidence(plain) == payload


def test_extract_evidence_missing_or_broken() -> None:
    assert verdict_audit.extract_evidence(None) is None
    assert verdict_audit.extract_evidence("hiç kanıt yok") is None
    assert verdict_audit.extract_evidence(f"{verdict_audit.EVIDENCE_MARKER} {{bozuk json") is None
    # JSON ama nesne değil (liste) → reddedilir
    assert verdict_audit.extract_evidence(f"{verdict_audit.EVIDENCE_MARKER} [1,2,3]") is None


def test_extract_evidence_recursion_error_fail_closed(monkeypatch) -> None:
    """`raw_decode` `RecursionError` fırlatırsa fail-closed None (sürücüyü çökertmez).

    rlm-security-reviewer bulgusu: derinden iç-içe JSON `RecursionError` fırlatır ve o
    `ValueError` DEĞİL `RuntimeError` alt sınıfıdır → dar `except (ValueError, ...)` kaçırırdı.
    Tetikleyen ÖZYİNELEME DERİNLİĞİ platforma göre değişir (CI'da 5000 sorunsuz ayrışabilir),
    bu yüzden istisnayı DOĞRUDAN zorlarız → handler'ı deterministik test ederiz.
    """

    def boom(self, s, idx=0):
        raise RecursionError("derin iç-içe")

    monkeypatch.setattr(json.JSONDecoder, "raw_decode", boom)
    payload = f'{verdict_audit.EVIDENCE_MARKER} {{"scanned_files": []}}'
    assert verdict_audit.extract_evidence(payload) is None
    # Uçtan uca: audit da çökmeden reddetmeli.
    res = verdict_audit.audit_hunt_evidence(
        f"{payload}\nACHILLES_HUNT_VERDICT: PASS", root=Path(".")
    )
    assert res["ok"] is False


# ── audit_hunt_evidence ───────────────────────────────────────────────────────


def test_missing_evidence_rejected() -> None:
    res = verdict_audit.audit_hunt_evidence("ACHILLES_HUNT_VERDICT: PASS", root=Path("."))
    assert res["ok"] is False
    assert "kanıt" in res["reason"].lower()


def test_valid_evidence_passes(tmp_path: Path) -> None:
    scanned = _make_files(tmp_path, 3, "orchestration") + _make_files(tmp_path, 2, "web")
    out = _evidence(scanned, ["orchestration", "web"])
    res = verdict_audit.audit_hunt_evidence(out, root=tmp_path)
    assert res["ok"] is True
    assert res["scanned_count"] == 5 and res["subsystem_count"] == 2


def test_too_few_files_rejected(tmp_path: Path) -> None:
    scanned = _make_files(tmp_path, 2, "orchestration")
    out = _evidence(scanned, ["orchestration", "web"])
    res = verdict_audit.audit_hunt_evidence(out, root=tmp_path)
    assert res["ok"] is False and "dosya" in res["reason"]
    assert res["scanned_count"] == 2


def test_too_few_subsystems_rejected(tmp_path: Path) -> None:
    scanned = _make_files(tmp_path, 6, "orchestration")
    out = _evidence(scanned, ["orchestration"])  # tek alt-sistem
    res = verdict_audit.audit_hunt_evidence(out, root=tmp_path)
    assert res["ok"] is False and "alt-sistem" in res["reason"]


def test_nonexistent_files_do_not_count(tmp_path: Path) -> None:
    """Uydurulmuş yollar depoda yok → sayılmaz → eşik altında reddedilir."""
    fake = [f"uydurma/yok{i}.py" for i in range(9)]
    out = _evidence(fake, ["orchestration", "web"])
    res = verdict_audit.audit_hunt_evidence(out, root=tmp_path)
    assert res["ok"] is False
    assert res["claimed_files"] == 9 and res["scanned_count"] == 0


def test_path_traversal_rejected(tmp_path: Path) -> None:
    """Kök dışına (../) çıkan yollar sayılmaz (yol-geçişi savunması)."""
    outside = tmp_path.parent / "disarida.py"
    outside.write_text("x\n", encoding="utf-8")
    scanned = [*_make_files(tmp_path, 4, "orchestration"), "../disarida.py"]
    out = _evidence(scanned, ["orchestration", "web"])
    res = verdict_audit.audit_hunt_evidence(out, root=tmp_path)
    # 4 gerçek + kök dışı sayılmaz = 4 < 5 → reddedilir
    assert res["scanned_count"] == 4 and res["ok"] is False


def test_pass_with_high_finding_is_inconsistent(tmp_path: Path) -> None:
    """PASS derken kanıtta HIGH bulgu listelemek iç-tutarsız → reddedilir."""
    scanned = _make_files(tmp_path, 3, "orchestration") + _make_files(tmp_path, 2, "web")
    out = _evidence(
        scanned,
        ["orchestration", "web"],
        findings=[{"severity": "HIGH", "file": "x.py", "summary": "sızıntı"}],
    )
    res = verdict_audit.audit_hunt_evidence(out, root=tmp_path)
    assert res["ok"] is False and "HIGH/BLOCKER" in res["reason"]


def test_medium_low_findings_allowed(tmp_path: Path) -> None:
    """MEDIUM/LOW bulgular PASS ile çelişmez (yalnız HIGH/BLOCKER kapatır)."""
    scanned = _make_files(tmp_path, 3, "orchestration") + _make_files(tmp_path, 2, "web")
    out = _evidence(
        scanned,
        ["orchestration", "web"],
        findings=[{"severity": "MEDIUM", "file": "x.py", "summary": "ufak"}],
    )
    res = verdict_audit.audit_hunt_evidence(out, root=tmp_path)
    assert res["ok"] is True


def test_duplicate_files_counted_once(tmp_path: Path) -> None:
    """Aynı dosyayı tekrar tekrar listelemek kapsamayı ŞİŞİREMEZ."""
    one = _make_files(tmp_path, 1, "orchestration")
    out = _evidence(one * 9, ["orchestration", "web"])
    res = verdict_audit.audit_hunt_evidence(out, root=tmp_path)
    assert res["scanned_count"] == 1 and res["ok"] is False
