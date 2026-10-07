# Contexto del Proyecto — AI Trading System

**Última actualización**: 2026-09-29 (post-auditoría derivados)
**Repositorio**: `d:\ai_trading_system` · rama `develop`
**Tests**: 135 pasando, 2 de integración omitidos (requieren DB)

---

## 1. Objetivo general

Construir una infraestructura de trading cuantitativo con IA capaz de operar
BTC/USDT spot de forma rentable después de costes, con riesgo controlado,
utilizando exclusivamente recursos locales y datos gratuitos.

El proyecto NO busca:
- Operar con dinero real todavía.
- Utilizar APIs de pago ni servicios cloud.
- Construir muchos modelos a la vez sin validar los datos y la ejecución primero.

El proyecto SÍ busca:
- Demostrar una ventaja estadística reproducible antes de cualquier decisión de capital.
- Mantener disciplina experimental: preregistro, walk-forward, test reservado.
- Construir infraestructura reutilizable para futuras estrategias y activos.

Referencia completa del plan original:
[implementation_plan_ai_trading.md](file:///d:/ai_trading_system/implementation_plan_ai_trading.md)

---

## 2. Restricciones del proyecto

| Restricción | Decisión |
|-------------|----------|
| **Hardware actual** | WSL2 + Docker Desktop sobre Windows, RTX 3060 (equipo provisional) |
| **Hardware definitivo** | Ryzen 9 9950X3D · RTX 5080 16GB · 64GB DDR5 · 6TB NVMe · Dual boot |
| **Datos** | Solo fuentes gratuitas / open source (Binance Data Vision, APIs públicas) |
| **LLM** | Sin APIs de pago — modelos locales vía Ollama |
| **Cloud** | Nada — todo corre en la máquina local |
| **Coste recurrente** | Solo electricidad |

---

## 3. Qué se ha construido (infraestructura)

### Stack de servicios (Docker Compose)

```
TimescaleDB    ── Base de datos temporal (OHLCV, features)
Redis          ── Estado en tiempo real (futuro)
MLflow         ── Tracking de experimentos (activo, 6 experimentos)
Grafana        ── Monitorización (futuro)
Prometheus     ── Métricas (futuro)
Ollama         ── LLM local con CUDA (verificado con RTX 3060)
```

Docker almacena volúmenes en el HDD D:; Python y Ubuntu en el SSD.
Configuración WSL documentada en [wsl.md](file:///d:/ai_trading_system/docs/wsl.md).

### Código fuente (`src/`)

```
src/
├── backtesting/
│   ├── engine.py          Motor de ejecución secuencial spot, capital limitado
│   ├── benchmarks.py      Buy & Hold, EMA, Random, Efectivo
│   ├── metrics.py         Sharpe, Sortino, drawdown, profit factor (diario UTC, √365)
│   ├── evaluator.py       Evaluador automático del criterio risk-return-v1
│   ├── policies.py        Políticas de salida (holding, exit-by-DOWN, hysteresis)
│   ├── dataset.py         Carga y preparación de datasets para backtest
│   ├── diagnostics.py     Diagnósticos de umbral, walk-forward, costes
│   └── experiment.py      Runner de experimentos con MLflow
├── data/
│   └── historical_downloader.py  Descarga repetible de Binance Data Vision
├── features/
│   └── dataset.py         Generación de features v1 (20 variables) y labels
├── models/xgboost/
│   └── classifier.py      Wrapper XGBoost (clasificación y regresión)
├── risk/                  Gestión de riesgo (estructura base)
├── execution/             Broker abstraction (estructura base)
├── monitoring/            Alertas y métricas (estructura base)
├── training/              Pipeline de entrenamiento (estructura base)
└── cli.py                 Interfaz de línea de comandos
```

### Datos cargados

| Dataset | Rango | Volumen |
|---------|-------|---------|
| BTC/USDT spot 1m | Ene 2020 – Ago 2026 | 3.504.067 velas |
| Features v1 (15m) | Ene 2020 – Ago 2026 | ~139.000 filas, 20 features |
| Funding rate (auditoría) | Ene 2020 – Dic 2023 | 4.383 observaciones |
| Open Interest (auditoría) | Sep 2020 – Dic 2023 | 349.837 observaciones |

Documentación de ingesta: [data-ingestion.md](file:///d:/ai_trading_system/docs/data-ingestion.md)

---

## 4. Qué se ha experimentado (10 iteraciones)

### Diseño experimental

- **Folds internos**: 2022 H1, 2022 H2, 2023 H1, 2023 H2
- **Train**: expansivo desde 2020 hasta el inicio de cada semestre
- **Purga**: labels cuyo horizonte alcanza la frontera del fold
- **Validación exploratoria**: 2024 (consultada, no considerada confirmación)
- **Test reservado**: 2025–2026 (NUNCA evaluado)
- **Costes**: taker 0,04% + slippage 0,01% por ejecución (base)

### Tabla completa de iteraciones

| # | Variante | Cambio principal | Mejor WF+ | Criterio | Commit |
|:-:|:---------|:-----------------|:---------:|:--------:|:------:|
| 1 | v1 clasificador | Baseline | 1/4 | ✗ | — |
| 2 | Umbral 0.40 | Bajar confianza | 0/4 | ✗ | — |
| 3 | Umbral 0.35 | Bajar más | 0/4 | ✗ | — |
| 4 | v1 + holding 1h | Política de salida | **2/4** | ✗ | — |
| 5 | v1 + solo DOWN | Política de salida | 0/4 | ✗ | — |
| 6 | v1 + hold 1h + DOWN | Ambas políticas | 1/4 | ✗ | — |
| 7 | Binario 1h + hold | Target + horizonte | 0/4 | ✗ | — |
| 8 | v2 (25 features) + hold 1h | Régimen + lags | 2/4 | ✗ | 8f7f080 |
| 9 | v1 + lags + hold 1h | Solo lags | 2/4 | ✗ | 8e7eae3 |
| 10 | Regresión 15m + 15pb | Modelo + target | 1/4 (×5) | ✗ (0/5) | 8752f87 |

Ninguna variante ha superado el criterio de promoción.

### Criterio de evaluación vigente: risk-return-v1

Acordado tras la iteración 9. Definido en:
- [risk-return-v1.md](file:///d:/ai_trading_system/docs/risk-return-v1.md) — protocolo y definiciones
- [risk-return-v1.yaml](file:///d:/ai_trading_system/docs/risk-return-v1.yaml) — criterio máquina

| Dimensión | Regla |
|-----------|-------|
| Rentabilidad | Retorno neto compuesto de los 4 folds > 0 |
| Riesgo absoluto | Drawdown ≤ 15% en cada fold y en curva concatenada |
| Consistencia | En ≥3/4 folds: Sharpe > B&H **y** DD ≤ B&H |
| Efectivo | Excepción de consistencia si cash íntegro y B&H pierde |
| Fricciones | Retorno compuesto > 0 con slippage duplicado (2 pb) |
| Estabilidad | ≥4/5 semillas fijadas (42, 123, 456, 789, 2026) |

Evaluador automático implementado en
[evaluator.py](file:///d:/ai_trading_system/src/backtesting/evaluator.py)
con 43 tests dedicados.

---

## 5. Hallazgos clave acumulados

### Lo que funciona (parcialmente)

1. **Holding 1h**: la mejor mejora individual en 10 iteraciones. Convierte −26% en +17% en 2024. Reduce rotación de forma significativa.
2. **El clasificador v1 tiene algo de señal**: balanced accuracy 47% > random 33%, retornos brutos positivos en varios escenarios.
3. **La infraestructura experimental es sólida**: preregistro, walk-forward, multi-semilla, evaluador automático, MLflow, 135 tests.

### Lo que no funciona

1. **Ninguna combinación de modelo/target/política sobre las 20 features v1 alcanza rentabilidad neta consistente.** 10 variantes probadas; el espacio sobre v1 está sustancialmente explorado.
2. **Los costes destruyen el edge**: ganancia media ~4-10 pb por operación, costes ~10 pb. El modelo genera retorno bruto positivo pero no sobrevive a la ejecución.
3. **Dependencia de régimen**: el modelo funciona en mercados alcistas (2023, 2024) y pierde en bajistas (2022). Sin información de régimen macro, un long-only está estructuralmente expuesto.
4. **Fragilidad**: cambios de 68 filas en el train alteran semestres enteros. El multi-semilla confirma inestabilidad.
5. **La regresión no mejoró**: RMSE peor que predecir cero en 19/20 evaluaciones. Perdió la señal parcial que la clasificación tenía, bajo esta receta concreta.

### Lo que no se sabe todavía

- Si datos de derivados (funding rate, OI) aportan información económica que las features técnicas no capturan.
- Si un horizonte o modelo diferente (Transformer, ensemble) con información nueva podría funcionar.
- Si el problema es fundamentalmente que BTC spot 15m con XGBoost no tiene edge explotable después de costes.

---

## 6. Dónde estamos ahora — Situación actual

### Decisión tomada: parar iteraciones sobre v1 e investigar datos nuevos

Tras 10 iteraciones sin superar el criterio, se decidió NO probar otro umbral,
modelo o política sobre las mismas 20 features v1. El siguiente paso es
investigar si datos de derivados aportan información económica distinta.

### Auditoría de derivados completada (commit `99a4b75`)

Documentada en [derivatives-feasibility-audit.md](file:///d:/ai_trading_system/docs/derivatives-feasibility-audit.md).
Script reproducible: `scripts/audit_derivatives.py`. 3 tests de alineación pasando.

| Dato | Veredicto | Detalle verificado |
|------|-----------|--------------------|
| **Funding rate** | Viable con limitaciones | 4.383 eventos, sin huecos, cobertura 100% de filas v1 en los 4 folds. Resolución 8h (3 puntos/día). Disponibilidad temporal no demostrada: desfase de 15 min como supuesto conservador explícito, no un SLA de Binance. |
| **Open Interest** | No viable bajo criterio actual | Empieza Sep 2020 (falta Ene–Ago). Cobertura train: 66,53%–80,91% (< 95%). 75.255 duplicados exactos eliminados, 155 observaciones inválidas excluidas. 659 intervalos ausentes. |

Verificación: 1.265 ZIP descargados y comprobados con SHA-256 contra checksums
oficiales. Manifesto de trazabilidad con hashes en `data/audits/derivatives-20260929/`.
No se descargaron datos de 2024 ni del test 2025–2026. No se entrenaron modelos.

### Lo que falta para la iteración 11

1. **Resolver la incertidumbre temporal del funding**: decidir si el desfase
   conservador de 15 min es aceptable para el experimento, documentando
   explícitamente que no está demostrado inequívocamente. No es un problema
   técnico sino una decisión de diseño.
2. **Diseñar las features derivadas de funding** (nivel, delta entre eventos,
   media de N eventos). Definir warmup y regla de caducidad.
3. **Preregistrar el protocolo** con hipótesis, features, modelo, política,
   control emparejado y criterio risk-return-v1.
4. **Implementar, entrenar y evaluar** con el evaluador automático.

---

## 7. Roadmap — Del estado actual al objetivo general

### Fase actual: encontrar una señal rentable (bloqueante)

```
Iteraciones 1-10 sobre features v1
         │
         ▼
    TODAS RECHAZADAS
         │
         ▼
    Auditoría de derivados ✅
         │
         ▼
  ┌──────┴──────┐
  │             │
  Funding    OI (descartado
  viable     por cobertura)
  │
  ▼
  Iteración 11: features v1 + funding
  (por diseñar y preregistrar)
  │
  ▼
  ¿Supera risk-return-v1?
  │           │
  SÍ          NO
  │           │
  ▼           ▼
  Congelar    Replantear:
  receta      - Otros datos (sentimiento, macro)
  │           - Otro modelo (Transformer, ensemble)
  ▼           - Otro activo o timeframe
  Evaluar     - Aceptar que no hay edge explotable
  en test
  2025-2026
  │
  ▼
  ¿Confirma fuera de muestra?
  │           │
  SÍ          NO
  │           │
  ▼           ▼
  Paper       No operar.
  trading     Volver a investigar.
  │
  ▼
  ¿Consistente en paper?
  │
  ▼
  Trading real con capital mínimo
  + gestión de riesgo independiente
  + monitorización 24/7
```

### Fases del plan original pendientes

El [plan original](file:///d:/ai_trading_system/implementation_plan_ai_trading.md)
define 15+ fases. El estado actual respecto a las más relevantes:

| Fase | Descripción | Estado |
|:----:|-------------|--------|
| 0 | Base del proyecto | ✅ Completada (WSL, Docker, repo, tests) |
| 1 | Data ingestion (históricos) | ✅ Spot completado · Derivados auditados |
| 1 | Data ingestion (real-time) | ⏳ Pendiente (WebSocket, order book) |
| 2 | Feature engineering v1 | ✅ 20 features técnicas |
| 3 | Backtesting + validación | ✅ Motor, benchmarks, métricas, evaluador |
| 4 | Primer modelo (XGBoost) | ✅ 10 iteraciones, ninguna promovida |
| 5 | Walk-forward avanzado | ✅ Implementado y usado en cada iteración |
| 6 | Paper trading | ⏳ Bloqueado por falta de señal rentable |
| 7 | Trading real | ⏳ Bloqueado |
| 8 | Gestión de riesgo | 🔧 Estructura base, no conectada a señal |
| 9 | Monitorización | 🔧 Grafana/Prometheus desplegados, no configurados |
| 10 | Detector de régimen | ⏳ Pendiente (parcialmente explorado en features v2) |
| 11-15 | Multi-modelo, LLM, optimización | ⏳ Futuro |

**La Fase 4 (encontrar señal rentable) es el bloqueante principal.** Todo lo
demás depende de tener una estrategia que demuestre ventaja estadística.

---

## 8. Documentación de referencia

### Walkthroughs (histórico cronológico de trabajo)

| # | Documento | Contenido |
|:-:|-----------|-----------|
| 1 | [001_walkthrough_repositorio_base.md](file:///d:/ai_trading_system/docs/001_walkthrough_repositorio_base.md) | Estructura del proyecto, Docker, servicios |
| 2 | [002_walkthrough_infra_datos_features.md](file:///d:/ai_trading_system/docs/002_walkthrough_infra_datos_features.md) | WSL, ingesta de datos, features v1 |
| 3 | [003_walkthrough_backtesting_xgboost.md](file:///d:/ai_trading_system/docs/003_walkthrough_backtesting_xgboost.md) | Motor de backtest, benchmarks, XGBoost v1 |
| 4 | [004_walkthrough_diagnostico_xgboost.md](file:///d:/ai_trading_system/docs/004_walkthrough_diagnostico_xgboost.md) | Barrido de umbrales, walk-forward, costes |
| 5 | [005_walkthrough_salidas_horizonte.md](file:///d:/ai_trading_system/docs/005_walkthrough_salidas_horizonte.md) | Políticas de salida, target binario 1h |
| 6 | [006_walkthrough_features_v2.md](file:///d:/ai_trading_system/docs/006_walkthrough_features_v2.md) | Régimen + lags: rechazado |
| 7 | [007_walkthrough_ablacion_lags.md](file:///d:/ai_trading_system/docs/007_walkthrough_ablacion_lags.md) | Solo lags: rechazado |
| 8 | [008_walkthrough_regresion_rechazada.md](file:///d:/ai_trading_system/docs/008_walkthrough_regresion_rechazada.md) | Regresión XGBoost: rechazada |

### Informes técnicos

| Documento | Contenido |
|-----------|-----------|
| [backtesting.md](file:///d:/ai_trading_system/docs/backtesting.md) | Reglas del motor de simulación |
| [backtesting-dataset.md](file:///d:/ai_trading_system/docs/backtesting-dataset.md) | Formato y contrato del dataset |
| [xgboost-diagnostics.md](file:///d:/ai_trading_system/docs/xgboost-diagnostics.md) | Diagnóstico detallado del clasificador |
| [exit-horizon-experiments.md](file:///d:/ai_trading_system/docs/exit-horizon-experiments.md) | Políticas de salida y target 1h |
| [features-v2-protocol.md](file:///d:/ai_trading_system/docs/features-v2-protocol.md) | Preregistro features v2 |
| [features-v2-results.md](file:///d:/ai_trading_system/docs/features-v2-results.md) | Resultados features v2 |
| [lags-ablation-protocol.md](file:///d:/ai_trading_system/docs/lags-ablation-protocol.md) | Preregistro ablación lags |
| [lags-ablation-results.md](file:///d:/ai_trading_system/docs/lags-ablation-results.md) | Resultados ablación lags |
| [iteration-10-protocol.md](file:///d:/ai_trading_system/docs/iteration-10-protocol.md) | Preregistro regresión |
| [risk-return-v1.md](file:///d:/ai_trading_system/docs/risk-return-v1.md) | Criterio de evaluación vigente |
| [derivatives-feasibility-audit.md](file:///d:/ai_trading_system/docs/derivatives-feasibility-audit.md) | Auditoría funding + OI |
| [wsl.md](file:///d:/ai_trading_system/docs/wsl.md) | Configuración WSL2 |
| [data-ingestion.md](file:///d:/ai_trading_system/docs/data-ingestion.md) | Descarga e ingesta de datos |

---

## 9. Principios operativos del proyecto

Estos principios se han ido estableciendo a lo largo de las 10 iteraciones:

1. **Preregistro obligatorio**: la hipótesis, features, modelo, política y criterio
   se fijan en un commit antes de entrenar. No se ajusta post-hoc.

2. **Walk-forward como juez**: un resultado en un solo período no cuenta. Se exige
   consistencia en múltiples semestres y múltiples semillas.

3. **Test reservado**: 2025–2026 nunca se ha evaluado. Solo se abre con receta
   congelada y protocolo final. No se usa para iterar.

4. **Control emparejado**: cada candidato se compara contra v1 en las mismas filas,
   mismas semillas, mismas velas. La diferencia mide el efecto del cambio.

5. **Costes reales**: taker 0,04% + slippage 0,01% por ejecución. Stress test con
   slippage duplicado. Sin maker como supuesto favorable.

6. **Rechazo documentado**: cada variante rechazada se registra con todos sus
   resultados. No se borran fracasos. Los rechazos informan las decisiones futuras.

7. **Zero cost**: no se paga por datos, APIs, cloud ni servicios. Solo electricidad.
