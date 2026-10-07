# Auditoría macro — fuentes, disponibilidad y revisiones

**Estado posterior a it.16 (2026-10-07):** salida por DOWN rechazada 2/5.
Se cierra la prueba de persistencia; pendiente decisión de arquitectura.
[Resultados it.16](iteration-16-results.md). Los supuestos y las limitaciones
temporales de las fuentes no han cambiado.

**Cierre 2026-10-07:** la excepción exploratoria SP500 aceptada por el usuario
se ejecutó en [it.15](iteration-15-results.md): candidato 1/5, control 2/5,
rechazo por consistencia. Mejora económica condicional sin promoción.
Siguiente etapa: revisión de arquitectura de Fase F; test reservado intacto.
La [revisión posterior](architecture-review-post-15.md) ya está documentada:
propone aislar la persistencia de posición con los modelos it.15 congelados.
La propuesta no cambia las conclusiones temporales de esta auditoría.

Fecha: 2026-10-06. Fase E, posterior al rechazo de it.14.
**Actualización: reconstrucción diaria VIX terminada y auditada: 1.522 snapshots,
30 excluidos por observaciones posteriores a su vintage y cobertura condicional
2023 H1 del 93,34%. Ninguna fuente está aprobada para entrenar it.15.**
El [informe de reconstrucción VIX](vix-vintage-reconstruction.md) recoge la
verificación independiente. El [contraste con la API oficial](vix-api-crosscheck.md)
ya terminó: 37 vintages consultadas, las 30 anomalías reproducidas y ninguna
diferencia numérica con el gráfico. La credencial funciona; el bloqueo es temporal.
El [contraste Cboe](vix-cboe-crosscheck.md) también confirma los 1.059 cierres
y las doce fechas anómalas. VIX queda no aprobado con este protocolo; el
[contraste S&P 500 por API](sp500-api-audit.md) también terminó: el servidor
rechaza las vintages porque SP500 no existe en ALFRED; el snapshot actual sí
funciona. Antes de it.15 queda decidir entre evidencia temporal de otra fuente
y un experimento expresamente condicionado a supuestos. **Decisión posterior
del usuario: preparar SP500 bajo los supuestos de snapshot representativo y
disponibilidad +48 h.** El [preregistro it.15](iteration-15-protocol.md) fija
la excepción exploratoria; cobertura condicional 100% en todos los folds,
sin convertirla en prueba temporal ni abrir el test.

La referencia experimental sigue siendo it.13: 4h, clases ±100 pb, holding 4h,
gate SMA50>SMA200. It.14 no reemplaza esa referencia. Esta auditoría no entrena,
no ejecuta backtests y no abre datos BTC de 2024 ni test 2025–2026.

## Actualización cuantitativa — acceso resuelto

El reintento con `curl.exe` de Windows obtuvo HTTP 200 para las tres series,
manteniendo HTTPS con verificación de certificados y tiempos de espera acotados.
No fue necesario desactivar TLS ni crear una cuenta. El fallo anterior no
permite concluir si la causa fue transitoria, del cliente o de otra capa de red.
El auditor admite ahora transporte `curl`, incluido el ejecutable Windows desde WSL.

Raw y checksums en `data/external/macro-audit-20261006-retry/`.
Todos los snapshots contienen 1.086 filas laborables entre 2019-11-01 y
2023-12-29; no incluyen observaciones de 2024–2026. Fechas únicas, ordenadas,
valores no nulos positivos y finitos. Los nulos originales se conservan.

| Serie | Valores no nulos | Nulos | Mayor intervalo entre valores | 2022 H1 | 2022 H2 | 2023 H1 | 2023 H2 |
|---|---:|---:|---:|---:|---:|---:|---:|
| SP500 | 1.047 | 39 | 4 días | 124 | 127 | 124 | 126 |
| VIXCLS | 1.059 | 27 | 4 días | 126 | 130 | 128 | 129 |
| DTWEXBGS | 1.037 | 49 | 5 días | 125 | 125 | 125 | 124 |

Son conteos de observaciones, **no porcentajes de cobertura causal sobre barras
BTC**. Las ausencias incluyen festivos; el auditor no las confunde con fallos
de datos. Existen doce fechas con VIX informado y S&P ausente, todas con VIX
distinto del valor anterior. Se conservan en `vix_without_sp500.csv`: no se
eliminan ni se etiquetan automáticamente como forward-fill. Esta evidencia
obliga a verificar el calendario específico VIX, no reutilizar el de acciones.

### Versiones históricas obtenidas sin API key

