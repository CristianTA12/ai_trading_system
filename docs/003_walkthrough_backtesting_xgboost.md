# Walkthrough 003 — Backtesting, Benchmarks y Primer XGBoost

**Fecha**: 2026-09-25
**Fases cubiertas**: 3 (backtesting), 4 (primer modelo XGBoost)
**Commit**: `cfaaccc` en `develop`
**Equipo**: Windows + WSL2 + RTX 3060

---

## Lo que se ha hecho

### Fase 3 — Motor de backtesting

Implementado en `src/backtesting/`:

| Archivo | Función |
|---------|---------|
| [engine.py](file:///d:/ai_trading_system/src/backtesting/engine.py) | Backtester event-driven spot con capital limitado |
| [benchmarks.py](file:///d:/ai_trading_system/src/backtesting/benchmarks.py) | Buy & Hold, EMA20/50, Random (30 semillas) |
| [metrics.py](file:///d:/ai_trading_system/src/backtesting/metrics.py) | Sharpe, Sortino, Drawdown, Profit Factor, Win Rate |
| [dataset.py](file:///d:/ai_trading_system/src/backtesting/dataset.py) | Lectura de snapshots Parquet con verificación SHA-256 |
| [experiment.py](file:///d:/ai_trading_system/src/backtesting/experiment.py) | Orquestación de experimentos con MLflow |
| [run_backtest.py](file:///d:/ai_trading_system/src/backtesting/run_backtest.py) | CLI de ejecución |

Contrato de simulación:
- Spot BTC/USDT, solo largo, una posición, sin apalancamiento.
- Capital: 10.000 USDT; entrada con 100% del efectivo por defecto.
- Compra a `open × (1 + slippage)`, venta a `open × (1 - slippage)`.
- Comisiones: taker 0,04%, maker 0,02% por ejecución.
- Slippage: 0,01% por lado.
- Sin latencia, spread separado, impacto de mercado ni fills parciales.

### Fase 4 — Primer XGBoost

Implementado en `src/models/xgboost/`:

| Archivo | Función |
|---------|---------|
| [classifier.py](file:///d:/ai_trading_system/src/models/xgboost/classifier.py) | Clasificador UP/NEUTRAL/DOWN con pesos de clase |

Configuración del modelo:
- Target: retorno 15m → DOWN (<-0.25%), NEUTRAL, UP (>+0.25%)
- 500 árboles, profundidad 6, lr 0.05, subsample/colsample 0.8
- Pesos inversos de clase (solo de train)
- Señal: entra largo si UP es la clase más probable y p_up ≥ 0.5
- Train: 2020–2023 (139.245 filas), Validation: 2024 (35.135 predicciones)

### Testing

- **61 tests pasando** (18 nuevos respecto al walkthrough 002).
- Test 2025–2026 reservado, no tocado.

---

## Resultados — Validación 2024

| Estrategia | Retorno neto | Sharpe | Max Drawdown | Operaciones | Comisiones |
|:-----------|------------:|---------:|-------------:|------------:|-----------:|
| **Buy & Hold** | **+121,08%** | **1,755** | 32,44% | 1 | 12,85 |
| EMA 20/50 | +13,40% | 0,506 | 31,04% | 339 | 2.871 |
| Random (s42) | −99,95% | −22,369 | 99,96% | 8.774 | 9.613 |
| **XGBoost** | **−26,26%** | **−1,683** | **28,74%** | **556** | **3.741** |

XGBoost detalle: Profit Factor 0,763 · Win Rate 52,34% · Exposición 2,27% · Slippage 936 USDT

Clasificación: Accuracy 66,59% · Balanced Accuracy 46,94% · Macro F1 45,21%
(Predecir siempre la clase mayoritaria de train → 76,74% accuracy en validation)

MLflow: run `44411da11bd44042800f409f39de1990`, experimento `spot-baseline-v1`.

---

## Análisis de los resultados

### Lo que los números dicen

1. **Buy & Hold es un benchmark brutal en 2024.** BTC subió +121% — cualquier modelo que no esté largo la mayor parte del tiempo pierde contra esto. Es exactamente por eso que el plan exige comparar siempre contra B&H.

2. **El XGBoost solo está expuesto el 2,27% del tiempo.** Hace 556 operaciones pero mantiene posición muy poco. Esto significa que el modelo es extremadamente conservador — predice UP pocas veces. Cuando lo hace, acierta el 52,34% pero no lo suficiente para compensar los costes (3.741 USDT en comisiones + 936 USDT en slippage = 4.677 USDT comidos por fricciones).

3. **El drawdown del XGBoost (28,74%) es menor que B&H (32,44%).** Esto es interesante: el modelo controla el riesgo, pero lo hace a costa de perderse el rally completo. No es que el modelo sea aleatorio — está tomando decisiones, pero malas en un mercado alcista.

4. **Balanced accuracy 46,94% < 50% = peor que lanzar una moneda** para las clases balanceadas. La accuracy del 66,59% es engañosa porque NEUTRAL es la clase mayoritaria (76,74%). El modelo básicamente no distingue UP de DOWN.

5. **Random con -99,95% confirma que los costes son correctos.** 8.774 operaciones × costes = destrucción total. Este es un sanity check válido.

### Lo que NO dicen (y es importante)

- **Este es un resultado completamente normal para un primer modelo.** La mayoría de modelos de ML aplicados a finanzas no funcionan a la primera. El valor de este experimento es validar que el pipeline completo funciona (datos → features → modelo → backtest → métricas → MLflow) y que los costes son realistas.

- **2024 fue un año particularmente alcista** (BTC: +121%). Un modelo que intenta ir largo selectivamente en un mercado que sube sin parar está en desventaja estructural contra B&H. No significa que el enfoque esté roto — significa que el modelo necesita mejorar en la dirección correcta.

---

## Siguiente paso recomendado

Sí, **sigue por ahí** — walk-forward dentro de train es exactamente lo correcto. Pero hay varias líneas de mejora a explorar, y el orden importa:

### Prioridad 1: Diagnóstico antes de iterar

Antes de cambiar hiperparámetros o añadir features, diagnostica *qué falla*:

1. **¿El modelo tiene algún poder predictivo real?** Compara la distribución de `p_up` cuando el mercado realmente sube vs cuando baja. Si son indistinguibles, no hay señal — cambiar hiperparámetros no ayudará.

2. **¿El umbral 0.5 es correcto?** Con pesos inversos de clase las probabilidades no están calibradas. Experimenta con umbrales más bajos (0.4, 0.35) — quizá el modelo tiene señal pero el umbral la filtra.

3. **¿La baja exposición (2,27%) es el problema principal?** Si el modelo estuviera expuesto el 50% del tiempo con la misma dirección, ¿ganaría? Un backtest "si XGBoost dice UP → largo, si no → largo también" (siempre largo) te dice si el modelo sabe cuándo NO estar.

### Prioridad 2: Walk-forward interno (lo que planeas)

Dividir train (2020–2023) en sub-ventanas deslizantes:

```
Ventana 1:  Train 2020-2021  →  Val 2022-H1
Ventana 2:  Train 2020-2022  →  Val 2022-H2
Ventana 3:  Train 2020-2022  →  Val 2023-H1
Ventana 4:  Train 2020-2023H1 → Val 2023-H2
```

Esto te dice si el modelo es estable o si el rendimiento varía mucho por ventana. Si es consistentemente malo, el problema es la señal/features, no el overfitting.

### Prioridad 3: Features y target (si walk-forward confirma que no hay señal)

- **Target alternativo**: en vez de clasificación UP/NEUTRAL/DOWN, probar regresión directa de retorno. O un target binario sin zona neutral (UP vs NOT-UP).
- **Features adicionales**: funding rate, open interest, fear & greed — ya tienes las fuentes en el plan pero no están en el dataset v1.
- **Lag features**: incluir features de las últimas N velas como contexto.

### Lo que NO hacer todavía

- ❌ No tocar el test set (2025–2026) — bien hecho manteniéndolo reservado.
- ❌ No iterar repetidamente sobre validation 2024 — como bien dice tu doc, eso lo convierte en dev set.
- ❌ No saltar a Transformer/DL — si XGBoost no encuentra señal con 20 features, más complejidad no ayuda.
- ❌ No añadir complejidad al backtester (shorts, leverage) — primero encontrar una señal long-only.

---

## Estado del repositorio

```
src/
├── backtesting/
│   ├── engine.py              ✅ Nuevo
│   ├── benchmarks.py          ✅ Nuevo
│   ├── metrics.py             ✅ Nuevo
│   ├── dataset.py             ✅ Nuevo
│   ├── experiment.py          ✅ Nuevo
│   └── run_backtest.py        ✅ Nuevo
├── models/xgboost/
│   └── classifier.py          ✅ Nuevo
├── config/                    ✅ Sin cambios
├── data/                      ✅ Sin cambios
├── features/                  ✅ Sin cambios
├── execution/                 ✅ Sin cambios
├── risk/                      ✅ Sin cambios
└── utils/                     ✅ Sin cambios

tests/                         ✅ 61 tests (43 → 61)
data/experiments/              ✅ Resultados + modelo guardado
docs/backtesting.md            ✅ Nuevo
```

---

## Documentación

- [docs/backtesting.md](file:///d:/ai_trading_system/docs/backtesting.md) — contrato, benchmarks, resultados, interpretación.
- MLflow: http://localhost:5000 → experimento `spot-baseline-v1`.
