# Auditoría acotada de carry BTC — precios disponibles, ejecución no acreditada

Fecha: 2026-10-28. El usuario autorizó ampliar la investigación a spot más
futuros de cobertura. Esta autorización no implica operar, abrir cuentas,
usar claves ni cambiar el benchmark. La familia de 19 iteraciones sigue cerrada.

**Veredicto: no apto todavía para un backtest histórico causal de carry.**
La muestra de precios pasa; faltan evidencias esenciales de reglas y ejecución.
No se concluye que carry no sea rentable ni que los datos faltantes no existan.
Se cierra esta auditoría con alcance limitado, sin construir un simulador.

## Alcance fijado sin mirar rentabilidad

Una sola fuente: archivo público Binance, compatible con el proveedor existente.
BTCUSDT spot y futuro individual USD-M `BTCUSDT_220325`, sin series continuas,
perpetuos, contratos inversos ni cambio de exchange tras ver el resultado.
Día de muestra: 2022-01-03, primer lunes del año de desarrollo; resolución 15m.
La fecha y los cuatro recursos se fijaron en el script antes de descargarlos.
No se calcularon diferenciales, retornos, señales, Sharpe ni curvas de equity.

Se consultaron también documentación oficial y anuncios históricos, sin evaluar
rendimientos de 2024 o del test 2025–2026. Las páginas actuales pueden contener
ejemplos recientes de API; no se descargaron series de esos periodos.

## Comprobación ejecutada

| Archivo | Filas esperadas | Filas válidas | Huecos | SHA256 del proveedor |
|---|---:|---:|---:|---|
| Spot BTCUSDT klines | 96 | 96 | 0 | Coincide |
| BTCUSDT_220325 klines | 96 | 96 | 0 | Coincide |
| BTCUSDT_220325 markPriceKlines | 96 | 96 | 0 | Coincide |
| BTCUSDT indexPriceKlines | 96 | 96 | 0 | Coincide |

Cuatro ZIP y cuatro CHECKSUM: ocho respuestas HTTP 200, 17.734 bytes recibidos.
Los cuatro índices temporales son idénticos, únicos y ordenados. Se verificaron
12 columnas, OHLC positivos finitos y coherentes, límites del día y cierres a
open+15m−1ms. No se rellenaron huecos ni transformaron unidades a posteriori.
Los volúmenes no se utilizaron para inferir profundidad o fills.

