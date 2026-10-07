# Walkthrough 008 — Iteración 10: Regresión XGBoost — Rechazada

**Fecha**: 2026-09-29
**Commits**: `d3cfde6` (protocolo), `8b9c902` (implementación), `8752f87` (código)
**Fase**: 4 (décima iteración experimental)
**Tests**: 135 pasando, 2 integración omitidos
**Criterio**: risk-return-v1 · **Resultado**: 0/5 semillas

---

## Receta evaluada

| Elemento | Valor |
|----------|-------|
| Target | `target_return_next_15m` (continuo) |
| Modelo | XGBoost Regressor (`reg:squarederror`) |
| Features | v1 (20 variables) |
| Entrada | `predicción ≥ 15 pb` |
| Holding | 60 minutos mínimo |
| Salida | `predicción < 0` estrictamente; `= 0` mantiene |
| Semillas | 42, 123, 456, 789, 2026 |
| Control | Clasificador v1 + holding 1h, mismas filas/semillas |

Protocolo preregistrado antes de entrenar. Sin ajustes post-hoc.

---

## Resultado: 0/5 semillas cumplen (control también 0/5)

| Semilla | Regresión compuesta | DD concatenado | Folds consistentes | Control compuesto |
|:-------:|--------------------:|---------------:|:------------------:|------------------:|
| 42 | −39,95% | 43,97% | 1/4 | −47,68% |
| 123 | −31,01% | 36,54% | 1/4 | −32,19% |
| 456 | −26,08% | 40,44% | 1/4 | −34,06% |
| 789 | −29,46% | 38,34% | 1/4 | −12,32% |
| 2026 | −49,23% | 52,81% | 1/4 | −17,02% |

Falla en las 4 dimensiones: rentabilidad, riesgo (DD >> 15%), consistencia (1/4) y stress.

### Por semestre (regresión, 5 semillas)

| Semilla | 2022 H1 | 2022 H2 | 2023 H1 | 2023 H2 |
|:-------:|--------:|--------:|--------:|--------:|
| 42 | −5,08% | −32,67% | −7,25% | +1,30% |
| 123 | −10,57% | −19,18% | −8,31% | +4,10% |
| 456 | **+5,22%** | −25,25% | −12,04% | +6,85% |
| 789 | −0,02% | −21,88% | −10,89% | +1,35% |
| 2026 | −22,06% | −33,81% | −3,26% | +1,71% |

Patrón: positivo solo en 2023 H2 (5/5 semillas) y una excepción en 2022 H1.
Pierde en 2022 H2 y 2023 H1 con las 5 semillas.

---

## Diagnóstico clave

### El modelo NO predice mejor que "predecir cero"

**RMSE peor que predecir cero en 19 de 20 evaluaciones fold/semilla.** Esto es la señal más preocupante: el modelo de regresión no solo no es rentable — es peor que no predecir nada. La regresión pierde capacidad predictiva útil que la clasificación al menos parcialmente tenía (balanced accuracy > random).

### Predicciones vs realidad: calibración rota

| Fold | Media predicha (pb) | Media realizada (pb) |
|:-----|--------------------:|---------------------:|
| 2022 H1 | +30 a +31 | +0,2 a +4,3 |
| 2022 H2 | +32 a +36 | **−12 a −5** |
| 2023 H1 | +27 a +29 | −7 a +8 |
| 2023 H2 | +37 a +47 | +8 a +29 |

El modelo predice +30 pb de media cuando la señal supera el umbral, pero la realidad es cercana a 0 o negativa en 3 de 4 semestres. El modelo está sistemáticamente sobreestimando los retornos futuros.

### Menos rotación, pero no basta

57,84% menos operaciones (1.693 vs 4.016 del control). La reducción de rotación funciona como se esperaba, pero sin predicciones útiles, operar menos simplemente pierde menos rápido.

---

## Trayectoria completa: 10 iteraciones

| # | Variante | Mejor WF+ | Criterio |
|:-:|:---------|:---------:|:--------:|
| 1 | v1 clasificador original | 1/4 | ✗ |
| 2 | Umbral 0.40 | 0/4 | ✗ |
| 3 | Umbral 0.35 | 0/4 | ✗ |
| 4 | v1 + holding 1h | 2/4 | ✗ |
| 5 | v1 + solo DOWN | 0/4 | ✗ |
| 6 | v1 + hold 1h + DOWN | 1/4 | ✗ |
| 7 | Binario 1h + hold | 0/4 | ✗ |
| 8 | v2 (25 features) + hold 1h | 2/4 | ✗ |
| 9 | v1 + lags + hold 1h | 2/4 | ✗ |
| **10** | **Regresión + 15pb + hold 1h** | **1/4 (×5 seeds)** | **✗ (0/5)** |

---

## Qué sabemos después de 10 iteraciones

```
EVIDENCIA ACUMULADA:

1. CLASIFICACIÓN vs REGRESIÓN
   La clasificación v1 tiene algo de señal (bal.acc > random).
   La regresión pierde esa señal: RMSE peor que predecir cero.
   → El paso a regresión empeoró las cosas, no las mejoró.

2. LAS 20 FEATURES V1 TÉCNICAS TIENEN UN TECHO
   10 iteraciones con las mismas 20 features: ninguna combinación
   de modelo/target/política alcanza rentabilidad consistente.
   → La información contenida en estas features no es suficiente.

3. EL HOLDING 1H SIGUE SIENDO LA MEJOR PALANCA
   La mejora más grande en 10 iteraciones fue simplemente
   mantener las posiciones más tiempo. Esto sugiere que el
   problema no es tanto la dirección como la ejecución.

4. EL PATTERN 2022 H2 ES CONSISTENTEMENTE MALO
   Todas las variantes pierden en 2022 H2 (B&H: −17%).
   Incluso con B&H negativo, ningún modelo sabe apartarse.

5. MULTI-SEMILLA CONFIRMA FRAGILIDAD
   5 semillas × 4 folds = 20 evaluaciones.
   Resultados varían significativamente entre semillas.
   Ninguna semilla cumple el criterio completo.
```

---

## ¿Dónde estamos? Decisión de dirección

Después de 10 iteraciones con las mismas 20 features v1, el espacio de
exploración de modelo/target/política sobre este set de features está
razonablemente agotado. Las dos líneas que quedan abiertas implican
cambiar la información disponible para el modelo:

| Línea | Qué cambia | Esfuerzo | Riesgo |
|-------|-----------|----------|--------|
| **Datos externos** (funding, OI, sentimiento) | Información económica nueva, no derivada de precios | Medio-alto (ingesta nueva) | Si la señal está en derivados/sentimiento, podría funcionar |
| **Datos de order book** (aggTrades) | Microestructura: presión compradora/vendedora | Alto (150 GB de datos, feature engineering complejo) | Alta calidad informativa pero latencia y complejidad |

No propondría una iteración 11 específica sin que decidas primero si quieres
seguir iterando sobre el mismo marco (spot BTC, XGBoost, 4 folds 2022–2023)
o dar un paso atrás más amplio.

---

## Documentación

- [Informe de ejecución](file:///d:/ai_trading_system/data/experiments/iteration-10-20260929T120800005192Z/execution-report.md)
- [Protocolo preregistrado](file:///d:/ai_trading_system/docs/iteration-10-protocol.md)
- MLflow: experimento 6, run `0f797e63327d40a9a313f643d058786e`
- 40 modelos + 120 backtests + veredicto automático en artifacts
