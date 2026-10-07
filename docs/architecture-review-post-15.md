# Revisión de arquitectura — Fase F, después de it.15

**Actualización posterior:** la prueba propuesta se preregistró y ejecutó
como [it.16](iteration-16-results.md). Rechazo 2/5 frente a 1/5 del control;
H1 sigue fallando y aparece DD concatenado de 17,03% en una semilla.
Se cierra la prueba sin barrer variantes. El resto conserva el razonamiento
previo a conocer esos resultados.

Fecha: 2026-10-07. Alcance: revisión del diseño y diagnóstico de artifacts
existentes. **Cero modelos entrenados y cero backtests nuevos en esta revisión.**
It.13, it.14 e it.15 siguen rechazadas. No se abre el test 2025–2026, paper ni live.

## Decisión recomendada

Mantener el objetivo y `risk-return-v1`. Antes de cambiar de algoritmo o añadir
datos, hacer **una sola prueba de persistencia de posición** con los modelos
SP500 de it.15 congelados: misma entrada, holding mínimo 4h y gate, pero
cerrar por DOWN como argmax en vez de cerrar cuando desaparece la entrada.
La [propuesta it.16](iteration-16-proposal.md) fija todos los detalles.
Es una prueba de política de salida, no otro entrenamiento ni una nueva fuente.

Esta recomendación es una hipótesis de arquitectura, no un resultado. No se ha
calculado el rendimiento de la política alternativa ni se ha elegido por él.
Si falla, cerrar esta prueba sin barrer umbrales/holdings y decidir un cambio
de objetivo o arquitectura más profundo antes de continuar la familia actual.

## Qué cambió con la evidencia

| Cuestión | Evidencia disponible | Implicación |
|---|---|---|
| Costes consumen todo el edge | En it.15: 36,32 pb brutos y 26,29 pb netos medios por operación | Ya no describe esta receta; sigue existiendo fricción, pero no es el único bloqueo |
| Exposición bajista sin control | Gate fijo limita fuertemente la exposición; DD it.15 6,78–9,61% | No hace falta asumir que long-only pierde inevitablemente en bear |
| Macro no aporta nada | It.15 mejora compuesto y DD en 5/5 frente a control | Hay mejora descriptiva condicional; no demuestra alpha estable ni causalidad de cada feature |
| Más retorno basta | It.15 pasa 1/5, control 2/5 | La consistencia de Sharpe/DD por fold sigue siendo el cuello de botella |
| Quitar gate resuelve H1 | It.13 sin gate falla H1 en todas las semillas; regime_only tampoco supera B&H | No optimizar SMA50/200 ni quitar el gate por ese razonamiento |
| Falta potencia del algoritmo | No hay evidencia aquí que identifique capacidad de XGBoost como causa | Cambiar a LightGBM/Transformer no es aún la intervención mejor aislada |

Estos resultados provienen de folds de desarrollo utilizados repetidamente.
Las cinco semillas no son cinco mercados independientes. SP500 sigue
condicionado a snapshot representativo y disponibilidad asumida +48 h.

## El punto de diseño que se puede aislar

