# Piloto prospectivo de calidad — 2026-10-13

**Completado, verificado y detenido.** Valida captura y reconstrucción por
recepción local; no constituye un resultado de estrategia ni una iteración 18.

## Ejecución y evidencia

Collector del commit `5f170651c23b8a593d47c9e39936c5d46570fccb`, Python 3.12.7
y websockets 15.0.1 en Windows. Stream público BTCUSDT spot de velas 1m,
sin claves. Ventana configurada de 600 segundos y límite de 50.000.000 bytes.
La sesión terminó por `duration_limit`, con salida 0; el tiempo total fue
603,047 segundos, incluido el cierre del socket y elaboración del informe.
No queda servicio ni tarea de captura ejecutándose.

| Comprobación | Resultado |
|---|---:|
| Mensajes conservados | 274 |
| Cierres de minuto distintos | 10 |
| Minutos completos esperados dentro de la ventana | 9 |
| Cierres ausentes de esos minutos | 0 |
| Mensajes inválidos / duplicados / revisiones cerradas | 0 / 0 / 0 |
| Intentos de conexión | 1 |
| Saltos del reloj superiores a 1 segundo detectados | 0 |
| Tamaño total, incluido manifiesto | 167.488 bytes |
| Fronteras temporales verificadas por replay | 22 |
| Modelos entrenados / órdenes enviadas | 0 / 0 |

Diez cierres recibidos y nueve minutos completos son compatibles: la vela
parcial al inicio puede cerrar durante la sesión sin pertenecer al denominador
de minutos observados completos. Esto no acredita recepción de todos los
mensajes emitidos por el proveedor.

Captura original inmutable: `data/prospective/pilot-20261013-kline-1m`.
Revisión y copia archivada: `data/experiments/prospective-pilot-review-20261013`.
SHA256 del manifiesto de captura:
`48c52af8f21943c9687dee6ad416a046cce716748094a1a42ae56b679663264d`.
El hash del código ejecutado coincide con el collector local.

El verificador confirmó el conjunto exacto de archivos, hashes, presupuesto,
secuencias, cierre de conexiones, métricas recalculadas y disponibilidad
estrictamente anterior a cada decisión. Compara el replay principal con un
recorrido inverso independiente; ambos comparten parser y cálculo de métricas.
La suite completa previa pasó 258 tests, con dos omitidos; los ocho tests del
collector pasaron de nuevo en WSL tras los ajustes, incluida detección de
manipulación de archivos. Ocho comprobaciones de esas funciones también
pasaron en Python nativo; no se ejecutó pytest nativo por dependencias ausentes.

## Límite del reloj y siguiente paso

La consulta de Windows conservada en `session.json` indica **sin sincronizar**,
origen `Local CMOS Clock` y sin última sincronización correcta registrada.
El informe automático mantiene `clock_synchronization: unknown`: no interpreta
la salida localizada ni demuestra sincronización. No se modificó el reloj.

Las diferencias evento→recepción observadas fueron 1.071,48–1.740,36 ms y el
máximo cierre→recepción fue 1.199,13 ms. Incluyen desfase de reloj, transporte,
procesamiento y colas: **no son latencia absoluta acreditada**. Tampoco la
ausencia de saltos demuestra ausencia de deriva o desfase constante.

El siguiente paso técnico es verificar y resolver la sincronización del reloj
antes de una campaña prolongada, conservando evidencia del estado y del desfase.
Después queda implementar agregación causal 15m/1h y validar sesiones más largas
con huecos/reconexiones. Este piloto no prueba estabilidad 24/7, rentabilidad,
edge frente a B&H ni disponibilidad histórica de funding o macro. No se han
ejecutado entrenamientos, backtests ni evaluaciones del test reservado.
