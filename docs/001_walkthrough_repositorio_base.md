# Walkthrough 001 — Repositorio Base Creado

**Fecha**: 2026-09-21
**Fase**: 0 — Base del proyecto

---

## Lo que se ha hecho

### 1. Implementation Plan actualizado

- [implementation_plan_ai_trading.md](file:///d:/ai_trading_system/implementation_plan_ai_trading.md) — Plan completo con 17 fases + retraining loop
- Incorpora: dual boot, coste cero, LLM local, datos gratuitos, latencia definida
- Principios del proyecto definidos (13 principios)

### 2. Estructura del repositorio

```
ai-trading-system/
├── src/                         # Código fuente
│   ├── config/settings.py       # Configuración centralizada (Pydantic)
│   ├── data/                    # Ingesta de datos
│   │   ├── collectors/          # WebSocket real-time
│   │   ├── downloaders/         # Datos históricos
│   │   └── validators/          # Calidad de datos
│   ├── features/                # Feature engineering
│   ├── models/                  # Todos los modelos
│   │   ├── xgboost/
│   │   ├── transformer/
│   │   ├── orderbook/
│   │   ├── regime/
│   │   ├── ensemble/
│   │   └── rl/
│   ├── llm/                     # Pipeline LLM local (Ollama)
│   ├── backtesting/             # Motor de backtest
│   ├── execution/broker.py      # Interfaz abstracta de broker
│   ├── risk/risk_manager.py     # Risk Manager completo
│   ├── monitoring/              # Alertas y health checks
│   ├── training/                # Training y retraining loop
│   ├── utils/                   # Logging, database, helpers
│   └── cli.py                   # CLI principal (Click)
├── tests/                       # Tests (pytest)
│   └── unit/risk/test_risk_manager.py
├── config/settings.yml          # Configuración YAML principal
├── docker/
│   ├── init-db.sql              # Esquema DB (10 hypertables)
│   └── prometheus.yml           # Config Prometheus
├── docker-compose.yml           # 6 servicios
├── pyproject.toml               # Dependencias Python
├── Makefile                     # 20+ comandos útiles
├── .env.example                 # Variables de entorno
├── .gitignore
├── .pre-commit-config.yaml
└── README.md
```

### 3. Archivos con implementación real (no solo stubs)

| Archivo | Qué hace |
|---------|----------|
| [settings.py](file:///d:/ai_trading_system/src/config/settings.py) | Carga YAML + env vars con Pydantic, singleton global |
| [logging.py](file:///d:/ai_trading_system/src/utils/logging.py) | Logging estructurado (JSON en prod, bonito en dev) |
| [database.py](file:///d:/ai_trading_system/src/utils/database.py) | Conexiones a TimescaleDB y Redis con singletons |
| [broker.py](file:///d:/ai_trading_system/src/execution/broker.py) | ABC con Order, Position, Balance dataclasses |
| [risk_manager.py](file:///d:/ai_trading_system/src/risk/risk_manager.py) | Risk Manager completo con 7 checks + kill switch |
| [cli.py](file:///d:/ai_trading_system/src/cli.py) | CLI con comandos: status, download, paper, live, backtest |
| [init-db.sql](file:///d:/ai_trading_system/docker/init-db.sql) | 10 hypertables TimescaleDB |
| [settings.yml](file:///d:/ai_trading_system/config/settings.yml) | Toda la configuración: features, modelos, risk, retraining |
| [docker-compose.yml](file:///d:/ai_trading_system/docker-compose.yml) | TimescaleDB + Redis + MLflow + Grafana + Ollama (GPU) + Prometheus |
| [test_risk_manager.py](file:///d:/ai_trading_system/tests/unit/risk/test_risk_manager.py) | 8 tests unitarios del risk manager |

### 4. Docker Compose — 6 servicios

| Servicio | Puerto | Función |
|----------|--------|---------|
| TimescaleDB | 5432 | Base de datos principal |
| Redis | 6379 | Cache y estado real-time |
| MLflow | 5000 | Tracking de experimentos |
| Grafana | 3000 | Dashboards y monitorización |
| Ollama | 11434 | LLM local con GPU |
| Prometheus | 9090 | Métricas del sistema |

---

## Decisiones tomadas

| Decisión | Resultado |
|----------|-----------|
| Sistema operativo | Dual boot: Windows (SSD 4TB) + Ubuntu 24.04 (SSD 2TB) |
| Coste recurrente | Solo electricidad (~30-40€/mes) |
| Datos de mercado | Binance API + Data Vision (gratis) |
| LLM | Ollama local (Qwen 2.5 14B / Llama 3.1 8B) en RTX 5080 |
| Latencia | Sistema de dos velocidades: lenta (5m-1h) + rápida (10s-1m) |
| Retraining | Semanal + shadow mode 48h + promoción automática |
| RL (Fase 13) | Marcado como opcional/experimental |

---

## Siguiente paso

Instalar Ubuntu 24.04 en el SSD de 2TB, configurar CUDA + Docker, y ejecutar:

```bash
cd ai-trading-system
cp .env.example .env
make up
make ollama-pull
make setup
make test
```

Después empezar **Fase 1**: `historical_downloader.py` para descargar datos de Binance.
