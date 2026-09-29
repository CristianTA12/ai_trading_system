# Auditoría de viabilidad: funding y open interest de BTCUSDT

Fecha de consulta: 2026-09-29. Mercado: perpetuo USDⓈ-M BTCUSDT de Binance;
las operaciones del proyecto seguirían siendo spot. Este informe evalúa datos,
no estrategias. No se entrena ni se calcula rendimiento predictivo o de trading.
No se descargan observaciones de 2024 ni del test 2025–2026.

## Conclusión

**Funding: viable con limitaciones para investigación. OI: no viable bajo el
requisito actual de cobertura del 95% del train original.** El paquete conjunto
funding + OI hereda la limitación de OI. Poder emparejar los brazos no recupera
la historia que falta.

La disponibilidad temporal histórica exacta queda **sin demostrar** para ambos.
El desfase propuesto abajo es una hipótesis conservadora reproducible, no un
SLA de Binance ni una prueba de ausencia de leakage. Si el criterio exige probar
sin ambigüedad el instante original de publicación, esa casilla no queda aprobada.

## Fuentes y profundidad histórica

Se consultaron fuentes oficiales y los CSV originales, no tablas de terceros.

| Dato | Ruta comprobada | Inicio observado | Resolución |
|---|---|---|---|
| Funding bulk | `data/futures/um/monthly/fundingRate/BTCUSDT/` | 2020-01-01 00:00 UTC | 8 horas en todos los registros auditados |
| Funding REST | `/fapi/v1/fundingRate` | Primera respuesta desde septiembre de 2019: 2019-09-10 08:00 UTC | Eventos de liquidación |
| OI bulk | `data/futures/um/daily/metrics/BTCUSDT/` | 2020-09-01 00:00 UTC | Snapshots nominales de 5 minutos |

