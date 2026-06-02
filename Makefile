# Achilles Trader AI — geliştirme hedefleri
# uv varsa onu, yoksa pip/python'u kullanır.

UV := $(shell command -v uv 2> /dev/null)

.PHONY: help install test lint format typecheck run clean gen-data ci

help:
	@echo "Hedefler:"
	@echo "  install    - bağımlılıkları kur (uv sync veya pip install -e .[dev])"
	@echo "  test       - pytest"
	@echo "  lint       - ruff check"
	@echo "  format     - ruff format"
	@echo "  typecheck  - mypy"
	@echo "  ci         - lint + typecheck + test (CI ile aynı)"
	@echo "  gen-data   - sentetik OHLCV üret"
	@echo "  clean      - cache/artefakt temizle"

install:
ifdef UV
	uv sync
	-uv run pre-commit install
else
	python -m pip install -e ".[dev]"
	-pre-commit install
endif

test:
ifdef UV
	uv run pytest -q
else
	pytest -q
endif

lint:
ifdef UV
	uv run ruff check .
else
	ruff check .
endif

format:
ifdef UV
	uv run ruff format .
else
	ruff format .
endif

typecheck:
ifdef UV
	uv run mypy app
else
	mypy app
endif

ci: lint typecheck test

gen-data:
ifdef UV
	uv run achilles gen-data
else
	achilles gen-data
endif

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache **/__pycache__ build dist *.egg-info
	find . -name "*.pyc" -delete
