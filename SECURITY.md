# Güvenlik (SECURITY.md)

Achilles Trader AI **yerel-öncelikli bir araştırma aracıdır**. Web arayüzü,
çekirdek motoru saran ince bir katmandır. Tasarım ilkesi: **varsayılan olarak
dışarı kapalı, katmanlı savunma.**

## Tehdit modeli

| Varlık | Tehdit | Savunma |
|--------|--------|---------|
| Yerel makine | İstemeden ağa açılma | Varsayılan bind `127.0.0.1`; `0.0.0.0` değil |
| API uçları | Yetkisiz erişim (ağa açılırsa) | İsteğe bağlı bearer token (`ACHILLES_API_TOKEN`), sabit-zamanlı karşılaştırma |
| Upload | Kötü amaçlı/sahte dosya | Uzantı + `%PDF-` sihirli bayt + boyut limiti |
| Dosya sistemi | Path traversal (`../`) | `sanitize_filename` + `safe_destination` (hedef dizin doğrulaması) |
| Tarayıcı | XSS / clickjacking | CSP (`script-src 'self'`, inline yok), `X-Frame-Options: DENY`, `nosniff` |
| Servis | DoS / brute force | IP başına hız sınırı (kayan pencere) |
| Veritabanı | SQL injection | SQLAlchemy ORM (parametreli sorgular) |
| Strateji girdisi | Kod enjeksiyonu | `eval`/`exec` YOK; kurallar yalnız güvenli regex ile parse edilir |
| Sırlar | Kod içinde sızıntı | `.env` (Git-ignore); kodda hardcoded sır yok |

## Varsayılan davranış (güvenli)

- Sunucu yalnız **localhost**'a bağlanır (`ACHILLES_WEB_HOST=127.0.0.1`).
- Token boşsa kimlik doğrulama atlanır — **çünkü dışarıdan erişilemez.**
- Tüm yanıtlara güvenlik başlıkları eklenir.
- Yüklenen PDF'ler `data/papers/raw_pdf/` içinde temizlenmiş adla saklanır.

## Sunucuyu ağa/uzağa açacaksan (zorunlu adımlar)

1. **Güçlü token ata**:
   ```bash
   # .env
   ACHILLES_API_TOKEN=$(openssl rand -hex 32)
   ```
2. Tüm `/api/*` istekleri `Authorization: Bearer <token>` gerektirir.
3. Tercihen bir **reverse proxy** (nginx/caddy) arkasında **TLS** ile sun.
   Uygulamayı doğrudan internete koyma.
4. Gerekirse `ACHILLES_WEB_HOST` ve `ACHILLES_CORS_ORIGINS`'i daralt.
5. Hız sınırını sıkılaştır: `ACHILLES_RATE_LIMIT_PER_MIN`.

## Bilinçli kapsam dışı (MVP)

- Canlı borsa bağlantısı / emir gönderme **yok**.
- Çoklu kullanıcı / rol yönetimi yok (tek kullanıcı yerel araç).
- Kullanıcı hesapları / parola saklama yok (yalnız tek paylaşılan token).

## İlgili kod

- `app/web/security.py` — auth, hız sınırı, başlıklar, upload doğrulama
- `app/web/server.py` — middleware + uçlar
- `app/trading/strategy_ir.py` — güvenli kural ayrıştırma (kod yürütme yok)

## Açık bildirimi

Bu yazılım **eğitim/araştırma** amaçlıdır, yatırım tavsiyesi değildir.
Bir güvenlik açığı bulursan lütfen sorumlu biçimde bildir.
