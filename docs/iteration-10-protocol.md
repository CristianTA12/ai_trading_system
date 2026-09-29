# Protocolo preregistrado — Iteración 10: regresión con umbral de coste

Registrar en Git **antes** de entrenar o evaluar. Cualquier cambio posterior
requiere nueva versión con justificación y nuevo commit previo a la ejecución.

## Hipótesis

Un XGBoost de regresión que prediga la magnitud del retorno, operando solo
cuando el retorno esperado supere los costes con margen, generará menos
operaciones con mayor edge neto por operación. Se evalúa la receta completa
(target continuo + objetivo de entrenamiento + política de salida) contra el
criterio risk-return-v1. Cambiar tres elementos a la vez mide la combinación,
no aísla el efecto de la regresión.

## Target

Columna existente `target_return_next_15m`: retorno entre apertura y cierre de
la vela que comienza cuando las features están disponibles. Equivale a
`close[t] / open[t] - 1` en el índice de barras del dataset. Variable continua,
sin discretizar en clases.

## Features

Las 20 columnas v1 del snapshot existente, sin añadir ni quitar. Estas features
mantienen su warmup original; la cobertura no cambia respecto a las iteraciones
v1 anteriores.

## Modelo

XGBoost Regressor (`objective: reg:squarederror`):

| Parámetro | Valor |
|-----------|-------|
| `n_estimators` | 500 |
| `max_depth` | 6 |
| `learning_rate` | 0.05 |
| `subsample` | 0.8 |
| `colsample_bytree` | 0.8 |
| `tree_method` | hist |
| `n_jobs` | 4 |
| `random_state` | semilla del fold |

Sin pesos de clase, sin early stopping con datos de evaluación.
Semillas: **42, 123, 456, 789, 2026**, secuenciales, sin seleccionar la mejor.

## Política de trading

| Regla | Definición |
|-------|-----------|
| Entrada | `predicción ≥ 0,0015` (15 pb) |
| Holding mínimo | 60 minutos desde la ejecución de entrada |
| Salida tras holding | `predicción < 0` (estrictamente negativa) |
| Predicción = 0 | Mantener posición existente |
| Predicción ausente | Efectivo en la siguiente apertura, incluso antes del holding |
| Fin de fold | Liquidar posición |

El umbral de 15 pb es económico y orientativo: frente a ~10 pb de coste base
deja un margen nominal de ~5 pb; con stress (~12 pb), unos ~3 pb. La predicción
cubre 15 minutos y el holding mínimo es 60: el margen no representa el
beneficio esperado de la operación completa. Comprobar si esta combinación
funciona es el propósito del experimento.

Hysteresis: entrar a 15 pb, salir a 0 pb. Esto reduce rotación respecto a
usar el mismo umbral en ambos lados.

## Control emparejado

Clasificador v1 (tres clases, UP argmax, `p_up ≥ 0,50`) + holding 1h,
reentrenado con las mismas filas, mismas semillas, mismas velas de ejecución.
Además: Buy & Hold y efectivo, con los mismos costes base.

## Evaluación

- 4 folds internos: 2022 H1, 2022 H2, 2023 H1, 2023 H2.
- Train expansivo desde 2020 hasta el inicio de cada semestre.
- Purga de labels cuyo horizonte alcance la frontera.
- 5 semillas; evaluador automático aplica risk-return-v1.
- Escenario base: taker 0,04%, slippage 0,01% por ejecución.
- Escenario stress: taker 0,04%, slippage 0,02% por ejecución.
- Mismas predicciones y reglas en stress; recalcular ejecución y equity.
- **2024 no se reevalúa. Test 2025–2026 reservado.**
- Capital: 10.000 USDT por semestre, sin posiciones entre folds.

## Métricas y diagnóstico

### Criterio (evaluador automático)

Retorno compuesto, drawdown ≤ 15%, consistencia Sharpe > B&H, stress, ≥4/5 semillas.
Gate histórico (≥3/4 positivos) como referencia.

### Diagnóstico adicional (por fold y semilla)

| Métrica | Descripción |
|---------|-------------|
| MAE / RMSE | Error del regresor; comparar contra predecir cero y contra la media del train |
| Retorno realizado 15m cuando predicción ≥ 15 pb | ¿El modelo identifica correctamente movimientos grandes? |
| Correlación predicción vs retorno real | Capacidad predictiva continua |
| % predicciones ≥ umbral | Tasa de señal activa |
| Operaciones, duración media/mediana, exposición | Rotación y uso del holding |
| Edge neto medio por operación (pb) | ¿Supera costes? |
| Distribución de predicciones por régimen | ¿Predice bajo en 2022, alto en 2023? |

Una predicción continua no queda automáticamente calibrada. Correlación y MAE
no demuestran rentabilidad.

## Interpretación

- **Si supera el criterio**: congelar receta y diseñar protocolo de evaluación
  final antes de abrir test. No operar con dinero real.
- **Si no supera**: registrar rechazo con las cinco semillas. No reinterpretar
  el criterio. Un rechazo no demuestra que la regresión sea inviable en general
  ni que features adicionales no puedan aportar valor en otra receta.
- No se compromete la iteración 11 ni su diseño.

## Artifacts a guardar

- Protocolo con hash del YAML risk-return-v1 y del código.
- Versiones de dependencias.
- Features metadata y cobertura de train/eval por fold.
- Predicciones y targets por fold.
- Modelos `.ubj` por fold y semilla.
- Posiciones, operaciones, fills y equity por fold/semilla/escenario.
- Curvas brutas y netas.
- Métricas de clasificación del control y de regresión del candidato.
- Comparativa JSON/CSV.
- Veredicto del evaluador automático.
- Todo registrado en MLflow.
