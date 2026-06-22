"""Güvenlik / sır tarayıcı testleri."""

from __future__ import annotations

from app.lora.safety_scanner import (
    _detect_api_key,
    _detect_national_id,
    _valid_tc_checksum,
    scan_for_secrets,
)


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


# --------------------------------------------------------------------------- #
# national_id daraltması (Kademe-2 bulgusu B5): checksum + bağlam, çıplak değil
# --------------------------------------------------------------------------- #


def test_national_id_volume_number_not_flagged() -> None:
    """11 haneli hacim/zaman-damgası (checksum'sız, bağlamsız) TC sanılmamalı.

    NOT: `scan_for_secrets` düzeyinde çıplak 11 haneli sayı ayrıca gevşek `phone`
    desenine takılır (ayrı, B5-dışı over-match); bu yüzden national_id daraltmasını
    doğrudan `_detect_national_id` üzerinde doğruluyoruz.
    """
    assert _detect_national_id("Islem hacmi 12345678901 birim gerceklesti") is False
    assert _detect_national_id("zaman damgasi 16785551234 olarak kaydedildi") is False
    assert _detect_national_id("veri kumesi 98765432100 satir icerir") is False


def test_national_id_invalid_checksum_no_context_not_flagged() -> None:
    """Geçersiz checksum + bağlam anahtarı yok → ihlal değil."""
    assert _valid_tc_checksum("12345678901") is False
    assert _detect_national_id("parametre 12345678901 ile devam") is False


def test_national_id_context_word_not_substring_false_positive() -> None:
    """'batch'/'tcp' içindeki 'tc' bağlam sayılmamalı (kelime sınırı koruması)."""
    assert _detect_national_id("batch boyutu 12345678901 ornek") is False
    assert _detect_national_id("tcp port 12345678901 acik") is False


def test_national_id_valid_checksum_rejected() -> None:
    """Gerçek (checksum-geçerli) TC kimlik, etiketsiz bile yakalanmalı."""
    assert _valid_tc_checksum("19876543238") is True
    result = scan_for_secrets("Musteri 19876543238 kaydedildi")
    assert result.passed is False
    assert any("national_id" in v for v in result.violations)


def test_national_id_labeled_context_rejected() -> None:
    """Bağlam anahtarı ('kimlik') + 11 hane → checksum tutmasa da yakalanmalı."""
    assert _detect_national_id("TC kimlik no: 12345678901") is True


# --------------------------------------------------------------------------- #
# api_key daraltması (Kademe-2 bulgusu B5): entropi + sınıf + ön-ek, çıplak değil
# --------------------------------------------------------------------------- #


def test_api_key_long_hash_not_flagged() -> None:
    """Uzun saf-hex hash (git SHA / sha256) sır sanılmamalı (≤2 karakter sınıfı)."""
    sha1 = "a94a8fe5ccb19ba61c4c0873d391e987982fbbd3"
    sha256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert _detect_api_key(f"commit {sha1} olarak etiketlendi") is False
    assert scan_for_secrets(f"ozet degeri {sha256} olur").passed is True


def test_api_key_long_identifier_not_flagged() -> None:
    """Uzun değişken adı / underscore'lu tanımlayıcı sır sanılmamalı."""
    assert (
        scan_for_secrets("feature_importance_gradient_boosting_classifier_v2 katsayisi").passed
        is True
    )
    assert _detect_api_key("alpha_beta_gamma_delta_epsilon_zeta_eta_theta_iota") is False


def test_api_key_known_prefix_rejected() -> None:
    """Bilinen sır ön-ekleri (GitHub PAT / AWS access key) yakalanmalı."""
    gh = scan_for_secrets("token ghp_1234567890abcdefghABCDEFGH1234567890")
    assert gh.passed is False
    assert any("api_key" in v for v in gh.violations)

    aws = scan_for_secrets("AKIAIOSFODNN7EXAMPLE yapilandirmasi")
    assert aws.passed is False
    assert any("api_key" in v for v in aws.violations)