El modelo clasifica retornos 4h en DOWN (<−1%), NEUTRAL y UP (>+1%). Su salida
`multi:softprob` representa clases, no un retorno esperado neto ni una orden
óptima de liquidación. [Definición oficial de XGBoost](https://xgboost.readthedocs.io/en/stable/parameter.html#learning-task-parameters).
Además se entrena con pesos de clase; el proyecto no ha demostrado calibración
de las probabilidades. No interpretar `p_up=0,5` como 50% empírico de beneficio.

La política actual exige UP argmax y p_up≥0,5 para entrar. Tras las cuatro
horas mínimas, también exige esa condición para seguir dentro. Por tanto,
**ausencia de señal fuerte para abrir una posición nueva equivale a vender
una posición existente**. Es una elección explícita del código, no un bug.
Separar ambas decisiones permite medir su efecto sin cambiar el modelo.

NEUTRAL incluye tanto movimientos pequeños positivos como negativos; no es
una predicción de mercado plano ni de posición segura. Por ejemplo, −0,9%
en 4h pertenece a NEUTRAL. Mantenerlo puede aumentar pérdidas, duración y DD.
Un horizonte de label 4h tampoco implica que renovar la decisión manteniendo
una posición más tiempo produzca beneficio. Son riesgos que la prueba debe medir.

## Diagnóstico de las salidas existentes

Se leyeron predicciones, gate, targets y trades base de it.15; cada salida
por señal se contrastó con la transición long→cash. No se añadieron precios
posteriores a la salida ni retornos contrafactuales. Los inputs conservan sus hashes.

| Causa observada en la salida | SP500 it.15 | Control v1 |
|---|---:|---:|
| DOWN como argmax | 106 | 129 |
| NEUTRAL como argmax | 253 | 387 |
| UP argmax con p_up<0,5 | 167 | 181 |
| Predicción ausente | 1 | 0 |
| Total | **527** | **697** |

En SP500, 420/527 salidas (79,70%) corresponden a NEUTRAL o UP insuficiente.
En H1 2023 son 234/304 (76,97%): 124 NEUTRAL, 110 UP insuficiente, 69 DOWN
y una predicción ausente. Esta última debe seguir forzando cash.

**Lo que no se puede deducir:** que el 79,70% de las ventas fuera incorrecto,
que hubiera que mantener 420 trades más tiempo, o que las nuevas entradas
fuesen las mismas. Al cambiar salidas cambia toda la secuencia de posiciones,
capital y entradas. La alternativa necesita un replay completo independiente.
No se pueden concatenar artificialmente trades ni sumar PnL contrafactual.

## Relación con los experimentos antiguos

Las variantes `exit_down` y `hold_60m_exit_down` ya se probaron sobre el modelo
15m, y no resolvieron el objetivo. Véase
[experimentos de salida](exit-horizon-experiments.md). No se presenta la idea
como inédita ni se omite ese resultado negativo.

La prueba propuesta contrasta una interacción diferente y delimitada:
clasificador 4h ±100 pb, SP500, gate diario y holding mínimo 4h. Su motivación
es el cambio comprobado de receta y la atribución actual de salidas, no asumir
que una política antes fallida ahora funcionará. Se reutilizan todos los modelos
y semillas de it.15, sin elegir la única semilla que pasó.

## Alternativas de Fase F y prioridad

| Alternativa | Decisión de esta revisión |
|---|---|
| Separar entrada y mantenimiento | Primera prueba propuesta: una variable, sin modelos nuevos ni supuestos temporales adicionales |
| Replantear como filtro de exposición | Decisión de producto distinta; requeriría mandato y benchmark propios antes de experimentar, sin reclasificar it.15 como aprobada |
| Nuevo horizonte/decisiones diarias | Posible familia posterior; modifica target y dinámica, no demuestra por sí sola más edge |
| Modelo separado de régimen | Primero justificar régimen causal y tamaño de muestra; no etiquetar bull/bear usando el futuro |
| LightGBM/modelos secuenciales | Posponer hasta identificar una limitación predictiva que el cambio pretende resolver |
| Microestructura/order book | Requiere auditoría de disponibilidad y ejecución; no es un sustituto inmediato del problema diagnosticado |
| Shorts | Nuevo framework de instrumento, financiación, ejecución y riesgo; fuera de esta prueba spot |

No existe una imposibilidad matemática de superar Sharpe B&H con long-only
deducible de estos resultados. Tampoco puede prometerse que mayor exposición
lo consiga. El diagnóstico H1 ya mostró que importan media, volatilidad y
selección temporal, no solo porcentaje de tiempo dentro.

## Entregables y cierre de la revisión

- Script [review_exit_architecture.py](../scripts/review_exit_architecture.py).
- Artifacts `data/experiments/phase-f-exit-review-20261007/`: salidas,
  recuentos por fold y agregado, manifiesto de inputs y hashes.
- Seis tests específicos pasan: clasificación de salida, casos forzados,
  frontera de confianza y protección del directorio fuente. La última suite
  completa anterior a este diagnóstico pasó 224 tests y omitió dos de integración.
- Propuesta it.16 preparada; todavía sin implementación ni evaluación de esa política.

La revisión completa el análisis solicitado de Fase F; no convierte la
consolidación general del runner, los dashboards ni el despliegue en tareas
terminadas. El siguiente trabajo concreto es preregistrar e implementar la
prueba delimitada, manteniendo cerrado el test reservado.
