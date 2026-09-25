# Walkthrough 005 — Políticas de Salida y Target Binario 1h

**Fecha**: 2026-09-25
**Commit**: `5988f3c` en `develop`
**Fase**: 4 (continuación) — búsqueda de edge neto
**Tests**: 72 pasando

---

## Lo que se ha probado

### Experimento 1 — Políticas de salida (sin reentrenar)

Se reutilizaron los modelos ya entrenados. Cuatro políticas de salida sobre la misma señal UP (p_up ≥ 0.50):

| Política | Descripción |
|----------|-------------|
| Baseline | Sale si deja de cumplir condición de entrada |
| Holding 1h | Mantiene mínimo 60 min antes de poder salir |
| Solo DOWN | Solo sale si el modelo predice DOWN (NEUTRAL mantiene) |
| Holding 1h + DOWN | Combina ambas |

### Experimento 2 — Target binario 1h (reentrenando)

Nuevo target: `UP = return_1h > 0.5%` vs `NOT-UP`. Horizonte 4 velas, exige continuidad. Entrenado dentro de cada fold con los mismos parámetros. Evaluado con salida inmediata y con holding 1h.

---

## Resultados — Políticas de salida (modelo original 15m)

| Período | Original | Holding 1h | Solo DOWN | Holding 1h + DOWN |
|:--------|--------:|-----------:|----------:|------------------:|
| 2022 H1 | −38,62% | −33,09% | −33,07% | −34,93% |
| 2022 H2 | −31,11% | −36,36% | −14,25% | −28,02% |
| 2023 H1 | −4,47% | **+9,68%** | −14,17% | −5,26% |
| 2023 H2 | **+7,24%** | **+12,04%** | −0,32% | **+10,47%** |
| 2024 (expl.) | −26,26% | **+17,36%** | **+15,32%** | **+65,41%** |

**Holding 1h** es la mejor mejora individual: pasa de −26% a +17% en 2024 y gana en ambos semestres de 2023. Reduce operaciones (556→448), sube mediana de duración (15→60 min), y lleva el edge neto medio de −5,27 a +4,10 pb.

**Holding 1h + DOWN** da +65% en 2024 (drawdown 15,88%), pero pierde en 3 de 4 semestres internos.

### Resultados — Binario 1h (reentrenado)

| Semestre | Bal. Acc. | ROC AUC | Salida inmediata | Holding 1h | Ops (hold) | Edge neto/op |
|:---------|----------:|--------:|-----------------:|-----------:|-----------:|-------------:|
| 2022 H1 | 60,73% | 0,664 | −67,79% | −54,93% | 1.041 | −6,85 pb |
| 2022 H2 | 61,62% | 0,699 | −58,55% | −42,69% | 808 | −6,37 pb |
| 2023 H1 | 59,88% | 0,711 | −21,02% | −1,32% | 551 | +0,11 pb |
| 2023 H2 | 57,91% | 0,753 | −34,99% | −20,28% | 372 | −5,78 pb |

ROC AUC creciente (0,664 → 0,753) indica que el modelo mejora con más datos, pero **la discriminación no se traduce en rentabilidad** con esta configuración.

---

## Diagnóstico cruzado

```
HALLAZGO PRINCIPAL:
┌─────────────────────────────────────────────────┐
│  Reducir rotación ayuda significativamente:     │
│  holding 1h convierte −26% → +17% en 2024      │
│  y gana en 2023 H1/H2.                         │
│                                                 │
│  PERO no basta: pierde en 2022 H1/H2.          │
│                                                 │
│  El target binario 1h tiene mejor              │
│  discriminación (ROC AUC 0.66-0.75) pero        │
│  peor rentabilidad en walk-forward que           │
│  el original 15m + holding 1h.                  │
│                                                 │
│  Ninguna combinación probada produce            │
│  retorno neto positivo en los 4 semestres.      │
└─────────────────────────────────────────────────┘
```

### Patrón temporal claro

- **2022**: el modelo pierde en todas las variantes. Mercado bajista fuerte (B&H −57% y −17%).
- **2023**: el modelo gana con holding 1h. Mercado alcista (+84% y +39%).
- **2024**: holding 1h funciona bien. Mercado alcista (+121%).

El modelo solo funciona en mercados alcistas y con rotación reducida. En mercados bajistas no sabe apartarse a tiempo.

→ **Esto apunta directamente al detector de régimen** (Fase 10 del plan) como necesidad, no como lujo.

---

## Por dónde seguir

Tu conclusión es correcta: features adicionales de tendencia, régimen y volatilidad, usando las variantes actuales como controles.

### Qué features añadir (por orden de prioridad)

**Grupo 1 — Régimen y tendencia (impacto alto esperado)**

