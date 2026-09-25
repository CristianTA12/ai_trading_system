.PHONY: help setup up down restart logs test lint format check clean download-data validate-data load-data setup-dashboard

help: ## Mostrar ayuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# === Setup ===

setup: ## Instalar dependencias de desarrollo
	pip install -e ".[dev]"
	pre-commit install

# === Docker ===

up: ## Levantar todos los servicios
	docker compose up -d

down: ## Parar todos los servicios
	docker compose down

restart: ## Reiniciar todos los servicios
	docker compose restart

logs: ## Ver logs de todos los servicios
	docker compose logs -f --tail=100

logs-db: ## Ver logs de TimescaleDB
	docker compose logs -f timescaledb

logs-ollama: ## Ver logs de Ollama
	docker compose logs -f ollama

# === Ollama / LLM ===

ollama-pull: ## Descargar modelo LLM recomendado
	docker exec trading-ollama ollama pull qwen2.5:14b

ollama-pull-light: ## Descargar modelo LLM ligero
	docker exec trading-ollama ollama pull llama3.1:8b

ollama-list: ## Listar modelos LLM disponibles
	docker exec trading-ollama ollama list

# === Testing ===

test: ## Ejecutar todos los tests
	pytest tests/ -v --tb=short

test-unit: ## Ejecutar solo tests unitarios
	pytest tests/unit/ -v --tb=short

test-integration: ## Ejecutar solo tests de integración
	pytest tests/integration/ -v --tb=short

test-cov: ## Ejecutar tests con cobertura
	pytest tests/ -v --cov=src --cov-report=html --cov-report=term

# === Code Quality ===

lint: ## Ejecutar linter
	ruff check src/ tests/

format: ## Formatear código
	black src/ tests/
	ruff check --fix src/ tests/

type-check: ## Type checking
	mypy src/

check: lint type-check test ## Ejecutar todas las verificaciones

# === Data ===

DATA_ARGS ?=

download-data: ## Descargar datos históricos
	python -m src.cli download-historical $(DATA_ARGS)

validate-data: ## Validar calidad de datos
	python -m src.cli validate-data $(DATA_ARGS)

load-data: ## Validar y cargar un archivo local en TimescaleDB
	python -m src.cli load-data $(DATA_ARGS)

setup-dashboard: ## Configurar acceso de lectura y dashboard de datos
	python -m src.monitoring.setup_dashboard

# === Trading ===

paper-trade: ## Iniciar paper trading
	python -m src.cli paper-trade

live-trade: ## Iniciar trading real (¡CUIDADO!)
	@echo "⚠️  ¿Estás seguro? Esto usa dinero REAL."
	@read -p "Escribe 'SI' para continuar: " confirm && [ "$$confirm" = "SI" ] || exit 1
	python -m src.cli live-trade

# === Training ===

train-xgboost: ## Entrenar modelo XGBoost
	python -m src.training.train_xgboost

train-transformer: ## Entrenar modelo Transformer
	python -m src.training.train_transformer

walk-forward: ## Ejecutar walk-forward validation
	python -m src.training.walk_forward

backtest: ## Ejecutar backtest
	python -m src.backtesting.run_backtest

# === Cleanup ===

clean: ## Limpiar archivos temporales
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov
