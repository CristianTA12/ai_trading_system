# Walkthrough 006 — Features v2 (Régimen y Lags): No Supera Criterio

**Fecha**: 2026-09-26
**Commit**: `8f7f080` en `develop`
**Fase**: 4 (continuación) — tercera iteración experimental
**Tests**: 78 pasando

---

## Lo que se ha probado

Cinco features nuevas añadidas como bloque, definición preregistrada (commit `a99a2ec`) antes de entrenar:

| Feature | Definición | Justificación |
|---------|-----------|---------------|
| `drawdown_from_peak_2880` | Distancia al máximo de 2.880 velas (~30 días) | Señal de mercado bajista |
| `return_1_lag1` | Retorno 15m de la vela anterior | Contexto secuencial inmediato |
| `return_1_lag4` | Retorno 15m de hace 4 velas (1h) | Contexto secuencial a 1h |
| `rsi_lag1` | RSI de la vela anterior | Momentum reciente |
| `directional_efficiency_96` | Eficiencia direccional de 96 velas (~24h) | Fuerza de tendencia |

Total: 25 features (20 v1 + 5 nuevas). Target 15m tres clases, holding 1h, entrada UP argmax p_up ≥ 0.50.

---

## Resultado: NO supera el criterio

| Semestre | V1 (filas emparejadas) | V2 | Diferencia |
|:---------|-----------------------:|---:|-----------:|
| 2022 H1 | −22,02% | −49,58% | **−27,56 pp** |
| 2022 H2 | −6,74% | −33,97% | **−27,23 pp** |
| 2023 H1 | +3,86% | +1,97% | −1,89 pp |
| 2023 H2 | +6,97% | +1,40% | −5,57 pp |
| **Positivos** | **2/4** | **2/4** | — |

**V2 es peor que V1 en los cuatro semestres.** No se promueve.

Edge neto por operación v2: −13,80 / −17,08 / +2,01 / +1,55 pb.

### Impacto del warmup

El drawdown de 30 días requiere 2.880 velas continuas de warmup. Esto reduce el train significativamente:

| Fold | Train original | Train emparejado | Reducción |
|:-----|---------------:|-----------------:|---------:|
| 2022 H1 | 69.221 | 36.011 | **−48%** |
| 2022 H2 | 86.597 | 51.254 | −41% |
| 2023 H1 | 104.261 | 68.918 | −34% |
| 2023 H2 | 121.581 | 83.408 | −31% |

En 2022 H1 se pierde casi la mitad del train. Esto perjudica a ambos brazos, pero explica en parte por qué los resultados emparejados difieren del control histórico.

---

## Análisis

### ¿Por qué ha empeorado?

Tres hipótesis no excluyentes:

1. **Pérdida de datos de train por warmup.** El drawdown de 30 días elimina los primeros ~30 días continuos de cada segmento. En los folds tempranos (2022 H1) esto cuesta casi la mitad del train. Menos datos = peor generalización, especialmente para XGBoost con 500 árboles.

2. **Ruido amplificado.** Las 5 features nuevas pueden añadir más ruido que señal. Con 25 features en vez de 20 y menos datos, el modelo tiene más dimensiones donde sobreajustar. La feature importance mostraría si las nuevas absorben importancia de las útiles.

3. **El bloque completo no es la mejor receta.** El experimento evalúa las 5 juntas. Es posible que los lags ayuden pero el drawdown de 30 días perjudique (por el warmup). Una ablación lo aclararía, pero sería otro experimento con protocolo propio.

### Lo que el resultado SÍ dice

- Esta combinación concreta de 5 features con esta ventana de warmup no mejora el modelo. Rechazada.
- El control v1 emparejado (reentrenado con las mismas filas) obtiene resultados diferentes al histórico → la cobertura importa, no solo las features.
- La disciplina de preregistro es impecable. No se ha ajustado nada post-hoc.

### Lo que NO dice

- No demuestra que el régimen sea irrelevante como concepto.
- No demuestra que los lags no aporten valor (el warmup los penaliza junto al drawdown).
- No descarta que una ventana de drawdown más corta (ej: 100-200 velas en vez de 2.880) funcione con menos pérdida de datos.

---

## Dónde estamos — Mapa de decisión

```
                    Features v1 + holding 1h
                    (mejor resultado: 2/4 positivos)
                           │
            ┌──────────────┼──────────────┐
            │              │              │
       Target 15m     Target 1h      Features v2
       3 clases       binario        25 features
       hold 1h        hold 1h        hold 1h
            │              │              │
        2/4 ✓          0/4 ✗          2/4 ✗
      (mejor)        (peor)       (peor que v1)
            │
            │
      ¿Qué queda por probar?
```

### Opciones siguientes (por orden de pragmatismo)

**Opción A — Ablación de features v2 (esfuerzo bajo)**
- Separar lags del drawdown: probar solo `return_1_lag1` + `return_1_lag4` + `rsi_lag1` (sin warmup largo).
- Si los lags solos mejoran → el problema es el drawdown de 30 días, no el concepto.
- Probar drawdown con ventana más corta (200 velas = ~2 días en vez de 30).

**Opción B — Cambio de paradigma: regresión (esfuerzo medio)**
- En vez de clasificar UP/NEUTRAL/DOWN, predecir el retorno esperado directamente.
- Solo operar si `retorno_esperado > costes + margen`.
- Alinea la predicción con la pregunta económica real.
- Features v1, holding 1h, walk-forward en los 4 folds.

**Opción C — Datos externos: funding + OI (esfuerzo medio-alto)**
- Requiere nueva ingesta (Binance futuros) y alineación temporal.
- Funding rate es una de las pocas features con fundamentación económica clara (coste de apalancamiento).
- Pero si el modelo v1 con 20 features no encuentra señal estable, añadir 2 más probablemente tampoco baste.

**Opción D — Replantear el enfoque (esfuerzo conceptual)**
- 6 experimentos y el modelo solo funciona en mercados alcistas con holding forzado.
- En un long-only spot, ¿se necesita realmente un modelo? B&H hace +121% en 2024.
- El valor del modelo sería **evitar los drawdowns en mercados bajistas** (2022), no superar a B&H en mercados alcistas.
- Replantear el objetivo: "¿Puedo perder menos que B&H en 2022 mientras capturo >60% de B&H en 2023/2024?"
- Esto cambia la métrica de éxito de "retorno neto positivo" a "Sharpe o Sortino mejor que B&H".

### Mi recomendación

**Opción A primero** (es rápida y aclara si el warmup de 30 días fue el problema), luego **Opción D** como reflexión de fondo. Llevas 6 iteraciones rigurosas, todas rechazadas por el criterio correcto. Antes de la séptima, merece la pena repensar si el objetivo "3/4 semestres neto positivo" es el correcto para un long-only spot, o si debería ser "mejor risk-adjusted return que B&H de forma consistente".

---

## Estado del repositorio

```
src/features/dataset.py        ✅ Actualizado (v2 features)
tests/                         ✅ 78 tests (72 → 78)
docs/
├── 001-005 walkthroughs
├── features-v2-protocol.md    ✅ Nuevo (preregistro)
├── features-v2-results.md     ✅ Nuevo (resultados)
└── (resto sin cambios)
```

## Trayectoria experimental completa

| # | Cambio | 2024 | WF internos + |
|:-:|:-------|-----:|:-------------:|
| 1 | v1 original | −26,26% | 1/4 |
| 2 | Umbral 0.40 | −77,92% | 0/4 |
| 3 | Umbral 0.35 | −85,49% | 0/4 |
| 4 | + Holding 1h | **+17,36%** | **2/4** |
| 5 | + Solo DOWN | +15,32% | 0/4 |
| 6 | + Hold 1h + DOWN | +65,41% | 1/4 |
| 7 | Binario 1h + hold | −1% a −55% | 0/4 |
| 8 | **v2 features + hold 1h** | **no evaluado** | **2/4 (peor que v1)** |
