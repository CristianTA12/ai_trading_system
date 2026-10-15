# Piloto horario interrumpido — revisión 2026-10-15

**No completó la hora objetivo y no pasa la validación.** El proceso original
ya no estaba presente al revisar. No existen `result.json`, informe final de
captura ni manifiesto de cierre. El log solo contiene inicio y conexión;
no registra desconexión ni parada. La causa de la interrupción no puede
determinarse con estos archivos; no se atribuye a una acción concreta del usuario.

## Datos conservados

Sesión original: `data/prospective/hour-pilot-20261014`.

| Medida | Resultado |
|---|---|
| Primer mensaje (Madrid, 14 de octubre) | 22:53:28,632 |
| Último mensaje (Madrid, 14 de octubre) | 23:37:38,545 |
| Intervalo entre primer y último mensaje | 44 min 9,913 s |
| Mensajes JSON legibles | 1.318 |
| Payloads inválidos detectados | 0 |
| Minutos cerrados distintos | 44 |
| Minutos cerrados ausentes de la hora objetivo 23:00–00:00 | 23 |
| Barras completas recuperables de 15m | 2: 23:00 y 23:15 |
| Horas completas | 0 |

Se comprobaron secuencias consecutivas, ID de sesión, unidad temporal y
monotonía del reloj monotónico. Los agregados derivados solo usan cierres
recibidos antes de la decisión de revisión (última recepción +1 ns).
El minuto 23:37 tenía mensajes abiertos, pero no cierre recibido.

La revisión está en `data/experiments/interrupted-hour-review-20261015`:
`review.json`, `recovered_aggregates.json` y `observed_source_hashes.json`.
Los hashes se calcularon durante la revisión: permiten identificar lo observado
ahora, **no sustituyen el manifiesto original ausente ni prueban integridad
desde la captura**. Los archivos originales permanecen intactos. No se han
fabricado reportes de cierre ni rellenado minutos con otra fuente.

## Continuación

Se conserva este intento como interrumpido. Un segundo intento usa una carpeta
distinta, `data/prospective/hour-pilot-20261015`, con el mismo runner y los mismos
límites (50 MB, tres intentos, hora UTC completa más margen y parada automática).
Sus resultados deben evaluarse por separado. No se mezclan las dos sesiones
para presentar una hora completa ni se elimina el fallo anterior.

El equipo debe permanecer encendido y sin suspender durante la sesión.
No se ha modificado la configuración de energía ni instalado un servicio.
El resultado del segundo intento solo existirá cuando finalice la captura
y su revisión automática; el arranque no acredita éxito.