Estos datos ya están disponibles en el histórico o se calculan de las features existentes:

| Feature | Fuente | Por qué |
|---------|--------|---------|
| `trend_strength` | Pendiente de regresión lineal de N cierres | Distingue trending vs ranging |
| `adx_14` | Calculado de ATR | Fuerza de tendencia, agnóstico de dirección |
| `regime_volatility` | Ratio volatility_20 actual vs media 100 velas | Alta/baja volatilidad relativa |
| `drawdown_from_peak` | Distancia del precio al máximo reciente | Indica mercado bajista |
| `consecutive_up/down` | Racha de velas alcistas/bajistas | Momentum discreto |
| Lags de features | `return_1[-1]`, `return_1[-4]`, `rsi[-1]`, etc. | Contexto temporal sin Transformer |

**Grupo 2 — Datos externos (requiere ingesta nueva)**

| Feature | Fuente | Dificultad |
|---------|--------|-----------|
| `funding_rate` | Ya en TimescaleDB (si se cargó futuros) | Media — necesita alineación temporal |
| `open_interest_delta` | Binance API histórica futuros | Media — nueva descarga |
| `fear_greed` | alternative.me (diario) | Baja — pocos datos por día |
| `btc_dominance` | CoinGecko (diario) | Baja — pocos datos por día |

### Cómo hacerlo (protocolo)

```
1. Definir las features ANTES de ver sus resultados
   → Registrar la lista y la justificación en el doc
   → No iterar buscando la feature "que funciona en 2024"

2. Añadir a dataset.py como features_v2
   → Mantener v1 como control
   → Mismo pipeline: aggregate → compute → export

3. Entrenar XGBoost con v2 + holding 1h
   → Walk-forward en los 4 semestres internos
   → Comparar contra v1 + holding 1h (el mejor control actual)

4. Criterio de éxito:
   → Retorno neto positivo en ≥ 3 de 4 semestres
   → Edge neto por operación > 0 en ≥ 3 de 4 semestres
   → Si no: analizar feature importance y eliminar las inútiles

5. NO tocar test, NO promover a producción
```

### Lo que destacaría del patrón 2022 vs 2023

El patrón más revelador es que el modelo funciona en 2023 (alcista) y no en 2022 (bajista). Esto sugiere:

- **El modelo long-only está estructuralmente expuesto al régimen de mercado.** Sin shorts, en un mercado bajista lo mejor que puede hacer es no operar, pero necesita features que le digan "este es un mercado bajista, quédate fuera".

- **Las features v1 son todas técnicas de corto plazo** (returns, RSI, ATR, volumen) — ninguna captura el régimen macro. Un `drawdown_from_peak` de 50 velas o un `trend_strength` de 100 velas le daría al modelo información que ahora no tiene.

- **Los lags son potencialmente los más importantes**: el modelo ve cada vela aislada, sin memoria de las anteriores. Añadir `return_1[-1]`, `return_1[-4]`, `rsi[-1]` le da un mínimo de contexto secuencial sin necesidad de Transformer.

---

## Estado del repositorio

```
src/
├── backtesting/
│   ├── engine.py              ✅ Actualizado (políticas de salida)
│   ├── experiment.py          ✅ Actualizado (comparativa multi-política)
│   └── (resto sin cambios)
├── models/xgboost/
│   └── classifier.py          ✅ Actualizado (target binario 1h)
├── features/dataset.py        ✅ Sin cambios (v1 intacto)
└── (resto sin cambios)

tests/                         ✅ 72 tests (65 → 72)
docs/
├── 001-004 walkthroughs       ✅ Sin cambios
├── exit-horizon-experiments.md ✅ Nuevo
├── xgboost-diagnostics.md     ✅ Sin cambios
├── backtesting.md             ✅ Sin cambios
└── (resto sin cambios)
```

---

## Resumen de la trayectoria experimental

| Iteración | Cambio | Mejor resultado 2024 | Walk-forward internos positivos |
|:----------|:-------|---------------------:|-------------------------------:|
| v1 original | — | −26,26% | 1 de 4 |
| Umbral 0.40 | Bajar umbral | −77,92% | 0 de 4 |
| Umbral 0.35 | Bajar más | −85,49% | 0 de 4 |
| + Holding 1h | Política de salida | **+17,36%** | **2 de 4** |
| + Solo DOWN | Política de salida | +15,32% | 0 de 4 |
| + Hold 1h + DOWN | Ambas | +65,41% | 1 de 4 |
| Binario 1h + hold | Target + salida | −1,32% a −54,93% | 0 de 4 |

**Mejor control actual**: features v1 + XGBoost 15m + holding 1h → 2/4 semestres positivos.

Siguiente: features v2 (régimen, tendencia, lags) con este control como referencia.
