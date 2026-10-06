# Reconstrucción diaria de VIX — auditoría temporal no aprobada para entrenamiento

Fecha: 2026-10-06. Continuación de la [auditoría macro](macro-data-audit.md).
**Actualización posterior:** la clave ya está configurada y la API oficial
[reproduce las 30 anomalías](vix-api-crosscheck.md) en 37 vintages consultadas.
La falta de credenciales quedó resuelta; la fuente sigue sin aprobación.
**Se recibieron los 1.522 snapshots diarios solicitados; 30 contienen fechas
de observación futuras respecto a su vintage y se excluyen íntegramente.**
La cobertura restante de evaluación 2023 H1 es **93,34%** bajo las convenciones
de esta auditoría. No se inicia it.15, no se entrena ni se abre el test reservado.

## Qué se reconstruyó

Una petición por día calendario, incluidos fines de semana, desde 2019-11-01
hasta 2023-12-31. Cada CSV solicita observaciones dentro de esa misma ventana
y una `vintage_date` explícita. Se conservan URL, estado de captura, raw y hashes.
El identificador de la columna debe corresponder a la vintage solicitada.
La descarga se realizó con curl de Windows, TLS verificado, timeouts y hasta
tres conexiones simultáneas. Los reintentos no sustituyeron raw ya validados.

El código inicial quedó registrado antes de la captura en `faabf22`. La
construcción estricta se detuvo al detectar versiones inválidas. Después se
añadió un modo **offline y exclusivamente diagnóstico** que pone en cuarentena
el snapshot completo. No se recortan sus filas futuras para convertirlo en
una versión aprobada. El flujo estricto sigue rechazándolo.

## El problema encontrado no es solo conectividad

Ejemplo conservado: respuesta a la vintage **2023-01-13**, con encabezado
`VIXCLS_20230113`, contiene:

```text
2023-01-12,18.83
2023-01-13,18.35
2023-01-16,19.49
```

