# Walkthrough 007 — Ablación de Lags: No Supera Criterio

**Fecha**: 2026-09-26
**Commit**: `8e7eae3` en `develop`
**Fase**: 4 (continuación) — cuarta iteración experimental
**Tests**: 84 pasando

---

## Experimento

23 features (20 v1 + 3 lags), sin warmup largo. Protocolo preregistrado en `0b77438`.

| Feature añadida | Warmup | Pérdida de cobertura |
|-----------------|--------|---------------------|
| `return_1_lag_1` | 1 vela | 68 filas (0,049%) |
| `return_1_lag_4` | 4 velas | — |
| `rsi_14_cutler_lag_1` | 1 vela | — |

Cobertura prácticamente intacta: 139.177 de 139.245 filas. Diferencia irrelevante.

---

## Resultado: 2/4 positivos, no supera ≥3/4

| Semestre | V1 emparejado | V1 + lags | B&H | Sharpe lags | DD lags |
|:---------|-------------:|----------:|----:|------------:|--------:|
| 2022 H1 | −15,26% | −30,38% | −56,89% | −2,271 | 38,49% |
| 2022 H2 | −32,36% | −30,95% | −17,13% | −2,411 | 38,38% |
| 2023 H1 | −3,69% | **+12,61%** | +84,03% | **+1,700** | 7,90% |
| 2023 H2 | **+8,56%** | +1,74% | +38,62% | +0,446 | 4,84% |

- Lags mejor que v1 en 2/4 semestres (2022 H2 y 2023 H1), peor en los otros 2.
- Sharpe inferior a B&H en los 4 semestres.
- Drawdown menor que B&H en 3/4 (excepto 2022 H2).
- No promovido.

### Observación crucial: sensibilidad del control

El control v1 emparejado obtiene **1/4 positivos**, cuando el control histórico obtenía 2/4. La diferencia es de solo 68 filas. Esto revela que **el modelo XGBoost con estos parámetros es frágil**: pequeños cambios en el train alteran los resultados de semestres enteros.

---

## Balance de 9 iteraciones

| # | Variante | Semestres + | Criterio |
|:-:|:---------|:-----------:|:--------:|
| 1 | v1 original | 1/4 | ✗ |
| 2 | Umbral 0.40 | 0/4 | ✗ |
| 3 | Umbral 0.35 | 0/4 | ✗ |
| 4 | v1 + holding 1h | **2/4** | ✗ |
| 5 | v1 + solo DOWN | 0/4 | ✗ |
| 6 | v1 + hold 1h + DOWN | 1/4 | ✗ |
| 7 | Binario 1h + hold | 0/4 | ✗ |
| 8 | v2 (25 features) + hold 1h | 2/4 | ✗ |
| 9 | v1 + lags + hold 1h | 2/4 | ✗ |

**Ninguna de las 9 variantes supera ≥3/4.** El mejor resultado (2/4) se obtiene por tres caminos diferentes (hold 1h, v2, lags), siempre con el mismo patrón: positivo en 2023, negativo en 2022.

---

## Qué sabemos después de 9 experimentos

```
1. SEÑAL DÉBIL PERO REAL
   Balanced accuracy > random, ROC AUC 0.66-0.75,
   retornos brutos positivos en todos los umbrales.
   El modelo captura algo, pero no lo suficiente.

2. COSTES DESTRUYEN EL EDGE
   La ganancia media por operación (~4-10 pb) no cubre
   las fricciones (~10 pb). Reducir rotación (holding 1h)
   ayuda pero no resuelve.

3. DEPENDENCIA DEL RÉGIMEN
   Funciona en mercados alcistas (2023, 2024).
   Pierde en bajistas (2022).
   Un long-only sin información de régimen está
   estructuralmente expuesto a esto.

4. FRAGILIDAD DEL MODELO
   68 filas de diferencia en train cambian el resultado
   de un semestre entero. El modelo no es robusto.

5. FEATURES ≠ SOLUCIÓN MÁGICA
   Ni lags, ni drawdown, ni tendencia han cambiado el
   patrón fundamental. El problema es más profundo que
   "faltan features".
```

---

## Siguiente paso propuesto

El usuario planteó: *"usar esta evidencia para fijar un criterio de riesgo y rentabilidad concreto antes de seguir iterando"*. Después de 9 variantes, este es el momento correcto para hacerlo.

### Propuesta de reflexión antes de la iteración 10

Antes de probar otra feature o modelo, responder a estas preguntas:

**1. ¿Qué problema estamos resolviendo realmente?**

| Objetivo | Implicación | Métrica |
|----------|-------------|---------|
| "Ganar dinero en cualquier régimen" | Necesita shorts o un asset que suba en bajistas | Retorno neto > 0 por semestre |
| "Ganar más que B&H con menos riesgo" | Solo necesita estar fuera en los peores momentos | Sharpe > B&H, DD < B&H |
| "Evitar drawdowns grandes" | El valor es la protección, no el retorno | Max DD significativamente < B&H |
| "Saber cuándo NO estar en el mercado" | El modelo es un filtro, no un generador de alpha | % de bajadas evitadas vs subidas perdidas |

**2. ¿El framework actual puede responder a eso?**

- Long-only spot con 20 features técnicas de corto plazo y XGBoost: es una combinación que inherentemente funciona mejor en mercados alcistas.
- Sin datos de futuros (funding, OI) ni sentimiento, el modelo no tiene información sobre el posicionamiento del mercado.
- Sin shorts, la mejor acción en un bajista es cash — pero el modelo necesita features de régimen macro para saberlo.

**3. ¿Cuál es el coste de seguir iterando vs cambiar el enfoque?**

Después de 9 variantes sin éxito, cada iteración adicional del mismo tipo tiene rendimientos decrecientes. Dos alternativas de más alto impacto:

| Opción | Cambio | Por qué podría funcionar |
|--------|--------|--------------------------|
| **Datos de futuros** (funding + OI) | Información económica nueva, no técnica | Funding es coste de apalancamiento; OI muestra convicción |
| **Regresión en lugar de clasificación** | Alinea la predicción con la pregunta económica | Solo opera si retorno_esperado > costes |

Ambas cambian el tipo de información disponible para el modelo, no solo su configuración.

---

## Documentación

- [lags-ablation-results.md](file:///d:/ai_trading_system/docs/lags-ablation-results.md) — resultados completos
- [lags-ablation-protocol.md](file:///d:/ai_trading_system/docs/lags-ablation-protocol.md) — protocolo preregistrado
- MLflow: experimento `spot-lags-ablation`, run `eca3cde7c4a744fe8e5af58dc60741f6`
