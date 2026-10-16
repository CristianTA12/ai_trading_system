# Auditoría de atención externa — 2026-10-16

**Resultado: acceso y esquema correctos en la muestra; no apta para un backtest
causal histórico con la evidencia reunida.** No se abre it.18 ni se asume que
un retraso fijo resuelve el problema. La hipótesis económica no se ha evaluado.

## Ejecución acotada

Una petición al endpoint oficial de pageviews de Wikimedia, página `Bitcoin`,
proyecto `en.wikipedia.org`, `all-access`, agente `user`, frecuencia diaria,
del 1 al 31 de enero de 2020. User-Agent identificable con enlace al repositorio,
timeout 20 segundos y límite de respuesta de 1 MB; sin retries ni descarga masiva.
La [política oficial de acceso](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/documentation/access-policy.html)
exige identificación y recomienda peticiones secuenciales.

| Comprobación | Resultado |
|---|---|
| HTTP | 200 |
| Días esperados / recibidos | 31 / 31 |
| Fechas ausentes o duplicadas | 0 / 0 |
| Recuentos | Enteros no negativos |
| Serie y dimensiones | Coinciden con lo solicitado |
| Valores rellenados | Ninguno |
| Publicación histórica por observación | No acreditada |
| Historial de revisiones | No acreditado |

La cobertura del 100% se refiere exclusivamente a enero de 2020, no a todos
los folds. La validación exige fechas únicas dentro del intervalo solicitado
y no permite confundir booleanos con recuentos. Seis tests cubren faltantes,
duplicados, valores inválidos y registros fuera del alcance.

## Limitación temporal

La respuesta devuelve `access`, `agent`, `article`, `granularity`, `project`,
`timestamp` y `views`. El timestamp etiqueta el periodo observado; no acredita
cuándo se publicó ese valor. Se conservaron cabeceras HTTP y hora de recepción,
pero una cabecera de esta descarga tampoco demuestra disponibilidad en 2020.

La [documentación oficial de problemas y disponibilidad](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/documentation/troubleshooting.html)
describe carga posterior al periodo con retrasos que pueden superar 24 horas.
También advierte que un 404 puede representar cero o datos todavía no cargados,
y que hay omisiones en series. Ninguno de esos casos se rellena automáticamente.
No se ha identificado en las fuentes consultadas una garantía de latencia máxima
histórica ni una serie de versiones publicadas que cierre esta brecha.

El endpoint público actual permite reproducir un snapshot actual, no reconstruir
por sí solo el conocimiento de un investigador en cada fecha histórica.
No se infiere que todos los valores hayan cambiado, ni que no exista ninguna
evidencia posible en otro archivo: la evidencia disponible aquí es insuficiente.

## Artefactos y reproducción

Código: `scripts/audit_attention_source.py`.
Resultados: `data/experiments/attention-source-audit-20261016`.
Incluye cuerpo original `response.bin`, solicitud y cabeceras `request.json`,
diagnóstico `report.json` y hashes `manifest.json`.

```powershell
python scripts/audit_attention_source.py --output data/experiments/otra-auditoria-nueva
```

Exige directorio nuevo; no sobrescribe el snapshot. Repetirlo produciría una
nueva descarga actual, no evidencia retroactiva. No hace falta repetir ahora.

No se han descargado precios, unido retornos, medido correlaciones, probado
umbrales ni consultado el test reservado. Las capturas de klines previas permanecen
separadas. La auditoría no realiza tareas en segundo plano.

## Decisión

Se descarta **la ejecución histórica inmediata de esta formulación**. No se
ejecuta el baseline semanal, no se abre otro barrido de fuentes y no se extiende
a Wikimedia el supuesto temporal previamente aceptado solo para SP500.

La alternativa técnicamente defendible sería observar publicaciones futuras,
registrando cada respuesta y revisión con recepción local. Eso requeriría días
para estudiar publicación y un periodo mucho mayor para rendimiento; el PC de
uso intermitente daría observaciones incompletas. No se inicia esa campaña como
si unas horas pudieran resolver el problema. Se archiva la candidata hasta que
haya una razón y un presupuesto explícitos para ese trabajo o evidencia histórica
adecuada. Esto cierra la auditoría solicitada, no demuestra ausencia de alpha.
