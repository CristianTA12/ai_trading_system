# Campaña de cinco horas — resultados del 2026-10-16

**Completada y verificada. No es necesaria otra tanda para cerrar esta
validación técnica.** Terminó a las 13:46:27,730 de Madrid por límite temporal.
Las tres sesiones tienen cierre limpio, manifiesto verificado y revisión de
agregados. No se ha iniciado otra captura.

| Sesión | Mensajes | Cierres distintos | Minutos completos esperados | Barras 15m | Barras 1h |
|---|---:|---:|---:|---:|---:|
| 01 | 3.489 | 120 | 119 | 7 | 1 |
| 02 | 3.462 | 120 | 119 | 7 | 1 |
| 03 | 1.782 | 60 | 59 | 3 | 0 |
| Total | **8.733** | **300** | **297** | **17** | **2** |

Capturas: 5.280.460 bytes en total, por debajo del presupuesto de 150 MB.
Cero payloads inválidos, duplicados exactos, revisiones de cierres o saltos de
reloj mayores de un segundo detectados; un intento de conexión por sesión.
Ningún cierre ausente entre los minutos completos esperados de cada sesión.

## Cobertura y límites

Hubo **19,94 y 16,05 segundos** entre la última recepción de una sesión y la
primera de la siguiente. Son interrupciones reales de recepción por cierre,
verificación y reconexión. No se presenta la campaña como un stream continuo.
La unión diagnóstica de timestamps de cierre contiene 300 minutos distintos,
sin minutos ausentes entre el primero y el último; esto no demuestra recepción
de todos los mensajes intermedios del proveedor.

Las tres velas parciales iniciales explican los 300 cierres frente a 297 minutos
completos esperados. El agregador trabaja por sesión y descarta ventanas que
cruzan sus fronteras; por eso cinco horas de campaña no equivalen a cinco barras
horarias entregadas. No se han unido sesiones ni rellenado datos para elevar
esa cifra. La cobertura de cierres y la cantidad de barras son métricas distintas.

## Revisión reproducible

Origen inmutable: `data/prospective/campaign-20261016-five-hours`.
Revisión externa: `data/experiments/campaign-review-20261016`.
Se conserva `verification.json`, hashes de los archivos observados y el script
de revisión. Los manifiestos originales de cada sesión sí estaban presentes y
se validaron; los hashes adicionales de revisión identifican el resto de archivos.

Se repitió la verificación de integridad y replay en 606 fronteras de recepción.
Los agregados guardados coinciden con una nueva ejecución del agregador. Además,
un cálculo directo independiente desde los minutos raw reproduce OHLC,
los cuatro volúmenes y el número de trades de las 17 barras 15m y dos barras 1h.
Las capturas originales no se modificaron.

## Decisión de continuación

Se cierra el hito técnico de captura acotada por sesiones y agregación causal
en vivo. No acredita operación permanente, latencia absoluta ni rentabilidad.
El reloj permanece marcado como sincronización desconocida, sin bloquear
la recogida. No hubo modelos, órdenes ni consulta del test histórico reservado.

El usuario dispone de otras cuatro horas, pero repetir ahora la recogida no
resuelve una pregunta técnica pendiente de este piloto ni una hipótesis de alpha.
Se conserva esa disponibilidad sin lanzar procesos innecesarios. El siguiente
hito del [plan actualizado](implementation_plan_fase4b_ai_trading.md) es justificar
una hipótesis económica distinta antes de preregistrar cualquier it.18; la
familia anterior sigue cerrada según la revisión post-it.17.
