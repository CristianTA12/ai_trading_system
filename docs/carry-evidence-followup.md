# Carry BTC — seguimiento de reglas históricas y ejecución

Fecha: 2026-10-28. Continuación autorizada de la [auditoría](carry-data-audit.md).
Contrato fijo `BTCUSDT_220325`. Cero backtests, entrenamientos o nuevas descargas
de precios. Se consultaron inventarios de archivos, índices de capturas web y
documentación. No se accedió a cuentas, claves o datos reservados.

**Resultado: evidencia parcial adicional; el baseline histórico sigue no apto.**
Hay fuentes concretas localizadas para tarifas/margen, pero no una reconstrucción
verificada. No repetir la búsqueda general ni construir el simulador mientras
estas piezas sigan pendientes.

## Qué se ha resuelto parcialmente

La [especificación oficial de trimestrales USDT](https://www.binance.com/en-AE/support/faq/detail/3ae441db4ae740e19af3fe9228eb6619)
describe contratos lineales, denominados y liquidados en USDT, y una comisión
de liquidación equivalente a la taker. Su fecha publicada es 2021-02-03.
Se leyó la versión actualmente servida: esa fecha no acredita que todo el
contenido se mantuviera idéntico desde 2021. No confundir con COIN-M.

El [artículo oficial de costes](https://www.binance.com/en-IN/blog/futures/421499824684902239),
fechado 2021-09-23, menciona tasas iniciales taker 0,04% y maker 0,02%.
Es evidencia histórica orientativa del proveedor, no un registro inmutable
de tarifas del 220325 durante diciembre de 2021 a marzo de 2022. Tampoco
acredita tarifas spot, descuentos personales o ausencia de cambios posteriores.
No se han asignado esas cifras a un backtest.

## Inventario de mercado comprobado

Se consultaron cuatro prefijos del bucket público, con máximo 1.000 claves por
respuesta. Todas las respuestas HTTP 200, sin truncamiento:

| Prefijo | Resultado |
|---|---|
| `data/futures/um/daily/trades/BTCUSDT_220325/` | 184 claves: 92 ZIP diarios y 92 CHECKSUM |
| `data/futures/um/daily/bookTicker/BTCUSDT_220325/` | 0 claves |
| `data/futures/um/daily/bookDepth/BTCUSDT_220325/` | 0 claves |
| `data/spot/daily/bookTicker/BTCUSDT/BTCUSDT-bookTicker-2022-01-03` | 0 claves |

Las fechas de los ZIP de trades son consecutivas del 2021-12-24 al 2022-03-25;
cada ZIP tiene un CHECKSUM listado. Se verificó el inventario, no el contenido
de los 92 archivos. No se infiere la hora exacta de alta o liquidación del
contrato a partir del nombre del primer/último archivo.

Un prefijo vacío demuestra ausencia de claves bajo ese prefijo consultado,
no ausencia global de datos en otros directorios, proveedores o formatos.
No se cambió de fuente para rescatar la prueba. El tape de trades describe
transacciones realizadas, no el bid/ask o capacidad ejecutable disponible
para nuestras órdenes hipotéticas; no acredita ejecución simultánea spot/futuro.

## Capturas históricas localizadas, contenido aún no leído

El índice CDX de Internet Archive se consultó entre 2021-01-01 y 2022-03-25,
con filtro HTTP 200, máximo 100 entradas y agrupación por digest:

| URL original | Entradas con digest distinto devueltas |
|---|---|
| `www.binance.com/en/fee/futureFee` | 5: 2021-04-16, 09-23, 10-08, 10-30, 11-27 |
| `www.binance.com/en/futures/trading-rules/perpetual/leverage-margin` | 2: 2021-12-23 y 2022-03-05 |
| `www.binance.com/en/support/faq/3ae441db4ae740e19af3fe9228eb6619` | 0 en esa URL exacta y rango |

La consulta agrupada no enumera todas las capturas y no demuestra que no
hubiera cambios entre ellas. La ruta de margen contiene `perpetual`: no puede
asumirse que cubra el trimestral elegido sin inspeccionar su contenido y alcance.

Se intentó leer exactamente estas tres capturas, sin seguir redirecciones:

- [Tarifas, 2021-11-27 15:17:13](https://web.archive.org/web/20211127151713id_/https://www.binance.com/en/fee/futureFee).
- [Margen, 2021-12-23 05:22:01](https://web.archive.org/web/20211223052201id_/https://www.binance.com/en/futures/trading-rules/perpetual/leverage-margin).
- [Margen, 2022-03-05 15:02:19](https://web.archive.org/web/20220305150219id_/https://www.binance.com/en/futures/trading-rules/perpetual/leverage-margin).

Las tres respondieron **HTTP 429** con un mensaje de bloqueo por tráfico
automatizado sospechoso. Los cuerpos guardados son mensajes de bloqueo, no las
tablas de Binance. No hubo reintentos automáticos ni intentos de eludir el bloqueo.
La apertura con la herramienta web tampoco pudo acceder a esas capturas.
Por tanto, el índice acredita referencias de archivo, no lectura de sus valores
ni suficiencia de cobertura. No informar este resultado como «no existen snapshots».

## Liquidación: qué sigue sin resolverse

La [documentación del mark trimestral](https://www.binance.com/fr/support/faq/detail/360033525071)
describe el uso del índice durante los últimos 30 minutos. No aporta aquí el
registro de liquidación realizado del contrato 220325. No se sustituyó ese
registro por el último trade, cierre de kline o media de OHLC de índice.
La búsqueda documental no identificó un registro oficial exacto del vencimiento
que pudiera leerse de manera acotada al desarrollo. Se conserva esa limitación.

## Decisión concreta y condiciones de reanudación

No hay evidencia suficiente para ejecutar carry bajo el protocolo actual.
No se declara rechazo económico: no se ha medido su rentabilidad.
El acceso a precios ya no es la pregunta pendiente y no merece otra descarga.

La siguiente revisión solo tendría sentido con nueva evidencia concreta:

1. Contenido recuperado de las capturas localizadas, comprobando fechas, tablas,
   moneda, instrumento y aplicabilidad al trimestral. Aunque se recuperen, dos
   capturas de margen no bastan automáticamente para reconstruir todos los cambios.
2. Registro oficial de liquidación del 220325 o documentación que permita
   reconstruirlo exactamente con datos disponibles, sin consultar el test.
3. Datos de cotizaciones/capacidad o una política de ejecución con límites
   defendibles. El tape por sí solo no resuelve esa condición.

No abrir una nueva búsqueda de algoritmos, otro exchange, perpetuos o un
collector continuo por inercia. Tampoco modificar `risk-return-v1` ni el
benchmark B&H. Un estudio con supuestos simplificados sería otro protocolo
condicionado, no una auditoría histórica aprobada; no se ha autorizado ni ejecutado.

## Trazabilidad

Script: `scripts/audit_carry_evidence.py`. Modo normal: siete consultas acotadas;
modo `--snapshots`: tres lecturas de capturas exactas. No calcula retornos ni
lee datasets locales. Máximo tres conexiones, timeout 20s, límite 1 MB por
respuesta y sin seguimiento de redirecciones en la versión final.

- `data/audits/carry-evidence-20261028/`: siete respuestas y reporte; ocho archivos
  del manifiesto verificados por SHA256 y conjunto exacto.
- `data/audits/carry-snapshots-20261028/`: tres respuestas 429 y reporte; cuatro
  archivos del manifiesto verificados.
- Manifiestos SHA256 respectivamente:
  `a16cfea1fe3d649bf96f1ac751da9d945089a4d6046c845d78940ca3e42d64e7` y
  `8c3abc432b46656b3a274f87653290a22eb2ab12502014faba165cba00cdf800`.

En dos registros de la primera tanda el reloj de pared retrocedió entre
petición y recepción. Se preservaron los valores originales; no se usan para
inferir latencia ni fecha histórica de publicación. La segunda tanda añade
duración monotónica y bandera de retroceso, sin alterar ni repetir la primera.
Las fechas CDX son metadatos del servicio, independientes de ese reloj local.
Lint, formato y hooks comprobados; no se modificó el motor ni ejecutó su suite.
