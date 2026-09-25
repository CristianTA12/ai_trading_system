# Walkthrough 002 — Infraestructura WSL, Datos Históricos y Features

**Fecha**: 2026-09-25
**Fases cubiertas**: 0 (parcial WSL), 1 (ingesta), 2 (features)
**Equipo temporal**: Windows + WSL2 + RTX 3060 (pendiente equipo final con RTX 5080)

---

## Lo que se ha hecho

### Fase 0 — Infraestructura (adaptada a WSL2)

- Desplegado el proyecto completo en **Windows + Ubuntu WSL2 + Docker Desktop**.
- Trasladado el almacenamiento de Docker al HDD `D:` para liberar SSD; Ubuntu y el entorno virtual Python permanecen en el SSD de Linux.
- Levantados los **6 servicios** del docker-compose:
  - TimescaleDB, Redis, MLflow, Grafana, Prometheus, Ollama.
- Corregidos fallos encontrados durante la puesta en marcha:
  - Instalación Python (backend de setuptools).
  - Driver PostgreSQL para MLflow (`psycopg2`).
  - Health check de TimescaleDB (usuario correcto en `pg_isready`).
- Añadido `docker-compose.wsl.yml` como override opcional para WSL, sin romper compatibilidad con Ubuntu nativo.
- Verificada la **RTX 3060** accesible desde Ollama y PyTorch vía CUDA en WSL2.
- Documentación creada en [docs/wsl.md](file:///d:/ai_trading_system/docs/wsl.md).

### Fase 1 — Data Ingestion (completada)

- Implementado [historical_downloader.py](file:///d:/ai_trading_system/src/data/downloaders/historical_downloader.py) + [history.py](file:///d:/ai_trading_system/src/data/downloaders/history.py):
  - Descarga mensual de CSVs desde Binance Data Vision (ZIP + CHECKSUM).
  - Verificación SHA-256 contra checksum publicado.
  - Validación estricta: fechas, precios, gaps, duplicados, orden cronológico.
  - Carga en TimescaleDB en lotes de 2.000, transacción única por mes.
  - Sin duplicados: la carga es repetible e idempotente.
  - Rollback automático ante cualquier fallo (no queda un mes parcialmente cargado).
- Implementado [data_quality_validator.py](file:///d:/ai_trading_system/src/data/validators/data_quality_validator.py).
- Implementado `sync-history` para descarga masiva con manejo de gaps:
  - `--allow-gaps`: acepta meses con minutos ausentes.
  - `--quarantine-duration-errors`: excluye velas con duración inválida, sin descartar el mes.
- **Datos cargados**: 80 meses de BTC/USDT spot (enero 2020 – agosto 2026):
  - **3.504.067 velas de 1 minuto**.
  - 2.333 minutos ausentes registrados (no inventados).
  - 8 registros excluidos por duración inválida en cuarentena.
- Dashboard de Grafana creado con cobertura, huecos y precios (acceso de solo lectura).
- Documentación en [docs/data-ingestion.md](file:///d:/ai_trading_system/docs/data-ingestion.md).

### Fase 2 — Feature Engineering (completada)

- Implementado [dataset.py](file:///d:/ai_trading_system/src/features/dataset.py) con 20 variables v1:

| Grupo | Variables |
|-------|-----------|
| Returns | `return_1`, `return_4`, `return_16`, `log_return_1` |
| Volatilidad | `volatility_20` |
| Medias | `sma_distance_20/50`, `ema_distance_20/50` |
| Indicadores | `rsi_14_cutler`, `atr_14_sma_ratio` |
| Vela | `range_ratio`, `body_ratio` |
| Volumen | `volume_relative_20`, `volume_zscore_20`, `trades_relative_20` |
| Temporal | `hour_sin/cos`, `weekday_sin/cos` |

- Agregación a velas de 15 minutos; solo velas completas (15 minutos fuente).
- Indicadores reiniciados tras cada gap (no se interpola a través de discontinuidades).
- Generadas **232.767 filas** con predictores y objetivos separados.
- Target: `target_return_next_15m` (cierre/apertura − 1 de la vela siguiente).
- Campos auxiliares: `entry_open`, `exit_close`, `label_end` (nunca como predictores).
- Particiones temporales definidas:
  - **Train**: 2020–2023
  - **Validation**: 2024
  - **Test**: 2025–agosto 2026
- Purge gap implementado en bordes de partición.
- Output en `data/processed/` como Parquet:
  - `bars.parquet`, `features.parquet`, `labels.parquet`, `splits.parquet`, `metadata.json`
- Sin normalización global: la normalización se hará solo con datos de train.
- Documentación en [docs/backtesting-dataset.md](file:///d:/ai_trading_system/docs/backtesting-dataset.md).

### Testing y CI

- **43 tests pasando**, cubriendo:
  - Causalidad (features no usan datos futuros).
  - Integridad de datos (no NaN en velas completas).
  - Separación temporal (train/val/test no se solapan).
  - Reinicio de indicadores tras gaps.
  - Targets que no atraviesan discontinuidades ni bordes de partición.
  - Carga idempotente y rollback en integración.
- Código subido a rama `develop`; datos y credenciales excluidos de Git.

---

## Estado actual del repositorio

```
ai-trading-system/
├── src/
│   ├── config/settings.py            ✅ Funcionando
│   ├── data/
│   │   ├── downloaders/
│   │   │   ├── historical_downloader.py  ✅ Descarga + validación + carga
│   │   │   └── history.py               ✅ Sync masivo multimes
│   │   └── validators/
│   │       └── data_quality_validator.py ✅ Validación de calidad
│   ├── features/
│   │   └── dataset.py                   ✅ 20 features v1 + splits
│   ├── backtesting/                     ⏳ Solo __init__.py (siguiente paso)
│   ├── execution/broker.py              ✅ Interfaz abstracta
│   ├── risk/risk_manager.py             ✅ Implementado
│   ├── models/                          ⏳ Stubs
│   ├── llm/                             ⏳ Stubs
│   ├── cli.py                           ✅ Comandos de datos funcionando
│   └── utils/                           ✅ Logging, DB, Redis
├── tests/                               ✅ 43 tests pasando
├── docs/
│   ├── 001_walkthrough_repositorio_base.md
│   ├── wsl.md
│   ├── data-ingestion.md
│   └── backtesting-dataset.md
├── dashboards/grafana/                  ✅ Dashboard de calidad de datos
├── docker-compose.yml                   ✅ 6 servicios
├── docker-compose.wsl.yml              ✅ Override para WSL
└── data/
    ├── raw/binance/spot/BTCUSDT/1m/    ✅ 80 meses ZIP + checksums
    └── processed/                       ✅ Features + labels + splits
```

---

## Notas sobre el equipo temporal (WSL + RTX 3060)

| Aspecto | Estado |
|---------|--------|
| Docker Compose | ✅ Funcionando (volúmenes en HDD D:) |
| TimescaleDB | ✅ 3.5M velas cargadas |
| Ollama + CUDA | ✅ RTX 3060 accesible |
| PyTorch + GPU | ✅ Verificado |
| Rendimiento | ⚠️ Más lento que SSD nativo (HDD para Docker) |
| VRAM | ⚠️ 12GB (3060) vs 16GB (5080 final) — modelos más pequeños |

Cuando llegue el equipo final (RTX 5080 + dual boot Ubuntu):
- Migrar los datos raw (`data/raw/`) copiando los ZIPs.
- Re-ejecutar `make sync-history` + `make build-features` en nativo.
- Los volúmenes Docker se recrean al hacer `make up` por primera vez.

---

## Pendiente confirmado

> Primer backtest con comisiones y slippage; todavía no hay resultados
> de rentabilidad ni bot operativo.
