# Implementation Plan — Cierre de Fase 4A y apertura de Fase 4B

**Proyecto:** `ai-trading-system`
**Fecha:** 2026-10-05 (revisado tras iteraciones 11–13)
**Objetivo:** cerrar de forma reproducible la exploración con XGBoost + features técnicas v1, diagnosticar el bloqueo de consistencia de la receta 4h + gate, y abrir una nueva etapa centrada en resolver ese bloqueo y, si es necesario, incorporar información de mercado nueva.

---

## 0. Principio de trabajo para la siguiente etapa

A partir de este punto no se seguirá iterando sobre el mismo espacio de búsqueda de forma indefinida.

Se mantiene como norma:

- No tocar el test 2025–2026 hasta que una receta supere el criterio prospectivo.
- No elegir retrospectivamente la mejor semilla.
- No cambiar varias familias de hipótesis a la vez.
- Toda receta nueva se define antes de ejecutarse.
- XGBoost se mantiene como baseline mientras se cambia primero la información disponible.
- MLflow sigue siendo la fuente de trazabilidad experimental.
- Grafana se usa para visualización y diagnóstico, no como sustituto de MLflow.
- Paper trading y trading real permanecen fuera de esta etapa.
- No introducir todavía shorts, leverage, múltiples posiciones, Transformer, ensemble ni RL.

---

## 0B. Estado actual del proyecto — Punto de partida real

### 13 iteraciones completadas

| # | Variante | Cambio principal | Resultado | Commit |
|:-:|----------|:-----------------|:---------:|:------:|
| 1 | v1 clasificador | Baseline | 1/4 folds+ | — |
| 2 | Umbral 0.40 | Bajar confianza | 0/4 | — |
| 3 | Umbral 0.35 | Bajar más | 0/4 | — |
| 4 | v1 + holding 1h | Política de salida | 2/4 | — |
| 5 | v1 + solo DOWN | Política de salida | 0/4 | — |
| 6 | v1 + hold 1h + DOWN | Ambas políticas | 1/4 | — |
| 7 | Binario 1h + hold | Target + horizonte | 0/4 | — |
| 8 | v2 (25 features) + hold 1h | Régimen + lags | 2/4 | 8f7f080 |
| 9 | v1 + lags + hold 1h | Solo lags | 2/4 | 8e7eae3 |
| 10 | Regresión 15m + 15pb | Modelo + target | 0/5 semillas | 8752f87 |
| 11 | v1 + funding rate | Datos de derivados | 0/5 semillas | 9ccd153 |
| 12 | v1 + SMA50>SMA200 gate | Filtro de régimen | 0/5 (DD resuelto) | b76c3c2 |
| 13 | 4h + gate + hold 4h | Horizonte + régimen | **2/5 semillas** | df241c5 |

### Mejor receta conocida: iteración 13

```text
Mercado: BTC/USDT spot
Modelo: XGBoost classifier (3 clases, mismos hiperparámetros v1)
Features: v1 — 20 features técnicas de 15m
Target: retorno 4h, clases ±1%
Entrada: UP argmax y p_up >= 0.50
Holding mínimo: 240 minutos
Gate: SMA50 diaria > SMA200 diaria (cierre 23:45 UTC)
Dirección: long-only
Capital inicial por fold: 10.000 USDT
Fee taker: 0,04% por ejecución
Slippage base: 0,01% por ejecución
```

| Métrica | Valor |
|---------|-------|
| Retornos compuestos netos | +14,58% a +29,90% |
| Drawdown concatenado | 5,52% a 14,90% |
| Rentabilidad positiva | 5/5 semillas |
| DD ≤15% | 5/5 semillas |
| Stress positivo | 5/5 semillas |
| **Consistencia ≥3/4** | **2/5 semillas** (falla) |
| Edge neto por trade | +15,62 pb |
| Operaciones agregadas | 697 (5 semillas × 4 folds) |

**Bloqueo**: 2023 H1 no cumple consistencia en ninguna semilla (Sharpe < B&H).
Las semillas 456 y 2026 consiguen el tercer semestre en 2023 H2.

### Lo que ya se ha probado y no debe repetirse

| Fuente | Estado | Referencia |
|--------|--------|-----------|
| Funding rate | Rechazado. 0/5, no aporta sobre v1 | it.11, `9ccd153` |
| Open Interest | No viable. Cobertura 66-80% < 95% requerido | Auditoría, `99a4b75` |
| Features v2 (régimen+lags) | Rechazado. 2/4 folds, no mejora v1 | it.8, `8f7f080` |
| Regresión | Rechazada. RMSE peor que predecir cero | it.10, `8752f87` |

---

# Fase A — Cierre formal de Fase 4A

## A1. Documentar las 13 iteraciones

Crear `docs/009_walkthrough_cierre_fase4a.md` con:

- Tabla consolidada de las **13** iteraciones.
- Identificación de la receta it.13 como mejor candidato conocido.
- Lista de hipótesis rechazadas y aprendizajes.
- Confirmación de que test 2025–2026 sigue intacto.
- Los dos descubrimientos clave:
  - Filtro de régimen SMA50>SMA200 resuelve el riesgo (DD de 33-47% → 5-15%).
  - Horizonte 4h resuelve el edge por operación (de −0,51 a +15,62 pb neto).

### Criterio de cierre

```text
CERRADA
NO PROMOVIDA
MEJOR CANDIDATO: iteración 13 (4h + gate), 2/5 semillas
CONSERVADO PARA INVESTIGACIÓN
```

---

## A2. Sincronizar documentación

Revisar que `risk-return-v1.md`, `risk-return-v1.yaml`, `000_contexto_proyecto.md`
y los runners reflejen exactamente el mismo criterio. Actualizar
`000_contexto_proyecto.md` para incluir las iteraciones 11–13 y la situación actual.

### Entregables

- `000_contexto_proyecto.md` actualizado.
- `risk-return-v1.yaml` verificado contra el evaluador.
- Hash del criterio registrado en cada experimento futuro (ya se hace).

---

# Fase B — Consolidación del framework experimental

## B1. Runner genérico reutilizable

Actualmente cada iteración duplica ~250-300 líneas de runner. Consolidar en un
framework que acepte:

```text
Inputs:
  - dataset path + hashes
  - feature builder (callable)
  - target builder (callable)
  - policy builder (callable)
  - gate builder (callable, opcional)
  - model config
  - seeds [42, 123, 456, 789, 2026]
  - folds [2022 H1, 2022 H2, 2023 H1, 2023 H2]
  - scenarios [gross, base, stress]
  - control arms

Outputs:
  - protocol.json con hashes
  - predictions, targets, equity, fills, trades por fold/seed/arm/scenario
  - comparison.csv
  - verdicts JSON
  - MLflow registration
```

El runner debe:
- Verificar preregistro en Git.
- Validar hashes de inputs.
- Calcular cobertura y exigir ≥95%.
- Ejecutar evaluador automático.
- Guardar artifacts sin sobrescribir.

**No reescribir desde cero**: refactorizar `funding_experiment.py`, `regime_gate_experiment.py`
y el runner de it.13, extrayendo el patrón común.

### Criterio de cierre

- Ejecutar una iteración existente con el runner nuevo y obtener resultados idénticos.
- ≥5 tests del framework.

---

# Fase C — Diagnóstico de consistencia 2023 H1 ✅ COMPLETADO

**Completado**: 2026-10-05. Documento: [diagnostic-2023h1-consistency.md](diagnostic-2023h1-consistency.md).

### Hallazgos clave

- B&H en 2023 H1: **+84,03%, Sharpe 2,7343**. Estructuralmente difícil de superar.
- Exposición del candidato: **6,93–7,68%** (no 30-40% como se estimó).
- Gate abierto 79% pero el **40,44% del rally de B&H ocurre con gate cerrado**.
- Sharpe bruto (sin costes) de todas las semillas queda por debajo del Sharpe neto de B&H.
- Holding no impone cooldown: hay re-entradas a 15 min de la salida anterior.
- Features importances estables entre semillas (Spearman 0,99+).
- Jaccard de entradas exactas solo 0,35-0,44: decisiones sensibles a semilla.

**Conclusión**: el fallo combina rally parcialmente excluido por gate, exposición
~7%, y relación media/volatilidad diaria insuficiente. No puede atribuirse a
una causa única ni resolverse cambiando solo el umbral.

---

# Fase D — Iteración 14: umbral ±75 pb ✅ COMPLETADO — RECHAZADO

**Completado**: 2026-10-05. Documento: [iteration-14-results.md](iteration-14-results.md).

### Resultado

- Candidato ±75 pb: **1/5 semillas** (peor que control ±100 pb: 2/5).
- Edge neto por trade: 10,48 pb (vs 15,62 pb del control).
- 2023 H1 sigue fallando en las 5 semillas.
- Más etiquetas UP no se traduce en mejor selección económica.
- El diagnóstico C descartó holding como causa → D2 no se ejecutó.
- D3 (criterio v2) no se ejecutó: no se relaja el criterio.

**Decisión**: caso D4 activado → proceder a Fase E (datos macro).

---

# Fase E — Nueva información: contexto macro ← PASO ACTIVO

Fase D no resolvió la consistencia. Se activa esta fase.

## E1. Ingesta macro inicial

Fuentes:

```text
S&P500 (Yahoo Finance / FRED — gratuitas)
VIX (CBOE vía Yahoo Finance — gratuita)
DXY (FRED / Yahoo Finance — gratuita)
```

### Requisitos de ingesta

- Fuente documentada y gratuita.
- Timestamps UTC.
- Datos raw conservados con checksums.
- Validación de duplicados/gaps.
- Alineación causal estricta: un dato macro solo se usa después de su
  disponibilidad real.
- Variables de antigüedad (`data_age`) para mercados cerrados.
- BTC opera 24/7; estos mercados no. Los fines de semana y feriados
  deben gestionarse explícitamente.
- Nunca forward-fill que introduzca información futura.

---

## E2. Features macro v3

Propuesta orientativa:

```text
sp500_return_1d
sp500_sma_distance_20
vix_level
vix_change_1d
dxy_return_1d
```

Con variables de antigüedad:

```text
sp500_data_age_hours
vix_data_age_hours
```

### Experimento

```text
CONTROL: 4h + gate (iteración 13/14, la mejor vigente)
CANDIDATO: 4h + gate + features macro
```

### Condición

No combinar derivados (funding) y macro en la misma prueba. Funding ya fue
rechazado; si se quiere re-explorar sobre la receta 4h + gate, es una
iteración separada con preregistro propio.

---

## E3. Auditoría de causalidad (si se añaden features externas)

Tests específicos para:

- Cierre/apertura de S&P500 y mercados de divisas.
- Fines de semana y feriados (BTC opera, macro no).
- `data_age` calculado correctamente.
- Gaps y forward-fill.
- Train/validation/test boundaries.
- Purge coherente con el horizonte del target.

---

# Fase F — Decisión al final de 4B

## Caso 1 — Ninguna receta supera risk-return-v1

```text
NO abrir test 2025–2026
NO pasar a paper trading
NO saltar directamente a live
```

Abrir una revisión de arquitectura. Opciones a estudiar:

- Reformular el objetivo (filtro de exposición vs alpha).
- Modelo de régimen separado (train bear/bull).
- Datos de order book / aggTrades.
- LightGBM como alternativa rápida.
- Modelos secuenciales (LSTM, Transformer).
- Permitir short en un framework nuevo.
- Replantear si la consistencia frente a B&H es alcanzable con long-only.

---

## Caso 2 — Una receta supera risk-return-v1

No abrir el test inmediatamente. Primero:

1. Congelar código.
2. Congelar features.
3. Congelar parámetros.
4. Congelar semillas o regla de ensemble.
5. Congelar política de entrada/salida.
6. Congelar costes.
7. Registrar hashes.
8. Crear protocolo final de test.
9. Definir por escrito qué resultado permite avanzar y qué obliga a parar.

Después:

```text
TEST 2025–2026
UNA SOLA EVALUACIÓN
```

No reajustar la receta después de ver el test.

---

# Fase G — Paper trading

Solo se abre si el protocolo final y el test permiten avanzar.

Objetivo:

```text
validar: backtest ≈ paper
```

sin dinero real.

### Requisitos previos

- Streaming estable (WebSocket Binance).
- Features realtime equivalentes a training.
- PaperBroker.
- Risk Manager integrado.
- Logging completo.
- Grafana con métricas operativas.
- Alertas.
- Kill switch.
- Comparación automática paper/backtest.

Mantener paper trading durante un periodo suficientemente largo antes de
plantear capital real.

---

# Fase H — Dashboard de investigación (no bloqueante)

## H1. Mantener el dashboard actual de Data Quality

No modificar de forma destructiva. Debe seguir mostrando:

- Velas almacenadas.
- Primera/última vela.
- Cobertura mensual.
- Minutos ausentes.
- Precio.
- Últimas velas.

