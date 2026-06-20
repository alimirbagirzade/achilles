"""Central configuration via pydantic-settings.

All settings can be overridden by environment variables prefixed with ``ACHILLES_``
or by a local ``.env`` file. Paths are resolved relative to the project root.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = two levels up from this file (app/config/settings.py -> root)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _resolve(p: str | Path) -> Path:
    """Resolve a path relative to PROJECT_ROOT unless it is already absolute."""
    path = Path(p)
    return path if path.is_absolute() else (PROJECT_ROOT / path)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ACHILLES_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- LLM backend ---
    # "ollama"  → sadece yerel Ollama kullan
    # "openai"  → sadece OpenAI API kullan (openai_api_key gerekli)
    # "auto"    → Ollama dene; çalışmıyorsa OpenAI'ye geç
    llm_backend: str = "auto"

    # --- Ollama (yerel) ---
    ollama_host: str = "http://127.0.0.1:11434"  # localhost yerine IP — Windows IPv6 sorununu önler
    llm_model: str = "qwen3:4b"
    # Modeli sorgu sonrası ne kadar yüklü tutsun. RAM darsa (ör. aynı anda LoRA eğitimi)
    # "0" → hemen boşalt (eğitimle ~7GB çakışmayı önler). Varsayılan "30s"; büyük
    # makinede ".env: ACHILLES_OLLAMA_KEEP_ALIVE=5m" hızlı ardışık sorgu için.
    ollama_keep_alive: str = "30s"
    embed_model: str = "nomic-embed-text"

    # --- OpenAI (bulut, opsiyonel) ---
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"

    # --- Anthropic (bulut, opsiyonel) ---
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5-20251001"

    # --- Google (bulut, opsiyonel) ---
    google_api_key: str = ""
    google_model: str = "gemini-2.0-flash"

    # mlx-lm LoRA eğitimi için HuggingFace model ID (Ollama formatı geçersiz)
    mlx_base_model: str = "mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit"

    # PEFT (Windows/Linux) LoRA eğitimi için HuggingFace base model.
    # MLX 4-bit formatı transformers ile yüklenemez; bu yüzden ayrı HF model gerekir.
    # DİKKAT: Ollama'daki `qwen3:4b` tag'i Instruct-2507 checkpoint'idir (256K ctx);
    # adapter'ın Ollama'da çalışması için eğitim base'i BİREBİR aynı olmalı.
    peft_base_model: str = "Qwen/Qwen3-4B-Instruct-2507"

    # --- Storage ---
    sqlite_path: Path = Field(default=Path("storage/sqlite/achilles_trader_ai.db"))
    chroma_path: Path = Field(default=Path("vector_db/chroma"))

    # --- RAG ---
    rag_top_k: int = 6
    chunk_size: int = 1200
    chunk_overlap: int = 200
    # Retrieval robustluğu (eğitimsiz kalite artışı — yazılı ama bağlanmamış
    # bileşenleri canlı yola alır). Hepsi LLM-free; çevrimdışı testlerle uyumlu.
    rag_rerank: bool = True  # over-fetch + heuristik reranker (semantik+kw+bölüm+formül)
    rag_overfetch: int = 4  # dense'ten top_k * overfetch aday çek, rerank et, top_k'ya kes
    # BM25 + dense hibrit (Faz A3): keyword adaylarını ekler. Korpus Chroma'dan lazy
    # kurulur; boşsa sessizce dense-only kalır → çevrimdışı testlerde davranış değişmez.
    rag_hybrid: bool = True
    # Cross-encoder reranker (Faz A8): en yüksek etkili sıralayıcı ama ağır (model
    # indirme + CPU latency). OPT-IN. Açmak için: ACHILLES_RAG_CROSS_ENCODER=true +
    # `uv pip install sentence-transformers`. Model yoksa heuristik reranker'a düşer.
    rag_cross_encoder: bool = False
    # Varsayılan hafif baz model (~280MB, ağırlıklı zh/en). Gerçek çok-dillilik (TR dahil
    # 100+ dil) için `BAAI/bge-reranker-v2-m3` önerilir (daha ağır ~2GB; modest CPU'da
    # latency artar). Modeli ACHILLES_RAG_CROSS_ENCODER_MODEL ile değiştir.
    rag_cross_encoder_model: str = "BAAI/bge-reranker-base"
    # FlashRank reranker (ONNX-int8 cross-encoder, torch GEREKMEZ): bge-reranker CPU'da
    # >15s/sorgu (kullanılamaz) iken FlashRank ~30-100ms (web-araştırma; bkz. roadmap Zincir 3).
    # OPT-IN, cross_encoder'a göre ÖNCELİKLİ. Açmak için ACHILLES_RAG_FLASHRANK=true +
    # `uv pip install flashrank`. Model yoksa heuristiğe düşer. A/B ile doğrulanmalı.
    rag_flashrank: bool = False
    rag_flashrank_model: str = "ms-marco-MiniLM-L-12-v2"
    # Reciprocal Rank Fusion (RRF) füzyon modu (opt-in): dense + BM25 sıralı listelerini
    # skor normalize etmeden sıra-tabanlı birleştirir (heuristik rerank yerine). Skor
    # kalibrasyonu gerektirmez → karşılaştırılamaz skorlu kaynaklarda sağlam. LLM-free,
    # deterministik. Varsayılan kapalı (alpha/rerank davranışı değişmez); açmak için
    # ACHILLES_RAG_RRF=true. RRF sabiti `rag_rrf_k` (yaygın varsayılan 60).
    rag_rrf: bool = False
    rag_rrf_k: int = 60
    # Graf-tabanlı retrieval (SPRIG-lite, opt-in): term–chunk bipartite graf üzerinde
    # dense-hit'lerden tohumlanmış Personalized PageRank ile çok-hop ilgili chunk'ları
    # yüzeye çıkarır; sonucu dense ile RRF ile füzyonlar. LLM-free, deterministik, CPU-only.
    # Dense'in kaçırdığı (paylaşılan terimle bağlı) chunk'ları getirebilir. Varsayılan kapalı
    # → mevcut retrieval davranışı değişmez. Açmak için ACHILLES_RAG_GRAPH=true.
    rag_graph: bool = False
    rag_graph_damping: float = 0.85  # PageRank yayılma katsayısı (1-damping = restart)
    rag_graph_iters: int = 20  # sabit iterasyon (determinizm)
    # Contextual Retrieval (Faz P2): chunk'ı embed etmeden önce "başlık / bölüm:" ön-eki
    # ekler (orijinal metin Chroma document'ında korunur). Tutarlılık için TÜM korpus
    # aynı ayarla embed edilmeli → açmadan önce `achilles reindex-contextual` çalıştır.
    # Varsayılan kapalı (yarı-prefix'li korpus tutarsızlık yaratırdı).
    rag_contextual_embed: bool = False

    # --- Trading ---
    default_market: str = "XAUUSD"
    default_timeframe: str = "15m"

    # --- Behavior ---
    allow_fake_embeddings: bool = True
    log_level: str = "INFO"

    # --- Sentez aynalama (synthesis mirror) ---
    # Üretilen her sentez makalesi (reports/synthesis/sentez_*.md) bu dizine de
    # kopyalanır. Boşsa aynalama kapalıdır (varsayılan → test/CI davranışı değişmez).
    # Makineye özel yol .env içinde verilir: ACHILLES_SYNTHESIS_MIRROR_DIR=...
    synthesis_mirror_dir: str = ""

    # --- Auto-LoRA Pipeline ---
    auto_lora_enabled: bool = False  # otomatik döngü; varsayılan kapalı
    auto_lora_min_cards: int = 20  # eğitim başlamadan gereken minimum kart
    auto_lora_check_interval_min: int = 60  # kaç dakikada bir kontrol
    auto_lora_eval_threshold: float = 0.5  # eval pass_rate eşiği

    # --- Web (FastAPI) ---
    # Güvenlik: varsayılan olarak SADECE localhost'a bağlanır (dışarı açılmaz).
    web_host: str = "127.0.0.1"
    web_port: int = 8765
    # Boşsa kimlik doğrulama kapalıdır (yalnız localhost güvenli sayılır).
    # Sunucuyu ağa açacaksan MUTLAKA güçlü bir token ata.
    api_token: str = ""
    # CORS: yalnız bu kökenlere izin verilir (frontend aynı origin'den sunulur).
    cors_origins: str = "http://127.0.0.1:8765,http://localhost:8765"
    # PDF upload üst sınırı (MB).
    max_upload_mb: int = 100
    # Basit hız sınırı: IP başına dakikadaki istek.
    rate_limit_per_min: int = 120
    # Yükleme uçlarına (PDF/CSV) ek, daha sıkı limit — ağ DoS / disk doldurma.
    upload_rate_limit_per_min: int = 20
    # Host-header saldırısı: boş = kısıt yok (lokal). Ağa açarken "alanadi.com,1.2.3.4" ver.
    trusted_hosts: str = ""
    # TLS (reverse proxy/HTTPS) arkasındaysan true → Strict-Transport-Security başlığı.
    hsts_enabled: bool = False

    # --- Derived dirs (not env-configurable) ---
    @property
    def root(self) -> Path:
        return PROJECT_ROOT

    @property
    def sqlite_file(self) -> Path:
        return _resolve(self.sqlite_path)

    @property
    def chroma_dir(self) -> Path:
        return _resolve(self.chroma_path)

    @property
    def raw_pdf_dir(self) -> Path:
        return PROJECT_ROOT / "data" / "papers" / "raw_pdf"

    @property
    def extracted_text_dir(self) -> Path:
        return PROJECT_ROOT / "data" / "papers" / "extracted_text"

    @property
    def metadata_dir(self) -> Path:
        return PROJECT_ROOT / "data" / "papers" / "metadata"

    @property
    def jsonl_dir(self) -> Path:
        return PROJECT_ROOT / "data" / "training" / "jsonl"

    @property
    def market_raw_dir(self) -> Path:
        return PROJECT_ROOT / "data" / "market" / "raw"

    @property
    def reports_dir(self) -> Path:
        return PROJECT_ROOT / "reports"

    @property
    def adapters_dir(self) -> Path:
        return PROJECT_ROOT / "models" / "adapters"

    @property
    def agent_runs_dir(self) -> Path:
        """Agent runtime gözlemcisi (Phase 1) — koşu başına JSONL günlükleri."""
        return PROJECT_ROOT / "reports" / "agent_runs"

    @property
    def prompts_dir(self) -> Path:
        return PROJECT_ROOT / "app" / "prompts"

    def ensure_dirs(self) -> None:
        """Create all runtime directories that must exist."""
        for d in (
            self.sqlite_file.parent,
            self.chroma_dir,
            self.raw_pdf_dir,
            self.extracted_text_dir,
            self.metadata_dir,
            self.jsonl_dir,
            self.market_raw_dir,
            self.adapters_dir,
            self.reports_dir / "papers",
            self.reports_dir / "training",
            self.reports_dir / "backtests",
            self.reports_dir / "evals",
            self.reports_dir / "agent_runs",
        ):
            d.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()


def configure_logging(level: str | None = None) -> None:
    settings = get_settings()
    logging.basicConfig(
        level=(level or settings.log_level).upper(),
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