Los listados oficiales de [funding](https://data.binance.vision/?prefix=data/futures/um/monthly/fundingRate/BTCUSDT/)
y [metrics](https://data.binance.vision/?prefix=data/futures/um/daily/metrics/BTCUSDT/)
se guardaron como XML. `monthly/openInterest/BTCUSDT/` devolvió un listado vacío;
OI se obtiene de `metrics`, junto a otras métricas que esta auditoría no propone
incorporar automáticamente. Los ZIP y sus `.CHECKSUM` se verificaron con SHA-256.

El endpoint de funding admite hasta 1.000 registros y comparte un límite de
500 consultas por cinco minutos/IP con `fundingInfo`. OI histórico admite hasta
500 registros, períodos desde 5m/15m y conserva solo el último mes, con límite de
1.000 consultas por cinco minutos/IP. `openInterest` devuelve un snapshot actual,
no una serie histórica. La consulta OI de 2021 devolvió HTTP 400; no permite
reconstruir nuestros folds. [Documentación REST oficial](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data).

## Cobertura real y calidad del snapshot

Se descargaron y verificaron **1.265 ZIP**, unos **14,43 MB comprimidos** más
checksums. Los 48 meses de funding y los 1.217 días de metrics disponibles desde
septiembre de 2020 hasta diciembre de 2023 están presentes. La presencia de un
archivo diario no garantiza que todas sus observaciones sean válidas.

| Medida, 2020–2023 | Funding | OI |
|---|---:|---:|
| Filas originales | 4.383 | 425.247 |
| Duplicados exactos eliminados | 0 | 75.255 |
| Timestamps con valores en conflicto | 0 | 0 |
| Observaciones excluidas por valor inválido | 0 | 155 |
| Observaciones únicas válidas | 4.383 | 349.837 |
| Intervalos nominales ausentes desde el inicio de la serie | 0 | 659 |
| Mayor separación entre observaciones válidas | 8h nominales | 9h45m |

Los 155 registros OI excluidos contienen cantidad o valor no positivo: 143 tienen
cantidad no positiva y los 155 valor no positivo. No se sustituyen por cero. Tras
deduplicar hay 504 slots de 5m sin observación y otros 155 excluidos: total 659.
No aparecieron conflictos entre valores de OI para un mismo timestamp. La regla
de auditoría excluye todo timestamp conflictivo si apareciera, en vez de escoger
una versión arbitraria.

Se detectaron 165 separaciones mayores de 5 minutos entre snapshots OI válidos.
Las mayores fueron:

| Observación anterior UTC | Observación siguiente UTC | Separación |
|---|---|---:|
| 2022-03-07 15:25 | 2022-03-08 01:10 | 9h45m |
| 2021-02-19 20:00 | 2021-02-20 01:20 | 5h20m |
| 2021-06-22 18:25 | 2021-06-22 22:50 | 4h25m |

Los huecos son de esta versión del archivo, no una reconstrucción demostrada de
incidencias en la API en tiempo real. Para funding, detectar slots nominales usa
el horario de 8h; **la alineación causal conserva el timestamp completo**.

### Efecto sobre los cuatro folds existentes

Cobertura calculada con el desfase y caducidad definidos en la sección siguiente.
Se replica la purga del proyecto (`timestamp + 15min < frontera`) sobre las filas
de v1. No se calculan labels, predicciones ni métricas de estrategia.

| Fold | Filas train v1 | Train con funding | Train con OI o ambos | Cobertura OI | Pérdida train |
|---|---:|---:|---:|---:|---:|
| 2022 H1 | 69.221 | 69.221 (100%) | 46.052 | 66,53% | 33,47% |
| 2022 H2 | 86.597 | 86.597 (100%) | 63.390 | 73,20% | 26,80% |
| 2023 H1 | 104.261 | 104.261 (100%) | 81.054 | 77,74% | 22,26% |
| 2023 H2 | 121.581 | 121.581 (100%) | 98.371 | 80,91% | 19,09% |

| Fold | Filas originales del semestre | Funding | OI o ambos |
|---|---:|---:|---:|
| 2022 H1 | 17.375 | 17.375 (100%) | 17.337 (99,7813%) |
| 2022 H2 | 17.663 | 17.663 (100%) | 17.663 (100%) |
| 2023 H1 | 17.319 | 17.319 (100%) | 17.316 (99,9827%) |
| 2023 H2 | 17.663 | 17.663 (100%) | 17.662 (99,9943%) |

Sobre toda la rejilla calendario solicitada, **2020-01-01 a 2023-07-01 exclusivo**,
la disponibilidad bajo la hipótesis temporal es **99,9984% funding** y **80,7728% OI**.
Las dos primeras barras calendario carecen de funding anterior elegible en el bulk;
el warmup original de v1 ya las excluye, de ahí el 100% sobre las filas reales.
Estos porcentajes son para las variables de nivel; deltas o medias pueden reducirlos.

| Criterio de la auditoría | Funding | OI |
|---|---|---|
| Cobertura >=95% | Cumple | No cumple |
| Resolución adecuada | 8h, contexto lento; valor económico por demostrar | 5m, cumple resolución |
| Disponibilidad histórica inequívoca | No demostrada; desfase explícito como supuesto | No demostrada; desfase explícito como supuesto |
| Descarga factible | Sí, bulk público | Sí, bulk público |
| Control emparejado | Sí, sin pérdida de filas de nivel v1 | Sí, con pérdida importante de train |
| Recomendación | Viable con limitaciones, sin aprobación temporal incondicional | No viable bajo el criterio actual |

## Publicación, revisiones y leakage

Hay que separar tres tiempos: evento económico, disponibilidad para el cliente
y publicación/revisión del archivo histórico. Ninguno puede sustituirse
automáticamente por otro.

- Funding contiene `calc_time`, `funding_interval_hours` y `last_funding_rate`.
  Son tasas liquidadas. No usaremos la tasa de las 08:00 para decisiones anteriores
  a ese evento. La pantalla de estimación en tiempo real no convierte la tasa
  final en un dato conocido de antemano. Binance distingue vistas de tasa en tiempo
  real e histórica y describe la acumulación previa a la liquidación.
  [Explicación oficial](https://www.binance.com/en/support/faq/detail/360033525031).
- No se ha encontrado un archivo histórico de estimaciones sucesivas del próximo
  funding con sus instantes de recepción. El histórico final no permite reconstruirlo.
- OI contiene `create_time`, `symbol`, `sum_open_interest` y
  `sum_open_interest_value`, además de ratios ajenos al alcance. El nombre
  `create_time` no acredita el instante de publicación. La API describe su
  `timestamp` como fin de período, pero no ofrece una latencia máxima ni demuestra
  la equivalencia exacta con la disponibilidad del CSV.
- El primer ZIP mensual de funding tiene `LastModified` de 2023-05-09; el primer
  ZIP diario de OI, de 2026-03-18. Esto acredita la versión actual del archivo,
  **no** demuestra que el dato económico fuera desconocido hasta esas fechas ni
  que la versión actual coincida con la que se habría recibido originalmente.
- Binance advierte que los archivos históricos pueden actualizarse. Los diarios
  se publican al día siguiente y los mensuales posteriormente; no son un feed
  para ejecutar en la misma vela. Los checksums garantizan integridad del snapshot
  descargado, no disponibilidad histórica punto a punto.
  [Repositorio oficial de datos públicos](https://github.com/binance/binance-public-data#updates).

La regla operacional propuesta, **todavía no preregistrada para un experimento**, es:

1. Conservar UTC y precisión original, incluidos milisegundos; no redondear hacia
   atrás la hora de disponibilidad. Funding observado tiene pequeños desplazamientos
   de milisegundos respecto al horario nominal.
2. Para esta medición de cobertura, asumir `available_at = event_time + 15min` y
   exigir `available_at < decision_at`. Por ejemplo, un evento a las 08:00 se
   incorpora por primera vez a las 08:30 en una rejilla de 15 minutos.
3. Hacer un join as-of hacia atrás. Caducar funding después de 8h desde
   `available_at`; OI después de 15min desde `available_at`. Esto limita la edad
   total a 8h15m y 30m respectivamente. No rellenar huecos indefinidamente ni
   hacer backfill. Dato ausente implica ausencia de la feature.
4. OI es un stock: seleccionar el último snapshot elegible, **no sumar** los tres
   registros de 5m para construir 15m. Las diferencias requieren historia causal
   suficiente y deben reiniciarse cuando falte cobertura.
5. En captura futura, guardar `event_time`, `received_at`, fuente, versión y
   checksum. La latencia observada hoy no prueba la de 2020–2023. Un estudio con
   datos revisados debe declararse como tal; retrasar la serie no elimina revisiones.

No se presupone que funding sea siempre de 8h para cualquier contrato o fecha.
Binance cambió ciertos contratos a 4h en octubre de 2023; BTCUSDT no figura en
esa lista. En nuestro rango la cadencia se comprobó directamente en los CSV.
[Aviso oficial de 2023](https://www.binance.com/en/support/announcement/detail/98d6b24d3e5c4f84a8ed04087997d8d0).

## Descarga e integración

Las descargas realizadas fueron públicas, sin claves ni pago. El histórico
2020–2023 requiere 48 ZIP mensuales de funding y 1.217 ZIP diarios de metrics,
más sus checksums. El equivalente funding por REST serían al menos cinco páginas
de 1.000 eventos; para 2020–2026 completo, unas ocho si se mantuviera 8h. Es una
estimación, no una descarga de los años reservados. OI antiguo exige bulk: más
páginas REST no evitan la retención de un mes.

El downloader actual está especializado en klines spot de doce columnas. Se
pueden reutilizar su descarga acotada, caché y verificación, pero **no** el parser,
validador de velas ni la ingesta OHLCV. Una extensión debe separar esquema y
claves por mercado/dataset, conservar milisegundos, controlar duplicados/conflictos
y escribir Parquet inmutable o tablas propias de derivados. Esta auditoría no
modifica el downloader ni escribe en TimescaleDB.

Se creó `scripts/audit_derivatives.py` para reproducir la inspección con cuatro
descargas concurrentes, caché local y CSV/JSON de evidencia. No extrae miles de CSV
sueltos al HDD: conserva los ZIP y genera un Parquet consolidado por tipo.
Los tres tests de alineación verifican frontera estricta, expiración y ausencia
de uso de datos futuros, incluida precisión de milisegundos.

## Control emparejado y posibles features

Con funding, conservar únicamente filas donde existan v1, label y funding válido
permite emparejar candidato/control con el mismo train y fechas de predicción.
Las filas necesarias para deltas/medias añaden su propio warmup y deben contarse
antes de fijar el experimento. Mantener las velas de ejecución del semestre completo
y pasar a efectivo si falta señal; no borrar fechas de la curva.

Con OI, excluir enero–agosto de 2020 elimina ocho meses, no nueve. Ambos brazos
seguirían siendo emparejables, pero bajo otro train sustancialmente recortado.
Rellenar esa ausencia con cero o con datos futuros no es válido. Permitir NaN en
XGBoost no convierte una cobertura inferior al 95% en cumplimiento; además,
la ausencia estructural puede identificar una época. Cambiar rango, política de
ausencias o proveedor exige un protocolo nuevo.

Features candidatas para una discusión posterior, no implementadas:

- `funding_last_settled`: última tasa liquidada elegible. Hipótesis: contexto lento
  de demanda de apalancamiento, sin afirmar poder predictivo para 15m.
- `funding_delta_event`: diferencia entre las dos últimas liquidaciones elegibles.
- `funding_mean_3_events`: media de tres eventos distintos; no media de una serie
  repetida artificialmente en cada barra.
- Solo si se resuelve la cobertura de OI: `oi_change_1h` sobre cantidad y
  `oi_relative_7d` frente a una media retrospectiva. El OI expresado en USDT mezcla
  cambios de posiciones con cambios de precio; se deben distinguir cantidad y valor.

Recomendación: discutir primero un bloque pequeño de funding, aceptando explícitamente
la limitación de disponibilidad histórica si se decide investigar. OI no pasa el
criterio de cobertura acordado para este diseño. No se ha fijado una iteración 11.

## Reproducibilidad

```bash
python scripts/audit_derivatives.py \
  --output data/audits/derivatives-20260929 \
  --dataset data/processed/btc-usdt-spot-15m-v1-2020-01-2026-08-20260925T164411092396Z
```

La evidencia local está en `data/audits/derivatives-20260929/`: listados XML,
ZIP/CHECKSUM, manifiestos de filas/hashes/versiones, observaciones, huecos y cobertura.
`api_probes.json` conserva consultas puntuales y respuestas REST. El cálculo de
folds lee únicamente timestamps/split anteriores a 2024, sin outcomes ni modelos.