El 16 de enero es posterior a la fecha solicitada. Un HTTP 200 y un encabezado
correcto no bastan para acreditar que el contenido estaba disponible el día 13.
Se reprodujo la respuesta tanto desde Windows como desde WSL.
[Petición reproducible al endpoint](https://alfred.stlouisfed.org/graph/alfredgraph.csv?id=VIXCLS&cosd=2019-11-01&coed=2023-12-31&vintage_date=2023-01-13).

Las 30 versiones afectadas contienen observaciones futuras correspondientes
a doce fechas: 2022-05-30, 2022-06-20, 2022-07-04, 2022-09-05, 2022-11-24,
2023-01-16, 2023-02-20, 2023-05-29, 2023-06-19, 2023-07-04, 2023-09-04 y
2023-11-23. Coinciden con las doce fechas con VIX y sin SP500 identificadas en
la auditoría anterior. **La coincidencia es descriptiva; la causa exacta no
está demostrada.** Puede ser necesario distinguir comportamiento del gráfico,
metadatos de publicación y archivo subyacente mediante la API oficial.

El hallazgo se refiere a esta extracción. No demuestra que todas las series
de ALFRED sean incorrectas ni que sus otros mecanismos de descarga fallen.
La documentación de ALFRED describe distintas procedencias para sus fechas
de publicación y una incorporación habitual dentro de un día laborable;
no proporciona por ello una garantía intradía uniforme.
[Ayuda oficial ALFRED](https://alfred.stlouisfed.org/help).

## Convenciones fijadas antes de medir cobertura

- Cada versión se considera utilizable, **por hipótesis**, desde su fecha
  a las 00:00 UTC más 48 horas. Esto no acredita la hora real de entrega
  histórica de FRED, especialmente alrededor de fines de semana y festivos.
- Unión estricta `assumed_available_at < decision_at`; la igualdad no sirve.
- Una versión no se arrastra más de 24 horas desde su disponibilidad asumida.
  Si la siguiente está en cuarentena, aparecen ausencias; no se toma una posterior.
- Antigüedad máxima de observación: 168 horas desde la fecha de observación
  etiquetada a las 00:00 UTC. Es edad de la **fecha**, no desde el cierre VIX.
- Estado diagnóstico: último nivel VIX y diferencia absoluta en puntos entre
  las dos últimas observaciones distintas conocidas en esa versión.
  Repetir snapshots durante el fin de semana no introduce retornos cero artificiales.
- La edad de observación y la edad de la versión se guardan por separado.

No se cambiaron estos límites para recuperar cobertura tras ver los huecos.
El modo cuarentena reduce la información admitida y no aprueba ninguna receta.

## Cobertura sobre las filas originales de it.13

Solo se leyeron los índices de los Parquet de train y predicciones: no sus
retornos, probabilidades o métricas económicas. Se conservaron todas las filas,
marcando elegibilidad; no se entrenó sobre una selección retrospectiva.

| Fold | Train original | Train elegible | Cobertura train | Evaluación original | Evaluación elegible | Cobertura evaluación |
|---|---:|---:|---:|---:|---:|---:|
| 2022 H1 | 68.981 | 68.885 | 99,86% | 17.360 | 16.784 | 96,68% |
| 2022 H2 | 86.357 | 85.685 | 99,22% | 17.648 | 16.976 | 96,19% |
| 2023 H1 | 104.021 | 102.677 | 98,71% | 17.304 | 16.152 | **93,34%** |
| 2023 H2 | 121.326 | 118.830 | 97,94% | 17.648 | 17.168 | 97,28% |

Estos porcentajes están **condicionados a las convenciones anteriores**,
no demuestran disponibilidad real. H1 2023 queda por debajo de la referencia
de cobertura del 95% del proyecto. No se amplía la caducidad para hacerlo pasar.

Los 1.492 snapshots que pasan la validación contienen, en conjunto, 1.059
fechas de observación distintas. No se detectaron cambios numéricos ni
retiradas de valores previamente presentes entre versiones aceptadas.
Eso **no equivale a disponibilidad completa desde la fecha de observación**:
hay incorporaciones tardías. El dato del **2021-04-16 aparece por primera vez
en una versión aceptada del 2021-06-03: 48 días después**.
Las comparaciones anuales previas no podían detectar ese retraso.

`first_seen.csv` significa primera aparición en versiones **aceptadas**;
la cuarentena puede retrasar ese indicador para 2022–2023. El caso de 2021
no está afectado por esas 30 cuarentenas. Los registros futuros rechazados
no se incorporan ni se utilizan para calcular el estado del modelo.

## Validación y artifacts

- 24 tests dirigidos pasan: vintage incorrecta, observación futura, caso real
  del 13/16 de enero, revisiones, as-of estricto, caducidad, fin de semana,
  ausencia por cuarentena y protección de las particiones reservadas.
- Verificador independiente basado en búsqueda de timestamps ordenados:
  contrasta raw, hashes, exclusiones, estados, edades y alineación con los
  índices originales. Normaliza explícitamente unidades de timestamps antes
  de comparar nanosegundos; no reutiliza el `merge_asof` del constructor.
- No modelos ni backtests nuevos; 2024 y test 2025–2026 sin evaluar.

Carpeta raw y diagnóstico:
`data/external/vix-daily-vintages-20261006/`.
Contiene `raw/`, `capture.json`, `policy.json`, `quarantine.json`,
`daily_states.parquet`, `first_seen.csv`, `revision_events.csv`, `coverage.csv`,
`alignment/`, `report.json` y `verification.json`.
Los artifacts con huecos sirven para auditar; **no son un dataset aprobado**.

```bash
# Diagnóstico offline conservando la cuarentena completa:
python -m scripts.reconstruct_vix_history data/external/vix-daily-vintages-20261006 --offline --quarantine
python -m scripts.verify_vix_history data/external/vix-daily-vintages-20261006
pytest tests/test_vix_reconstruction.py tests/test_macro_source_audit.py tests/test_macro_vintages.py -q
```

## Decisión y siguiente comprobación

**No aprobar todavía la fuente para it.15.** Antes de cualquier entrenamiento,
contrastar los casos anómalos con la API oficial `series/observations`, fijando
`realtime_start=realtime_end` en la vintage y manteniendo las observaciones
acotadas a 2019–2023. Empezar por el 13-01-2023 y el caso de incorporación
tardía de abril de 2021; no repetir toda la captura sin resolver esos casos.
[Documentación API](https://fred.stlouisfed.org/docs/api/fred/series_observations.html).

En el cierre inicial faltaba configurar `FRED_API_KEY`. El usuario la añadió
localmente y se completó el [contraste oficial](vix-api-crosscheck.md): las
30 anomalías se reproducen. Falta investigar su significado con otra evidencia
temporal o replantear la fuente; no ocultarlas con un lag.
