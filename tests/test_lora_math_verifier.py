"""Matematik / istatistik doğrulayıcı testleri."""

from __future__ import annotations

from app.lora.math_verifier import verify_math_content


def test_clean_text_passes_without_review() -> None:
    """Temiz metin geçmeli ve inceleme gerektirmemeli."""
    result = verify_math_content("RSI 0 ile 100 arasında değer alan bir osilatördür.")
    assert result.passed is True
    assert result.requires_review is False
    assert result.issues == []


def test_lookahead_bias_flagged_for_review() -> None:
    """Look-ahead bias terimi inceleme işaretlemeli."""
    result = verify_math_content("Bu strateji look-ahead bias içeriyor olabilir.")
    assert result.requires_review is True
    assert any("look-ahead" in issue for issue in result.issues)


def test_overconfident_phrase_fails() -> None:
    """Aşırı emin yatırım ifadesi blocker olmalı (passed=False)."""
    result = verify_math_content("Bu strateji kesinlikle garanti kazandırır.")
    assert result.passed is False
    assert any("garanti" in issue for issue in result.issues)


def test_overconfident_uppercase_fails() -> None:
    """BÜYÜK HARF aşırı emin ifade de blocker olmalı (Türkçe İ bypass'ı kapalı)."""
    result = verify_math_content("BU STRATEJİ KESİNLİKLE GARANTİ KAZANDIRIR.")
    assert result.passed is False
    assert result.issues


def test_suspicious_high_return_flagged() -> None:
    """Aşırı yüksek getiri iddiası inceleme işaretlemeli."""
    result = verify_math_content("Yıllık getiri %5000 olur.")
    assert result.requires_review is True
    assert any("getiri" in issue for issue in result.issues)


def test_risk_percentage_over_100_flagged() -> None:
    """%100'ü aşan risk yüzdesi tutarsızlık olarak işaretlenmeli."""
    result = verify_math_content("Pozisyon başına risk %150 olmalı.")
    assert result.requires_review is True
    assert any("risk" in issue.lower() for issue in result.issues)


def test_empty_text_passes() -> None:
    """Boş metin sorunsuz geçmeli."""
    result = verify_math_content("")
    assert result.passed is True
    assert result.requires_review is False
