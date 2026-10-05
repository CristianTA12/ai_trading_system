# Diagnóstico de consistencia 2023 H1 — Iteración 13

Fecha: 2026-10-05. Alcance: bloque C del
[plan de fase 4B](implementation_plan_fase4b_ai_trading.md), utilizando exclusivamente
resultados ya existentes. **No hay promoción: se mantiene el veredicto 2/5.**
No se entrenaron modelos, ejecutaron backtests nuevos ni consultaron 2024 o el test
2025–2026. Este diagnóstico exploratorio no constituye un preregistro de iteración 14.

## Conclusión

El fallo observado combina una parte relevante del rally excluida por el gate,
una selección del clasificador que deja una exposición de solo 6,93–7,68%, y
una relación media/volatilidad diaria insuficiente en las operaciones realizadas.
**No puede atribuirse exclusivamente al gate, a los costes o a un supuesto
bloqueo de reentradas.** Los artifacts permiten describir estos mecanismos, pero
no identificar causalmente qué cambio de target o política resolvería el problema.

La auditoría independiente vuelve a validar 40 modelos, 200 backtests, filas
emparejadas, etiquetas por timestamp, políticas y veredictos. Los cinco candidatos
fallan 2023 H1; las semillas 456 y 2026 obtienen su tercer semestre consistente
en **2023 H2**, no en H1. El aprobado cash de 2022 H2 sigue vigente.

## 1. Rendimiento y exposición reales

B&H: **+84,03%, Sharpe 2,7343, exposición 100%**. Las métricas siguientes son
netas, escenario base, sobre el semestre completo y las mismas filas.

| Semilla | Retorno | Sharpe | DD | Exposición | Operaciones | Retorno / retorno B&H |
|---|---:|---:|---:|---:|---:|---:|
| 42 | 8,31% | 0,7962 | 11,15% | 6,93% | 74 | 9,88% |
| 123 | 12,98% | 1,2641 | 10,29% | 7,23% | 77 | 15,45% |
| 456 | 15,70% | 1,3690 | 13,58% | 7,68% | 82 | 18,68% |
| 789 | 1,29% | 0,2249 | 14,90% | 7,03% | 75 | 1,53% |
| 2026 | 9,13% | 0,9553 | 9,95% | 7,60% | 81 | 10,86% |

El cociente de retornos es descriptivo; no es alpha ni ajusta por riesgo o tiempo.
La exposición mide barras con posición, no fracción de días con rentabilidad.
Hay retornos diarios distintos de cero en 54–60 de las 181 observaciones diarias.
La estimación del plan de exposición del 30–40% no se confirma.

## 2. El gate sí excluyó una parte importante del rally

Abrió el **2023-02-08 a las 00:15 UTC** y estuvo abierto el 78,99% de las barras.
Descomponiendo multiplicativamente los retornos de la curva B&H existente:

| Intervalos de la curva B&H | Factor compuesto | Retorno equivalente |
|---|---:|---:|
| Gate cerrado | 1,404435 | +40,44% |
| Gate abierto | 1,310338 | +31,03% |
| Semestre completo | 1,840283 | +84,03% |

Se cumple `1,404435 × 1,310338 = 1,840283`; los porcentajes no se suman.
Cada retorno entre puntos de equity se asigna al gate de la barra cuyo cierre
lo registra. Es una descomposición contable de B&H, con sus fricciones ya
incluidas, no dos estrategias simuladas ni una atribución causal del PnL.

El benchmark **regime_only** ya ejecutado obtiene +30,96% y Sharpe 1,4248:
tampoco supera B&H en este semestre. El control **4h sin gate** obtiene
retornos +3,61% a +18,60% y Sharpes 0,3959–1,4131; falla en las cinco semillas.
Por tanto, quitar el gate tampoco resuelve el fallo en los resultados existentes.
No se propone optimizar SMA50/200 retrospectivamente.

## 3. Selección, costes y Sharpe

| Semilla | Señales UP ≥0,5 | Elegibles con gate | Entradas reales | Media bruta por trade | Media neta por trade | Sharpe bruto |
|---|---:|---:|---:|---:|---:|---:|
| 42 | 362 | 286 | 74 | 22,41 pb | 12,39 pb | 1,4047 |
| 123 | 373 | 295 | 77 | 27,43 pb | 17,41 pb | 1,9635 |
| 456 | 372 | 297 | 82 | 29,57 pb | 19,55 pb | 2,0451 |
| 789 | 347 | 277 | 75 | 13,30 pb | 3,29 pb | 0,8555 |
| 2026 | 380 | 307 | 81 | 22,30 pb | 12,28 pb | 1,7126 |

Señal exige además argmax UP; no equivale a orden ejecutada. Las restantes
202–226 señales elegibles ocurren con posición ya abierta. El control sin gate
tampoco supera el 10,32% de exposición: la baja participación no procede solo
del filtro. Los cinco Sharpes **brutos** quedan incluso por debajo del Sharpe
**neto** de B&H (2,7343). Reducir fricción por sí solo no explica cómo aprobar.

Se reconstruyen exactamente las series diarias usadas por `compute_metrics`:
bins UTC cerrados a la derecha, desviación muestral y anualización √365.

| Semilla | Media diaria neta | Desv. diaria | Media necesaria para igualar Sharpe B&H, si la desviación permaneciera fija |
|---|---:|---:|---:|
| 42 | 5,15 pb | 123,67 pb | 17,70 pb |
| 123 | 7,34 pb | 110,97 pb | 15,88 pb |
| 456 | 8,79 pb | 122,71 pb | 17,56 pb |
| 789 | 1,46 pb | 123,68 pb | 17,70 pb |
| 2026 | 5,39 pb | 107,84 pb | 15,43 pb |
| B&H | 37,02 pb | 258,70 pb | 37,02 pb |

La última columna es `Sharpe_BH × sigma_observada / sqrt(365)`, una identidad
condicional, no una predicción al aumentar exposición. No existe un Sharpe
máximo deducible únicamente del porcentaje de exposición; tanto media como
volatilidad y selección temporal importan. Los cinco trades de mayor PnL
representan entre 1,59 y 14,94 veces el beneficio neto del semestre: las pérdidas
compensan una parte importante de las ganancias y el cociente de 789 se amplifica
por su beneficio total pequeño. No son cinco observaciones independientes entre semillas.

## 4. Clases: desplazamiento de distribución, no ausencia de ejemplos UP

Distribución real con ±100 pb; las cinco semillas comparten las mismas etiquetas.
Los CSV incluyen cada semilla y los cuatro folds, sobre sus filas exactas.

| Fold | Filas train | UP train | % UP train | Filas evaluación puntuables | UP evaluación | % UP evaluación |
|---|---:|---:|---:|---:|---:|---:|
| 2022 H1 | 68.981 | 12.933 | 18,75% | 17.360 | 2.644 | 15,23% |
| 2022 H2 | 86.357 | 15.585 | 18,05% | 17.648 | 1.994 | 11,30% |
| 2023 H1 | 104.021 | 17.595 | 16,91% | 17.289 | 1.710 | 9,89% |
| 2023 H2 | 121.326 | 19.305 | 15,91% | 17.648 | 1.114 | 6,31% |

En H1 hay 17.304 predicciones: 15 carecen de outcome completo y se excluyen
solo del scoring, no de las señales. Las clases train de H1 son
DOWN 16.567 / NEUTRAL 69.859 / UP 17.595; evaluación:
1.294 / 14.285 / 1.710. Hay miles de ejemplos UP, aunque su prevalencia baja.
La precisión UP por argmax es 22,15–23,07%, frente a prevalencia 9,89%; recall
20,41–21,58%. Estas métricas usan toda la evaluación puntuable, sin gate ni
filtro de confianza: no son precisión de las entradas ni calibración de `p_up`.

Sensibilidad **descriptiva de etiquetas** en las mismas filas de 2023 H1:

| Umbral | % UP train | % UP evaluación | Peso UP train N/(3×n_UP) |
|---|---:|---:|---:|
| 50 pb | 28,79% | 20,39% | 1,158 |
| 75 pb | 21,89% | 13,68% | 1,523 |
| 100 pb, receta ejecutada | 16,91% | 9,89% | 1,971 |

Los pesos calculados sobre evaluación en el CSV son **hipotéticos**, únicamente
descriptores de distribución; nunca se aplican al entrenamiento. Ningún modelo
de 50/75 pb ha sido entrenado aquí. Más etiquetas UP no demuestra más entradas,
mejor calibración, mayor edge ni una mejora del criterio. Tampoco demuestra
que el balanceo de clases esté causando el fallo.

## 5. Holding: aplaza salidas; no impone cooldown

El replay independiente coincide barra a barra con los targets y con todas las
compras de fills/trades. La mediana es 240 minutos; los máximos son 360–420 minutos.
No hubo cierres forzados por gate en H1 porque no volvió a cerrarse tras abrir.

| Semilla | Barras con salida diferida por holding | Reentradas a menos de 4h de la salida anterior | Menor intervalo de reentrada |
|---|---:|---:|---:|
| 42 | 918 | 20 | 15 min |
| 123 | 960 | 25 | 15 min |
| 456 | 1.037 | 28 | 15 min |
| 789 | 944 | 18 | 15 min |
| 2026 | 1.013 | 22 | 15 min |

Las barras de salida diferida son estados repetidos dentro de trades, no trades
perdidos. Las señales UP mientras ya se está long no son reentradas bloqueadas.
No hay evidencia del supuesto cooldown; valorar si salir antes mejoraría el
resultado exige un experimento diferente, con otra secuencia de operaciones.

## 6. Semillas e importancia de features

Las cuatro primeras features son iguales y en el mismo orden en las cinco semillas:
`atr_14_sma_ratio`, `weekday_sin`, `range_ratio`, `volatility_20`.
La quinta es `hour_cos` o `weekday_cos`. La correlación Spearman de rankings
entre pares es **0,9895–0,9955**: no aparece una inestabilidad grande del ranking.
La importancia del modelo no es una atribución causal ni una medición del edge.

La correlación de `p_up` es 0,9773–0,9796; la diferencia absoluta media es
1,87–1,97 puntos porcentuales y el acuerdo de argmax 94,50–94,81%.
Sin embargo, el Jaccard de timestamps exactos de entrada es solo **0,3478–0,4364**,
y el de barras long 0,6003–0,6819. Son decisiones y secuencias sensibles a cambios
pequeños de predicción. Jaccard penaliza también entradas desplazadas una sola barra;
no significa que todas las operaciones no coincidentes sean oportunidades distintas.
Esto describe variación entre semillas, no un test de perturbación del dataset.

## 7. Implicaciones para el plan

- Corregir las premisas: exposición ≈7%, gate abierto 79% pero con rally excluido,
  holding sin cooldown y todas las semillas fallando H1. El DD concatenado del
  candidato it.13 es **9,95–14,90%**, no 5,52–14,90% (5,52% corresponde a it.12).
- Mantener `risk-return-v1`, SMA50/200, costes taker y test reservado. La baja
  exposición no justifica sustituir retrospectivamente B&H para aprobar esta receta.
- Entre las propuestas del bloque D, el diagnóstico debilita la motivación de
  holding 2h como remedio a «reentradas bloqueadas». Investigar el target es una
  hipótesis razonable por la selectividad y el cambio de prevalencias, pero todavía
  no hay evidencia de que 50 o 75 pb mejoren el resultado económico.
- Antes de entrenar otra iteración, fijar una sola intervención y su control,
  filas, semillas, política, costes y criterio en un preregistro. No elegir el
  umbral mediante un barrido sobre estos resultados. La reiteración de consultas
  sobre 2022–2023 limita la fuerza confirmatoria de futuras mejoras allí.

Este trabajo completa el diagnóstico solicitado del bloque C. No declara
terminada toda la fase 4B: cierre documental de 4A, consolidación del runner y
cualquier intervención posterior siguen siendo trabajos separados.

## Reproducción y trazabilidad

Registrado en [MLflow local, experimento 10, run 38847d023b404a8d8eeab976dc181354](http://localhost:5000/#/experiments/10/runs/38847d023b404a8d8eeab976dc181354),
como diagnóstico separado y vinculado al run original de la iteración 13.

Script: [scripts/diagnose_2023h1.py](../scripts/diagnose_2023h1.py).
Tests: [tests/test_diagnose_2023h1.py](../tests/test_diagnose_2023h1.py), cinco casos
aprobados: fronteras de etiquetas, agregación diaria, reentrada inmediata,
salida por gate y protección de directorios. Ruff aprobado.

```bash
python scripts/verify_four_hour_experiment.py data/experiments/iteration-13-20260930-four-hour
python scripts/diagnose_2023h1.py data/experiments/iteration-13-20260930-four-hour data/experiments/iteration-13-diagnostic-20261005
pytest tests/test_diagnose_2023h1.py -q
```

El segundo comando requiere una carpeta de salida nueva; no sobrescribe runs.
Salida: `data/experiments/iteration-13-diagnostic-20261005/`, con tablas
`summary.csv`, `class_distribution.csv`, `consistency.csv`, `feature_importance.csv`,
`seed_similarity.csv`, `all_arms_2023h1.csv`, `market.json` y `manifest.json`.
El manifiesto registra SHA256 de todos los inputs leídos y del script, y verifica
que los inputs no cambian durante el diagnóstico. La verificación independiente
adicional reconstruye las etiquetas usando exclusivamente la partición train.

Correcciones al borrador adjunto: columna `target_return` en el artifact de
etiquetas; `classification.json` en lugar de `diagnostics.json`; ventanas exactas
tomadas de los artifacts, sin aproximar H2 desde enero; consistencia leída del
veredicto completo, incluida excepción cash y drawdown; señales separadas de
ejecuciones. El adjunto y el plan original se conservan sin modificación.
