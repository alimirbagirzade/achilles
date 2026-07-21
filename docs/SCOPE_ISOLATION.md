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
`--disallowedTools Bash,Edit,Write,NotebookEdit,WebFetch,WebSearch,Task`. Derin av zaten
salt-okumadır (Read/Grep/Glob yeter). Bu, prompt'taki "kod değiştirme / eğitim
başlatma" talimatını **teknik olarak** zorunlu kılar.

`Task` de yasaktır: aksi halde motor, kısıtsız araç setine sahip bir **alt-ajan**
doğurup deny-list'i dolaylı olarak aşabilir (deny-list'in alt-ajanlara özyinelemeli
uygulandığı, test edilmiş bir varsayım değildir).

> Prompt talimatı bir güvenlik sınırı **değildir**: RAG'e alınan bir makale/kart
> içeriği prompt-injection ile motoru yönlendirebilir.

### 1b. Özelleştirme kanalları deny-list'in DIŞINDA (MCP + hook'lar)

Araç deny-list'i **tek başına yetmez**. Claude Code'un *özelleştirme* kanalları araç
katmanının dışında çalışır; iki ayrı denetim turunda ikisi de somut olarak bulundu:

**MCP:** `--disallowedTools` yalnız **yerleşik** araç adlarını yasaklar, `mcp__*`
araçlarını **değil**. Proje kapsamında kayıtlı `achilles` MCP sunucusu
(`mcp_server/achilles_mcp.py`), Achilles OpenAPI'sinden tool üretip
`127.0.0.1:8765`'e `httpx` ile proxy'ler — yani **Bash olmadan HTTP isteği atan bir
kanal**. Üstelik bu proxy sürücü başlığı göndermediği için istekleri `human` scope'una
düşerdi.

**Hook'lar:** `.claude/settings.json` içindeki `SessionStart`/`PreToolUse` hook'ları
Claude Code tarafından **doğrudan kabukta** çalıştırılır — `Bash` *aracı* üzerinden
değil. `-p` modunda güven (trust) diyaloğu atlandığı için **onaysız** koşarlar ve
deny-list bunları hiç görmez. Depoya hook ekleyen bir PR/enjeksiyon, motor doğduğu
anda tek bir araç çağrısı bile yapmadan `curl`/`achilles approval-approve`
çalıştırabilirdi.

**Düzeltme (sınıf-düzeyi):** spawn'a **`--safe-mode`** eklendi — CLAUDE.md, skill'ler,
plugin'ler, **hook'lar**, **MCP sunucuları**, özel komut/ajanlar ve diğer tüm
özelleştirmeler kapatılır. Kanal kanal kovalamaca yerine sınıfın tamamı kapanır.
`--strict-mcp-config` kemer-askı olarak korunur.

> `--safe-mode` CLAUDE.md **oto-keşfini** de kapatır (dosya hâlâ okunabilir). Bu yüzden
> av promptu avcıya CLAUDE.md'yi **açıkça Read ile okumasını** söyler.

> MCP vektörü bir süre **kazara** kapalıydı: insan-yalnız 6 uç
> `include_in_schema=False` olduğu için FastMCP'nin ürettiği şemada yer almıyordu. Bu
> bir savunma **değildi** — dokümanın kendisinin "koruma değildir" dediği bayrağa
> bağımlıydı.

### 1c. `hunt_ack` doğrulanmadan kabul ediliyordu

`POST /api/orchestration/start` ve `/resume`, gövdeden gelen `hunt_ack: bool`'u
doğrulamadan kabul ediyordu; `delegates.py` yalnız truthy'liğine bakar. Yani
CLAUDE.md'nin "her eğitimden önce **ZORUNLU**" dediği Kademe-2 av,
`{"hunt_ack": true}` göndermekle atlanabiliyordu — **v5 regresyonunun kök nedeni**.

**Düzeltme:** `hunt_ack=true` bir insan yetki beyanıdır → `require_human` arkasında.
Koşu başlatmanın kendisi serbest kalır (yalnız beyan kapılıdır).

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
| Araç kısıtı (`--safe-mode` + `--strict-mcp-config` + `--disallowedTools`) | **Asıl sınır.** Üçü BİRLİKTE gerekir: `--disallowedTools` yerleşik araçları kısar ama özelleştirme kanallarını (hook/plugin/MCP/özel-ajan) görmez; `--safe-mode` o sınıfın tamamını kapatır ama yerleşik araçları kısmaz. |
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