El endpoint público de gráficos ALFRED respondió a solicitudes con
`vintage_date` explícita. Se exigió encabezado `SERIE_YYYYMMDD`, fechas dentro
de la ventana auditada y ninguna observación posterior a la vintage. Los
ficheros y comparaciones quedan conservados; la prueba no se basa solo en HTTP 200.
ALFRED describe las vintages como datos existentes en una fecha histórica.
[Ayuda oficial](https://alfred.stlouisfed.org/help/downloaddata).

| Serie / vintage solicitada | Valores comparables con snapshot actual | Valores distintos |
|---|---:|---:|
| VIXCLS / 2019-12-31 | 41 | 0 |
| VIXCLS / 2020-12-31 | 294 | 0 |
| VIXCLS / 2021-12-31 | 546 | 0 |
| VIXCLS / 2022-12-31 | 802 | 0 |
| VIXCLS / 2023-12-31 | 1.059 | 0 |
| DTWEXBGS / 2023-01-10 | 792 | **791** |

También se conserva una muestra VIX del 2023-01-10. Las muestras VIX anuales
no prueban ausencia de revisiones entre esas fechas ni disponibilidad intradía.
No se suman sus tamaños como muestras independientes: sus períodos se solapan.
Para dólar, la máxima diferencia absoluta es **0,206 puntos de índice**, no
20,6% ni 20,6 pb de retorno. Su última observación disponible en esa vintage
es 2023-01-06. Hay evidencia directa de que el snapshot actual incorpora cambios
posteriores: aplicar solo un lag no reconstruye la versión histórica.

La página ALFRED de SP500 devuelve HTTP 404 y la petición de vintage al gráfico
falla. Esto documenta que **esa vía no ha suministrado vintages SP500**, no que
ninguna fuente del mundo las tenga ni que la serie sea necesariamente revisada.

### Decisión actual y trabajo restante

- **Cerrar el diagnóstico VIX con fuente no aprobada.** Cboe confirma los
  valores y documenta actividad GTH en el festivo estudiado, pero no acredita
  su presencia en una vintage anterior. Se mantienen las 30 cuarentenas.
- **S&P 500 pendiente de otra evidencia temporal o de un supuesto explícito.**
  El raw ya existe; el problema restante es histórico/temporal, no conectividad.
  La API autenticada confirmó que SP500 no existe en ALFRED: cinco respuestas
  HTTP 400 y control actual HTTP 200. No repetir extracción diaria por esta vía.
- **Mantener DTWEXBGS fuera de la primera propuesta.** La revisión cuantificada
  refuerza la necesidad de modelar vintages y publicación semanal antes de usarlo.
- No aprobar it.15. Ya se midió cobertura condicional sobre las filas congeladas
  de it.13: 2023 H1 alcanza el 93,34%. Los artifacts son exclusivamente diagnósticos.

Auditor adicional: [audit_macro_vintages.py](../scripts/audit_macro_vintages.py).
**16 tests dirigidos pasan** entre ambos auditores; incluyen detección de
parámetro vintage ignorado, fechas futuras, revisiones y errores HTTP.

```bash
# Transporte que ha funcionado, invocado desde el entorno Python WSL:
python scripts/audit_macro_sources.py data/external/<carpeta-nueva> --fetch \
  --transport curl --curl-executable /mnt/c/Windows/System32/curl.exe
python -m scripts.audit_macro_vintages data/external/macro-audit-20261006-retry
pytest tests/test_macro_source_audit.py tests/test_macro_vintages.py -q
```

Los apartados siguientes conservan el razonamiento documental y el historial
del primer intento; su bloqueo de descarga quedó resuelto en esta actualización.

## Evaluación documental inicial por fuente

| Propuesta | Fuente examinada | Cobertura documental | Disponibilidad histórica | Decisión |
|---|---|---|---|---|
| S&P 500 | FRED `SP500`, origen S&P DJI | Ventana móvil de 10 años; debería incluir 2019–2023 hoy | Fecha de observación y cierre no prueban hora de entrega por FRED | Candidato, pendiente raw/vintages/latencia |
| VIX | FRED `VIXCLS`, origen Cboe; histórico oficial Cboe | Cboe anuncia cierres desde 1990 | El cierre del índice no es la publicación del CSV o actualización de FRED | Candidato, pendiente raw/vintages/latencia |
| Dólar amplio | FRED `DTWEXBGS`, origen Fed H.10 | Serie diaria documentada; cobertura de nuestros folds no medida | Publicación semanal y revisiones históricas | Excluir de la primera receta propuesta hasta disponer de versiones históricas y releases |
| DXY | ICE U.S. Dollar Index | Instrumento distinto de `DTWEXBGS` | No se ha validado aquí una fuente gratuita con histórico y disponibilidad suficientes | No sustituir silenciosamente por dólar amplio |

No confundir disponibilidad anunciada de histórico con cobertura medida. No
hay porcentajes por fold en este informe porque no se recibieron los raw.

## 1. S&P 500: cierre, proveedor y ventana móvil

FRED define `SP500` como índice de precios al cierre, sin dividendos, con
histórico limitado a diez años. El cierre habitual es a las 16:00 Eastern,
con excepciones por calendario. La ventana es móvil: conservar el raw y su
checksum será necesario para reproducibilidad futura.
[Ficha oficial SP500](https://fred.stlouisfed.org/series/SP500).

Ese horario describe el índice, no la hora en que FRED entregó cada observación
histórica. **No se autoriza asignar `available_at = fecha a las 00:00 UTC`,
ni `cierre + 15 min` sin evidencia o un supuesto explícitamente aprobado.**
Los metadatos de actualización actuales no reconstruyen la latencia de 2022.

## 2. VIX: el horario del índice tampoco fecha el fichero

Cboe ofrece cierres diarios desde 1990. El índice VIX spot no es el futuro VIX
ni su precio de liquidación. Debe conservarse esta identidad al elegir la serie.
[Histórico oficial Cboe](https://www.cboe.com/tradable_products/vix/vix_historical_data).

La metodología consultada distingue sesiones y sitúa el final regular de
difusión a las 15:15 Central, equivalente a las 16:15 Eastern en esas sesiones.
No se debe usar sin más el cierre de las acciones a las 16:00 para fechar VIX;
hay que verificar también el calendario histórico y las sesiones especiales.
[Metodología Cboe](https://cdn.cboe.com/resources/vix/VIX_Methodology.pdf).

La ficha FRED `VIXCLS` confirma frecuencia diaria de cierre, pero no aporta
timestamps originales por observación.
[VIXCLS](https://fred.stlouisfed.org/series/VIXCLS).
Como ejemplo de que el canal importa, el producto Cboe Main Channel End-of-Day
Summary se distribuye después de la apertura del siguiente día de negociación.
Es **otro producto**: no se extrapola ese plazo al CSV gratuito ni a FRED.
[Descripción del producto Cboe](https://datashop.cboe.com/main-channel-end-of-day-summary).

## 3. DXY y DTWEXBGS no son intercambiables

DXY de ICE combina seis monedas con ponderaciones específicas; el euro pesa
57,6%. No es el índice amplio de la Reserva Federal.
[Descripción de ICE](https://www.ice.com/insights/indexation-and-etfs/managing-us-dollar-risk-in-uncertain_times).
FRED identifica `DTWEXBGS` como Nominal Broad U.S. Dollar Index, release H.10.
Si se empleara, su nombre y su hipótesis deberían reflejar ese índice amplio,
nunca llamarlo `dxy_return_1d`.
[Ficha DTWEXBGS](https://fred.stlouisfed.org/series/DTWEXBGS).

H.10 publica los datos diarios de la semana laboral anterior **los lunes a
las 16:15**, desplazándose al siguiente día laborable si el lunes es festivo
federal. Una fecha diaria de observación no implica disponibilidad diaria.
Se necesita reconstruir el calendario de releases y su zona horaria antes
de convertirlo a UTC; no basta desplazar cada observación una barra.
[Calendario oficial H.10](https://www.federalreserve.gov/releases/h10/).

La Fed también indica que actualiza/revisa las ponderaciones anualmente y que
eso puede modificar valores históricos. Un lag semanal aplicado al snapshot
actual **no elimina** ese sesgo de revisión.
[Notas oficiales de los índices](https://www.federalreserve.gov/Releases/h10/summary/default.htm).

## 4. Snapshots actuales frente a información conocida entonces

La API de FRED usa por defecto el período real-time de hoy: representa lo que
hoy se conoce del pasado. Para reconstrucción histórica hay que fijar períodos
real-time y recuperar versiones, no solo acotar fechas de observación.
[Documentación real-time](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

ALFRED archiva versiones; sus fechas de release pueden proceder de la fuente,
del proveedor o, si no se conoce la publicación, de la primera disponibilidad
en FRED. La incorporación suele ocurrir dentro de un día laborable, pero esto
no es una garantía uniforme ni una hora intradía. Hay que verificar qué cubre
el archivo para cada serie y cada tramo.
[Ayuda ALFRED](https://alfred.stlouisfed.org/help).

Ruta preferente: investigar versiones ALFRED y su cobertura, sin asumir que
`vintage_date` equivale a medianoche UTC de disponibilidad. Si solo se conoce
una fecha, usarla requiere una convención conservadora documentada, con zona
horaria y tratamiento de la entrega del proveedor. Si queda incertidumbre,
registrarla como supuesto; no declarar causalidad histórica demostrada.
La API oficial requiere clave registrada; no se crea una cuenta ni se configura
ninguna credencial en esta tarea.
[API observations](https://fred.stlouisfed.org/docs/api/fred/series_observations.html),
[API key](https://fred.stlouisfed.org/docs/api/api_key.html).

## 5. Primer intento: descargas fallidas (resuelto arriba)

Se solicitaron `SP500`, `VIXCLS` y `DTWEXBGS` al endpoint CSV de FRED, acotando
`cosd=2019-11-01&coed=2023-12-31`. Noviembre–diciembre de 2019 se reservarían
para warmup; no se pidió ampliar entrenamiento BTC ni evaluar períodos posteriores.

**Las tres peticiones desde WSL terminaron en timeout.** Una comprobación de
SP500 desde PowerShell, también fuera del sandbox, terminó en timeout. La
herramienta web permitió consultar documentación, pero no obtener ese CSV.
Esto demuestra un fallo de acceso en esta sesión, no inexistencia de datos,
prohibición del proveedor ni una causa de red determinada.

Artifacts locales: `data/external/macro-audit-20261006/download.json` y
`audit.json`. No se recibieron raw válidos: no hay hashes de datos descargados,
conteos reales, diferencias entre proveedores ni cobertura causal calculada.
`raw_unavailable` y cobertura `null` son estados pendientes, no cobertura cero.

Se añadió [audit_macro_sources.py](../scripts/audit_macro_sources.py), que:

- Descarga únicamente esa ventana a una carpeta nueva; conserva raw y SHA256.
- Puede auditar offline; exige esquema, fechas ordenadas/únicas y valores finitos positivos.
- Rechaza fechas fuera de la ventana, incluidos 2024 y test, sin normalizarlas silenciosamente.
- Conserva nulos; separa días laborables sin valor de huecos confirmados por calendario.
- No convierte un snapshot válido en aprobación temporal, ni genera features.

Once tests pasan; cubren estas validaciones, los límites de partición y la
protección contra sobrescritura. No son todavía los tests de un pipeline
macro completo: éste no se ha implementado ni validado con datos reales.

```bash
# Reintento futuro: siempre carpeta NUEVA.
python scripts/audit_macro_sources.py data/external/macro-audit-<nuevo-id> --fetch
# Revisión offline del estado de esta sesión.
python scripts/audit_macro_sources.py data/external/macro-audit-20261006
pytest tests/test_macro_source_audit.py -q
```

## 6. Contrato exigido para la futura alineación causal

Cada registro deberá distinguir `observation_date`, `market_close_at`,
`source_release_at`, `provider_available_at` si se conoce, `retrieved_at`,
versión/vintage y `available_at` con su fundamento. Una fecha de observación
es una etiqueta de período, no un timestamp de disponibilidad.

La unión sobre decisiones BTC exigirá **`available_at < decision_at`**.
Las revisiones se aplican solo desde su disponibilidad; las medias y cambios
deben calcularse con el historial conocido en cada decisión, no con la versión
final del fichero. Varias observaciones publicadas juntas requieren tratar
el lote completo; no eliminar duplicados por hora y perder días de H.10.

Definir por separado edad desde publicación y edad desde cierre/observación.
Una revisión de un dato viejo no lo convierte en una observación de mercado
reciente. Expirar valores con una regla preregistrada y conservar indicadores
de ausencia; no hacer forward-fill ilimitado ni rellenar hacia atrás.

Usar calendarios históricos distintos para acciones, opciones/VIX y releases
de la Fed. Convertir zonas IANA a UTC con DST; no fijar un offset universal.
Verificar cierres anticipados y cambios de festivos: por ejemplo, el calendario
NYSE documentó cierre a las 13:00 Eastern el 24-11-2023, y Nasdaq documentó
el cierre por Juneteenth del 20-06-2022.
[Comunicado NYSE](https://www.nasdaq.com/press-release/nyse-group-announces-2022-2023-and-2024-holiday-and-early-closings-calendar-2021-12),
[Aviso Nasdaq](https://www.nasdaqtrader.com/TraderNews.aspx?id=ETA2022-55).

Pruebas pendientes antes de integrar: instante exacto de publicación, revisiones
retroactivas, viernes–lunes/festivo, cambios DST USA/Europa, early close, dato
ausente/expirado, lotes semanales y límites train/evaluación. Medir cobertura
sobre las filas congeladas de it.13, sin entrenar ni eliminar barras por outcomes futuros.

## 7. Siguiente paso planteado inicialmente (actualizado arriba)

Resolver el acceso a raw acotados y verificar vintages/publicación de S&P 500
y VIX. Después, medir cobertura y decidir si existe soporte temporal suficiente
o hace falta aceptar un supuesto explícito. DTWEXBGS queda fuera de esa primera
propuesta; DXY necesita una auditoría propia si se mantiene como requisito.

Solo entonces preregistrar it.15: referencia it.13 ±100 pb y una única familia
macro, mismos costes, gate y risk-return-v1. Las features del plan son todavía
orientativas; no hay selección de columnas, lag o caducidad basada en backtests.
No se afirma que macro vaya a resolver el edge ni que la fase E esté terminada.
