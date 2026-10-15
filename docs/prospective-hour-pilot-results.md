# Piloto horario completado — revisión 2026-10-16

**Validación técnica superada.** El segundo intento completó la hora objetivo
del 15 de octubre, 21:00–22:00 Madrid (19:00–20:00 UTC), y se detuvo por
`duration_limit`. Finalizó aproximadamente a las 22:00:33 Madrid, incluido
el cierre del socket. No necesita reiniciarse ni prolongarse.

| Comprobación | Resultado |
|---|---:|
| Mensajes conservados | 2.800 |
| Minutos cerrados distintos | 97 |
| Minutos completos esperados en la ventana | 96 |
| Cierres ausentes de esos minutos | 0 |
| Mensajes inválidos / duplicados / revisiones cerradas | 0 / 0 / 0 |
| Intentos de conexión | 1 |
| Saltos del reloj superiores a 1 segundo detectados | 0 |
| Barras completas de 15m | 6 |
| Barras completas de 1h | 1 |
| Tamaño de la captura, incluido su manifiesto | 1.689.221 bytes |
| Tiempo total de ejecución | 5.839,188 segundos |
| Fronteras temporales verificadas | 196 |
| Modelos entrenados / órdenes enviadas | 0 / 0 |

Un cierre de una vela parcial al inicio explica la diferencia entre 97 cierres
recibidos y 96 minutos completos esperados. No implica cobertura acreditada
de todos los mensajes emitidos por el proveedor.

## Evidencia y revisión adicional

Carpeta original inmutable: `data/prospective/hour-pilot-20261015`.
Contiene plan, captura, resultado, agregados, verificación y manifiesto de revisión.
SHA256 del manifiesto de captura:
`c6e2ef1dae291f1cdb5bb7a46714c3e5d8f3da4a5ec8212f6e9a8bde106713ad`.

La revisión del 16 de octubre volvió a verificar el conjunto exacto de archivos
y los hashes de los nueve archivos del manifiesto de revisión, además del
manifiesto propio de la captura. Se repitió la verificación de secuencias,
cierre limpio y replay por recepción.

Un cálculo adicional directo sobre minutos raw, independiente de la función
de agregación, reprodujo OHLC, los cuatro volúmenes, número de trades, límites
temporales y referencias a mensajes de las seis barras 15m y la barra 1h.
La hora reconstruida coincide con la hora objetivo del plan.
El script utilizado se conserva junto a la revisión externa en
`data/experiments/hour-pilot-review-20261016`.

El primer intento permanece registrado como
[interrumpido](prospective-hour-pilot-interruption.md). No se mezclaron sesiones
ni se rellenaron huecos con datos históricos. No se modificó la captura original.

## Qué queda validado

Captura pública acotada, parada automática, archivos íntegros, trazabilidad y
agregación causal de una hora real completa. No acredita estabilidad 24/7,
latencia absoluta, rentabilidad ni ventaja frente a B&H. La sincronización del
reloj sigue marcada desconocida; no impide este resultado de agregación.

Se cierra este piloto. Antes de una campaña continua habría que fijar equipo,
almacenamiento y supervisión de interrupciones. No se inicia automáticamente
otra captura ni una nueva iteración de modelos a partir de este resultado.
