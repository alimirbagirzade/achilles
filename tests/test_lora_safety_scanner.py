"""Güvenlik / sır tarayıcı testleri."""

from __future__ import annotations

from app.lora.safety_scanner import scan_for_secrets


def test_clean_text_passes() -> None:
    """Temiz metin güvenlik taramasını geçmeli."""
    result = scan_for_secrets("RSI bir momentum göstergesidir.")
    assert result.passed is True
    assert result.violations == []


def test_api_key_pattern_rejected() -> None:
    """32+ karakter alfanumerik token reddedilmeli."""
    result = scan_for_secrets("key: ABCDEFGHIJ1234567890abcdefghij1234567890")
    assert result.passed is False


def test_credential_assignment_rejected() -> None:
    """password= ataması reddedilmeli."""
    result = scan_for_secrets("password=hunter2")
    assert result.passed is False
    assert any("credential" in v for v in result.violations)


def test_email_rejected() -> None:
    """E-posta adresi kişisel veri olarak reddedilmeli."""
    result = scan_for_secrets("İletişim: ali@example.com")
    assert result.passed is False
    assert any("email" in v for v in result.violations)


def test_financial_directive_rejected() -> None:
    """Kesin al/sat yönlendirmesi reddedilmeli."""
    result = scan_for_secrets("Şimdi al, garanti kar var.")
    assert result.passed is False
    assert any("finansal" in v for v in result.violations)


def test_financial_directive_uppercase_rejected() -> None:
    """BÜYÜK HARF Türkçe yönlendirme de yakalanmalı (İ→i+nokta bypass'ı kapalı)."""
    # str.lower() 'ŞİMDİ AL'ı 'şi̇mdi̇ al'a çevirip kaçırıyordu — tr_fold engeller.
    result = scan_for_secrets("ŞİMDİ AL pozisyona gir, GARANTİ KÂR var.")
    assert result.passed is False
    assert any("finansal" in v for v in result.violations)


def test_national_id_rejected() -> None:
    """11 haneli TC kimlik deseni reddedilmeli."""
    result = scan_for_secrets("Kimlik: 12345678901")
    assert result.passed is False


def test_empty_text_passes() -> None:
    """Boş metin sorunsuz geçmeli."""
    assert scan_for_secrets("").passed is True
