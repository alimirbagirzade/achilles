# Scope izolasyonu — sürücü motoru vs insan yetkisi

**Amaç:** Achilles kendi motorunu doğurur (`app/orchestration/driver.py` → headless
`claude -p`). Bu motorun **kendi eğitimini onaylaması** ve **kill-switch'i temizlemesi**
engellenmelidir. CLAUDE.md **Kural 8** ancak bu ayrım varsa anlamlıdır.

## Düzeltilen zafiyet

Denetim öncesi durum:

| Uç | Sorun |
|----|-------|
| `POST /api/approvals/{id}/approve` | Motor kendi eğitim onayını verebiliyordu |
| `POST /api/supervisor/clear-stop-all` | Motor kill-switch'i temizleyebiliyordu |
| `POST /api/training/run` | Motor gerçek eğitimi başlatabiliyordu |
| `POST /api/auto-lora/train` · `/promote` | AYNI onay-tüketim yolu; kapıda değildi |
| `app/web/security.py:66` | `api_token` boşsa doğrulama **tamamen** atlanıyordu |

## İki kimlik seviyesi

- **`human`** — web UI / CLI. Varsayılan; başlık göndermeyen her istek.
- **`driver`** — doğurulan motor. `X-Achilles-Driver-Token` + `X-Achilles-Run-Id`
  başlıklarıyla kendini tanıtır.

`require_human` kapısı olan uçlarda `driver` **403** alır. Sürücü token'ı
`Authorization` başlığında **asla** kabul edilmez → yanlışlıkla insan yoluna düşemez.
Geçersiz sürücü token'ı **401**'dir, sessizce `human`'a **düşmez** (aksi halde geçersiz
token göndermek bir yetki yükseltmesi olurdu).

Sürücü token'ı: `secrets.token_urlsafe(32)`, sha256-hash'li saklanır, bir `run_id`'ye
bağlıdır, TTL ile sınırlıdır ve koşu bitince `revoke_run` ile iptal edilir.

> **"Tek-koşuluk" ne demek?** Token *bir koşuya* aittir: başka bir `run_id` ile
> kullanılamaz, yeniden mint eskisini iptal eder ve koşu bitince ölür. Doğrulama
> token'ı **tüketmez** — sürücü token'ı bir *kimlik etiketi*dir, tek kullanımlık bir
> yetki bileti değil. (Her doğrulamada tüketmek, motorun meşru bir salt-okuma
> çağrısından sonra kimliğini kaybetmesine ve sonraki her isteğinin 401 almasına yol
> açardı — bu da ileride "geçersizse human'a düş" gevşetmesine baskı yaratırdı ki bu
> tam olarak orijinal açığı geri açar.) Tek-kullanımlık tüketim, gerçek yetkinin
> verildiği yerde kalır: `approvals.require_fresh_approval`.

## ⚠️ Asıl sınır HTTP katmanı DEĞİLDİR

Uygulama öncesi güvenlik denetimi iki **BLOCKER** yakaladı; ikisi de HTTP-katmanı
scope izolasyonunu tek başına **tiyatro** haline getiriyordu:

### 1. CLI, kimlik doğrulamasını tamamen atlar

`uv run achilles approval-approve <id>` ve `clear-stop-all`, doğrudan
`approvals.approve()` / `supervisor.clear_stop_all()` çağırır — **hiçbir token
kontrolü yoktur**. Bash aracı olan bir motor HTTP'ye hiç dokunmadan aynı sonuca ulaşır.

**Düzeltme:** motor artık araç-seviyesinde kısıtlı doğurulur —
`--disallowedTools Bash,Edit,Write,NotebookEdit,WebFetch,WebSearch`. Derin av zaten
salt-okumadır (Read/Grep/Glob yeter). Bu, prompt'taki "kod değiştirme / eğitim
başlatma" talimatını **teknik olarak** zorunlu kılar.

> Prompt talimatı bir güvenlik sınırı **değildir**: RAG'e alınan bir makale/kart
> içeriği prompt-injection ile motoru yönlendirebilir.

### 2. `.env` fallback, ortam temizliğini etkisiz kılıyordu

`Settings` `env_file=".env"` kullanır. `os.environ`'dan `ACHILLES_API_TOKEN`'ı
**silmek yetmez** — çocuk süreç aynı `cwd`'de çalıştığı için token'ı dotenv'den geri
okur. Deneyle doğrulandı:

```
anahtar silinmiş  -> 'secret_human_token'   # ← sızıntı
anahtar ""ye ezilmiş -> ''                  # ← doğru
```

**Düzeltme:** `build_child_env` anahtarı silmez, açıkça **boş string'e ezer** (env
kaynağı pydantic-settings'te dotenv'den önceliklidir).

## Dürüst sınır — neyi İDDİA ETMİYORUZ

`api_token` **boşken** (şu anki varsayılan) bu katman **kriptografik bir sınır
değildir.** Aynı OS kullanıcısı altındaki bir süreç, sürücü başlığını hiç göndermeyip
düpedüz insan istemcisi gibi davranabilir; loopback sunucuya erişimi olan yerel bir
süreç için hiçbir başlık şeması bunu engelleyemez. (Cookie / Origin / same-origin
teslim de çare değildir: düz HTTP'de "tarayıcı" ile "yerel ajan" arasında
kriptografik fark yoktur — başlıklar veridir, taklit edilebilir.)

Bu yüzden koruma **katmanlıdır** ve gücü şuna bağlıdır:

| Durum | Gerçek koruma |
|-------|---------------|
| Araç kısıtı (`--disallowedTools`) | **Asıl sınır.** Bash/Write olmayan motor ne CLI çalıştırabilir ne HTTP isteği atabilir. |
| `api_token` **atanmış** | Gerçek yetki sınırı: çocuğun ortamı temizlenir, insan token'ını bilemez. |
| `api_token` **boş** | Yalnız derinlemesine savunma + gürültülü başlangıç uyarısı. Kriptografik garanti **yok**. |

Bu nedenle sunucu, `api_token` boşken başlangıçta **WARNING** loglar — sessiz "auth
kapalı" durumu belirgin hale getirilir.

**Öneri:** ağa açmıyor olsan bile `ACHILLES_API_TOKEN` ata; sürücü izolasyonu ancak o
zaman gerçek bir sınır olur.

### `include_in_schema=False` bir güvenlik kontrolü DEĞİLDİR

İnsan-yalnız uçlar OpenAPI/`/api/docs` çıktısından gizlenir. Bu **yalnız dokümantasyon
gizlemesidir**; routing'i etkilemez ve yolu bilen herkes uca erişebilir. Erişim
kontrolü **tamamen** `require_human`'dan gelir. Bu bayrak kaldırılsa bile koruma sürer;
tersi doğru değildir.
