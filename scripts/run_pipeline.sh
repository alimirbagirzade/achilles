#!/usr/bin/env bash
# Örnek tam pipeline: araştırma -> dataset -> backtest.
# PDF'ler data/papers/raw_pdf/ içinde olmalı (yoksa ingest adımı atlanır).
set -euo pipefail

cd "$(dirname "$0")/.."
export ACHILLES_ALLOW_FAKE_EMBEDDINGS=true
RUN=$([ -x "$(command -v uv)" ] && echo "uv run" || echo "")

$RUN achilles init

if compgen -G "data/papers/raw_pdf/*.pdf" > /dev/null; then
  echo "==> PDF'ler indeksleniyor"
  $RUN achilles ingest
  $RUN achilles papers
  echo "==> Örnek RAG sorusu (Ollama varsa kaynaklı yanıt, yoksa ham parçalar)"
  $RUN achilles ask "Bu literatürdeki ana trading bulgusu nedir?" || true
  echo "==> Eğitim verisi (knowledge card'lardan) üretiliyor"
  $RUN achilles dataset || true
else
  echo "(!) data/papers/raw_pdf/ içinde PDF yok — araştırma adımları atlanıyor."
fi

echo "==> Sentetik veri + backtest"
$RUN achilles gen-data
$RUN achilles backtest data/market/raw/synthetic.csv

echo "==> Disiplin eval seti (Ollama varsa)"
$RUN achilles evaluate evals/discipline_core.jsonl || echo "(Ollama yok — eval atlandı)"

echo "✅ Pipeline tamam."
