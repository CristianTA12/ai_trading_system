# Auditoría de flujo agresor — recuperar datos ya disponibles

Fecha: 2026-10-08. **Viable para preparar un dataset de flujo por minuto;
no se ha demostrado señal predictiva.** Cero modelos y cero backtests.
No se consultan observaciones de 2024 ni del test 2025–2026.

## Decisión

No descargar el histórico completo de aggTrades para una primera prueba de
desequilibrio de volumen. Los ZIP locales de klines 1m ya contienen compras
agresoras en BTC y USDT, aunque la ingesta las descarta antes de guardar OHLCV.
Recuperarlas en un dataset separado conserva el snapshot base y permite
auditar cada agregado. AggTrades queda reservado para hipótesis que requieran
tamaños de operaciones, concentración o secuencias dentro del minuto.

Hipótesis económica propuesta, todavía sin evaluación: el desequilibrio de
volumen ejecutado por compradores/vendedores agresores puede aportar
información de presión negociadora que no contiene el volumen total de v1.
Que pueda calcularse no demuestra persistencia, causalidad económica ni alpha.

## Semántica y fuentes

[Binance Public Data](https://github.com/binance/binance-public-data) documenta
klines con volumen total y taker-buy en base y quote; aggTrades incluye precio,
cantidad, timestamp, IDs y si el comprador es maker. Los archivos tienen
checksums, pueden corregirse posteriormente y spot cambia a microsegundos
en 2025; esta auditoría 2020–2023 usa milisegundos. Hay una actualización
histórica de aggTrades en abril de 2022: congelar hashes, no asumir inmutabilidad.

Según [Spot REST API](https://raw.githubusercontent.com/binance/binance-spot-api-docs/master/rest-api.md),
se agrupan ejecuciones del mismo taker, precio y tiempo. Si buyer_maker=True,
el vendedor es el agresor; False identifica compra agresora. No confundir
número de registros agregados con número de órdenes independientes.
Estas operaciones no reconstruyen profundidad, cancelaciones, spread ni colas.

El [stream oficial](https://raw.githubusercontent.com/binance/binance-spot-api-docs/master/web-socket-streams.md)
incluye tiempo de evento y operación; las klines transmiten estado de cierre
y volúmenes taker-buy. El ZIP histórico no contiene el tiempo de recepción
del cliente. La documentación en vivo no acredita una latencia histórica máxima.

## Auditoría local completa: enero 2020–diciembre 2023

| Comprobación | Resultado |
|---|---:|
| ZIP mensuales con SHA256 verificado | 48/48 |
| Tamaño comprimido ya disponible | 105.786.144 bytes (105,79 MB) |
| Filas raw de un minuto | 2.101.515 |
| Minutos ausentes frente al calendario | 2.325 |
| Duración incorrecta, excluida | 8 filas |
| Volumen agresor inválido/no finito/fuera de rango | 0 filas |
| Minutos con volumen cero | 211 |
| Barras completas 15m reconstruidas | 140.096 |
| Coincidencias con barras del snapshot en volumen y trades | 140.096/140.096 |

Se exige volumen no negativo, taker-buy≤total y números finitos; se verifican
orden, unicidad y pertenencia al mes. No se rellenan huecos. La igualdad
de volumen usa tolerancia numérica; los recuentos de trades coinciden exactamente.
El contraste con el snapshot no demuestra por sí mismo ausencia de revisiones
históricas: solo establece compatibilidad con los datos congelados del proyecto.

## Inventario remoto y contraste acotado

Los 48 ZIP mensuales aggTrades responden a HEAD. Sus Content-Length suman
**38.316.175.397 bytes (38,32 GB / 35,68 GiB)** comprimidos. No se descargaron.
Existencia HTTP no garantiza cobertura interna ni ausencia de huecos.

Dos días prefijados por calendario, sin elegir por rendimiento:

| Día | Registros aggTrades | ZIP | CSV descomprimido | Minutos cotejados |
|---|---:|---:|---:|---:|
| 2020-01-01 | 182.984 | 2.945.680 bytes | 14.552.346 bytes | 1.440 |
| 2023-01-01 | 2.481.087 | 35.828.847 bytes | 207.194.413 bytes | 1.440 |

Ambos ZIP verifican su CHECKSUM. IDs agregados únicos, ordenados y sin saltos
en cada muestra. Se suman volumen base, quote, taker-buy base y taker-buy
quote por minuto: **2.880/2.880 minutos coinciden en los cuatro campos**,
con rtol=1e-9 y atol=1e-6. La mayor diferencia observada es <1e-9 USDT.
No extrapolar esta comprobación de dos días a todo aggTrades ni estimar el
CSV total con un factor fijo: su tamaño no se ha inventariado descomprimido.

## Contrato temporal propuesto para preparar datos

Para una decisión a t sobre rejilla 15m, usar el agregado completo de
[t−30min,t−15min), dejando una barra de margen tras su cierre. Esto equivale
a exigir cierre<t sin arrastrar una barra antigua cuando falta la esperada.
El margen es una hipótesis operativa, no evidencia de entrega histórica.
No procede del supuesto +48h de SP500 ni permite usar el ZIP mensual como
si hubiera estado publicado en tiempo real. Debe separarse instante del
evento, disponibilidad asumida y fecha de descarga.

| Fold | Barras de ejecución | Con agregado elegible | Cobertura |
|---|---:|---:|---:|
| 2022 H1 | 17.376 | 17.376 | 100% |
| 2022 H2 | 17.664 | 17.664 | 100% |
| 2023 H1 | 17.370 | 17.368 | 99,9885% |
| 2023 H2 | 17.664 | 17.664 | 100% |

Esta es cobertura sobre todas las barras, no sobre filas finales de train
o predicción ni sobre ventanas largas. Recalcularla para cualquier feature
con warmup y para el control emparejado antes de entrenar.

Dos magnitudes candidatas para preparación, sin escoger por rentabilidad:
`imbalance_base=(2*taker_buy_base−volume)/volume`, y su agregado de una hora
usando sumas de volumen, no media simple de ratios. Volumen cero: valor
ausente, nunca división por cero ni confundirlo con equilibrio negociador.
No implementar aún un modelo ni combinar este flujo con SP500 o funding.

## Validación y siguiente paso

Script: [audit_aggressor_flow.py](../scripts/audit_aggressor_flow.py).
Dos tests específicos validan cuarentena de datos inválidos, conservación
del flujo y límites temporales. Lecturas raw acotadas explícitamente a 48 meses.
Artifacts: `data/external/aggressor-flow-audit-20261008-complete/`.
El intento HEAD inicial activó el límite de tamaño de descarga de curl;
se conserva su JSON y se repitió HEAD sin ese límite, sin descargar cuerpos.

Siguiente entregable: dataset inmutable de flujo 15m procedente de los ZIP
locales, con manifiesto, pruebas temporales y cobertura emparejada. Antes
de evaluar rentabilidad deberá existir protocolo propio con hipótesis,
control, política, supuestos de disponibilidad y regla de parada.
Se mantiene el criterio y todos los rechazos anteriores. Esta auditoría
no autoriza promoción, apertura del test ni ejecución real.
