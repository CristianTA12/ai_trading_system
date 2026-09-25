# ai-trading-system

Sistema de trading cuantitativo multimodelo con IA.

## Objetivo

Plataforma para recoger datos de mercado, generar features, entrenar modelos de IA,
validar estrategias con backtesting/walk-forward, y ejecutar paper trading y trading real
con gestión de riesgo independiente.

## Principios

1. No construir modelos complejos antes de validar datos y backtesting.
2. Cada modelo nuevo debe superar un baseline simple.
3. Nunca usar datos futuros en training o features.
4. Simular fees, spread, slippage y latencia.
5. Risk Manager separado e inviolable.
6. Walk-forward validation obligatorio.
7. Coste cero: datos gratuitos, LLM local, sin cloud.

## Stack

- **Lenguaje**: Python 3.11+
- **Base de datos**: TimescaleDB (PostgreSQL)
- **Cache**: Redis
- **ML Tracking**: MLflow
- **Monitoring**: Grafana
- **LLM Local**: Ollama (Qwen 2.5 14B / Llama 3.1 8B)
- **Contenedores**: Docker + Docker Compose
- **GPU**: NVIDIA RTX 5080 16GB (CUDA 12.x)

## Estructura

```
ai-trading-system/
├── src/                    # Código fuente principal
│   ├── config/             # Configuración y settings
│   ├── data/               # Ingesta y gestión de datos
│   │   ├── collectors/     # WebSocket collectors (real-time)
│   │   ├── downloaders/    # Descarga de datos históricos
│   │   └── validators/     # Validación de calidad de datos
│   ├── features/           # Feature engineering
│   ├── models/             # Modelos de ML/DL
│   │   ├── xgboost/        # XGBoost / LightGBM
│   │   ├── transformer/    # Transformer temporal
│   │   ├── orderbook/      # Modelo de order book
│   │   ├── regime/         # Detector de régimen
│   │   ├── ensemble/       # Meta-modelo / ensemble
│   │   └── rl/             # Reinforcement learning (opcional)
│   ├── llm/                # Pipeline de LLM local (Ollama)
│   ├── backtesting/        # Motor de backtesting
│   ├── execution/          # Execution engine (brokers)
│   ├── risk/               # Risk manager
│   ├── monitoring/         # Alertas y health checks
│   ├── training/           # Training loop y retraining
│   └── utils/              # Utilidades comunes
├── tests/                  # Tests
│   ├── unit/               # Tests unitarios
│   └── integration/        # Tests de integración
├── config/                 # Archivos de configuración YAML
├── docker/                 # Dockerfiles
├── scripts/                # Scripts de utilidad
├── notebooks/              # Jupyter notebooks exploratorios
├── dashboards/grafana/     # Dashboards de Grafana (JSON)
├── docs/                   # Documentación
├── docker-compose.yml      # Servicios
├── pyproject.toml          # Dependencias Python
├── Makefile                # Comandos comunes
└── .env.example            # Variables de entorno de ejemplo
```

## Quickstart

```bash
# 1. Clonar
git clone <repo-url>
cd ai-trading-system

# 2. Configurar
cp .env.example .env
# Editar .env con tus claves de exchange

# 3. Levantar servicios
docker compose up -d

# 4. Instalar dependencias Python
pip install -e ".[dev]"

# 5. Verificar
make check
```

## Fases

Ver [implementation_plan_ai_trading.md](implementation_plan_ai_trading.md) para el plan completo.