El [repositorio oficial](https://github.com/binance/binance-public-data)
documenta archivos diarios/mensuales y formato de klines; sus
[herramientas](https://github.com/binance/binance-public-data/blob/master/python/README.md)
incluyen mark/index. La muestra acredita acceso y esquema de un día, no cobertura
completa de contratos o folds. El checksum acredita integridad del snapshot,
no publicación histórica sin revisiones ni disponibilidad de un precio ejecutable.

## Matriz de viabilidad

| Requisito | Estado | Evidencia / límite |
|---|---|---|
| Familia de instrumento USDT con vencimiento | Sí, documentada | Anuncio histórico de lanzamiento; no equivale al historial íntegro del contrato elegido |
| Cuatro series en muestra | Sí | 384 barras validadas, cuatro índices coincidentes |
| Cobertura de todos los contratos/folds | Desconocido | No se enumeró ni descargó histórico masivo |
| Alta/baja y especificaciones vigentes por contrato | Parcial | Nombre/archivo y documentación de familia; falta registro versionado completo |
| Margen inicial, mantenimiento y cambios históricos | No acreditado | Endpoint actual de cuenta y anuncios parciales; no una secuencia completa |
| Comisiones de ambas posiciones y liquidación históricas | No acreditado | No se verificó una tabla histórica aplicable al contrato y condiciones de cuenta |
| Precio de liquidación oficial del contrato | No acreditado | API documentada, sin selector temporal documentado para acotar la consulta |
| Ejecución y liquidez de las dos posiciones | No acreditado | OHLC no demuestra spreads, profundidad, simultaneidad ni precios de fill |
| Coste gratuito de datos | Sí para la muestra | No acreditado para todas las piezas necesarias |
| Acceso operativo personal | Fuera de alcance | Sin consulta de cuenta ni evaluación de elegibilidad del usuario |
| Backtest defendible bajo el protocolo propuesto | No | Hay piezas esenciales sin acreditar |

## Contrato, margen y liquidación: hallazgos documentales

El [anuncio de febrero de 2021](https://www.binance.com/en/support/announcement/detail/ee59b5c8ddf84d6bbbde4ebff7bdfaa0)
describe trimestrales BTCUSDT con collateral USDT y vencimiento fijo. Confirma
que la familia existía antes de 2022; no prueba por sí mismo los filtros,
escalones y condiciones del contrato `220325`. No confundirla con BTCUSD COIN-M.

La [documentación de cuenta](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/account)
marca `leverageBracket` y `commissionRate` como USER_DATA autenticados. Los
parámetros consultados no incluyen selección histórica; el timestamp firma la
petición, no solicita reglas vigentes en una fecha pasada. No se llamaron estos
endpoints ni se buscaron claves locales. Una clave actual no resolvería por sí
sola la reconstrucción histórica.

Hay evidencia fechada de cambios, no ausencia total de documentación: el
[anuncio del 29-12-2022](https://www.binance.com/en/support/announcement/detail/d7dbdde6375349248b983beda3904140)
anuncia cambios de apalancamiento máximo de trimestrales 1230 y advierte que
afectan posiciones existentes. No se trasladan esas condiciones al 220325 ni
se inventa una serie completa a partir de un anuncio.

La [API de mercado](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data)
documenta `delivery-price` por par con tiempo y precio de liquidación en la
respuesta. No muestra un filtro de fecha; no se llamó, para no recuperar por
defecto precios de periodos reservados. La muestra de index 15m tampoco basta
para reconstruir una media de índice por segundo durante la liquidación.

No se encontró en esta búsqueda acotada una tabla histórica completa de costes
y márgenes aplicable. No es una prueba de inexistencia. Se descartó usar guías
de COIN-M, material de terceros o tablas actuales como sustitutos del contrato
USD-M histórico. No se aplicó automáticamente el fee spot del proyecto al futuro.

## Capital y ejecución que un baseline tendría que representar

El esquema mínimo necesita: identificador de contrato y vigencia, multiplicador,
moneda de cotización/garantía/liquidación, filtros de cantidad y precio,
reglas de marginación con fecha efectiva, mark/index, liquidación oficial,
comisiones por evento y una política causal de ejecución de las dos posiciones.
Cada tabla debe registrar fuente, fecha de observación/disponibilidad, fecha
de recepción, hash y tratamiento de faltantes.

La contabilidad debe separar efectivo de spot, efectivo de garantía y reserva;
marcar la deuda/ganancia del futuro y modelar llamadas de margen, liquidación,
transferencias y fallos de una de las órdenes. La garantía no se cuenta dos
veces ni se considera disponible para comprar BTC. La cobertura no prueba que
el capital sea suficiente durante toda la trayectoria.

Una comprobación con OHLC y slippage supuesto podría ser un cálculo exploratorio
condicionado, pero no satisface esta auditoría de ejecución. No se inventa un
spread, retraso entre posiciones o margen «conservador» para declarar cumplido
el requisito. Supuestos alternativos requerirían una decisión explícita y un
protocolo diferente; no se han aplicado aquí.

## Decisión y condiciones exactas para reconsiderar

No construir un backtester de derivados ni lanzar it.20 con esta evidencia.
No descargar años de precios: el cuello de botella identificado es la historia
de reglas y la ejecución, no el acceso al OHLC. No pasar a perpetuos, otra moneda
o venue por inercia. No iniciar una captura continua para resolver un problema
histórico que esa captura no podría acreditar retrospectivamente.

Solo reconsiderar el baseline histórico al aportar: (1) registro aplicable de
especificaciones/márgenes/costes y sus cambios; (2) liquidaciones oficiales
acotadas al desarrollo; (3) evidencia o límites defendibles de ejecución de las
dos posiciones. Entonces auditar cobertura completa y preregistrar el baseline
antes de medir rendimiento. Si no se resuelve, esta vía histórica queda archivada.
Eso no autoriza reemplazar B&H por efectivo ni reabrir los datos reservados.

## Reproducción y trazabilidad

Script: `scripts/audit_carry_sample.py`; fija día, contrato, ocho peticiones
máximas, timeout de 20s y límite de 2 MB por respuesta/miembro descomprimido.
No acepta un rango de fechas, no lee datasets locales ni calcula rentabilidad.

Artefactos: `data/audits/carry-20261028/`: cuatro ZIP, cuatro CHECKSUM,
`requests.json`, `report.json` y manifiesto. Verificación posterior independiente
de hashes y conjunto de archivos: diez archivos del manifiesto correctos.
SHA256 del manifiesto:
`0fbfe2ba9f56c465eb2fbae64f29f19a434ae5a1c2df338741700da8b9d85146`.

Lint/formato y hooks del repositorio comprobados. No se ejecutaron tests del
motor porque no cambió, ni backtests o entrenamientos. Las fuentes externas
se consultaron el 2026-10-28. El informe distingue lo observado en la muestra
de lo documentado y de lo que permanece desconocido.