## H2. Dashboard Model Research & Backtesting

Crear cuando haya estabilidad en la receta. Secciones:

- Market Context (precio, retornos, volatilidad, RSI, volumen).
- Model Signals (probabilidades, señal BUY/CASH, threshold).
- Trading Activity (operaciones, exposición, duración).
- Costs & Edge (bruto, neto, fees, slippage, edge/trade).
- Equity & Risk (curva, B&H, drawdown).
- Model Quality (balanced accuracy, recalls, confusión).
- Experiment Comparison (tabla resumen multi-receta).

Tablas de reporting separadas de las raw; MLflow y artifacts siguen
siendo la fuente experimental.

---

# Tareas que se posponen explícitamente

No forman parte del siguiente bloque de trabajo:

```text
Ampliar histórico a 2017–2019   (no hay evidencia de train insuficiente)
Re-probar funding rate           (ya rechazado en it.11)
Re-probar Open Interest          (cobertura insuficiente)
Transformer temporal
Order book completo
Ensemble
LLM de noticias
Reinforcement Learning
Shorts
Leverage
Múltiples posiciones
Trading real
Optimización masiva con Optuna/Ray
```

No están descartadas; se posponen hasta demostrar necesidad o hasta
que una revisión de arquitectura justifique su entrada.

---

# Orden recomendado de ejecución

```text
1. Cerrar Fase 4A (13 iteraciones documentadas)
        ↓
2. Sincronizar documentación
        ↓
3. Consolidar runner genérico (refactor)
        ↓
4. DIAGNOSTICAR fallo de consistencia 2023 H1     ← CRÍTICO
        ↓
5. Iteración 14: intervención dirigida al bloqueo
        ↓
        ┌─────────────┴─────────────┐
        │                           │
      FALLA                       PASA
        │                           │
6. Macro (S&P/VIX/DXY)        congelar receta
        │                           ↓
        ┌────┴────┐           protocolo final
        │         │                 ↓
      FALLA     PASA          test 2025–2026
        │         │                 ↓
  revisión     congelar        paper trading
  arquitectura   ↓
              protocolo final
                  ↓
              test 2025–2026
                  ↓
              paper trading
```

---

# Definition of Done de esta etapa

La nueva etapa se considera bien ejecutada cuando:

- Fase 4A está cerrada y documentada con las 13 iteraciones.
- Existe una receta candidata identificada (iteración 13 como punto de partida).
- `risk-return-v1` es automático y reproducible.
- Cada experimento utiliza 5 semillas y 4 folds.
- Los resultados se registran en MLflow.
- El test 2025–2026 sigue reservado.
- Se ha diagnosticado la causa del fallo de consistencia en 2023 H1.
- Se ha probado al menos una intervención dirigida a resolver ese bloqueo.
- Existe una decisión documentada de continuar, replantear o congelar una receta.
- Ninguna decisión depende de escoger retrospectivamente el mejor resultado.

---

# Contexto y justificación

La primera etapa del proyecto ha validado correctamente la infraestructura de
datos, el dataset causal, el backtester, los costes, MLflow y un baseline
XGBoost. Se realizaron 13 iteraciones sobre diversas combinaciones de features,
targets, políticas y datos externos.

Los dos descubrimientos más importantes fueron:

1. **El filtro de régimen SMA50>SMA200** (it.12) reduce el drawdown de 33-47%
   a 5-15% y resuelve completamente el gate de riesgo.

2. **El horizonte de 4h** (it.13) mejora el edge por operación de −0,51 a
   +15,62 pb netos, resolviendo rentabilidad y stress en todas las semillas.

El bloqueo restante es concreto: **consistencia en 2023 H1**, donde ninguna
semilla supera el Sharpe de Buy & Hold durante un rally fuerte. Dos semillas
(456, 2026) consiguen 3/4 semestres consistentes; las otras tres solo 2/4.

La conclusión práctica es que el problema está bien localizado y la siguiente
etapa debe diagnosticarlo y atacarlo directamente, no volver a explorar fuentes
de datos ya probadas ni ampliar el histórico sin evidencia de necesidad.

El test 2025–2026 se mantiene reservado porque ya se han utilizado
repetidamente los folds 2022–2023 con fines de desarrollo. Solo debe abrirse
cuando una receta supere el criterio definido y quede completamente congelada.
