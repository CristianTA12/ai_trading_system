# S&P 500: snapshot disponible, vintages no disponibles en ALFRED

Fecha: 2026-10-06. Continuación de la [auditoría macro](macro-data-audit.md).

**La API oficial rechaza las solicitudes históricas porque SP500 no existe
en ALFRED.** La misma clave y endpoint sí devuelven el snapshot actual acotado
a 2019-11-01–2023-12-31. El bloqueo observado no es de autenticación ni de
conectividad; esta vía no ofrece las versiones históricas requeridas.

## Evidencia

| Petición | HTTP | Resultado |
|---|---:|---|
| Lista de vintages 2019-11-01–2023-12-31 | 400 | Serie no existente en ALFRED |
| Observaciones con vintage 2019-12-31 | 400 | Mismo error |
| Vintage 2021-12-31 | 400 | Mismo error |
| Vintage 2023-01-13 | 400 | Mismo error |
| Vintage 2023-12-31 | 400 | Mismo error |
| Snapshot actual, observaciones 2019-11-01–2023-12-31 | 200 | 1.086 filas, 1.047 valores no nulos |

Los 1.047 valores comparables coinciden con el CSV FRED ya conservado; último
valor no nulo fechado 2023-12-29. No es una prueba de ausencia de revisiones:
son dos interfaces al snapshot actual. Los errores se conservan íntegros
con parámetros sin clave, HTTP, fecha de captura y hash.

La documentación del endpoint de vintages lo define como fechas de cambios
o nuevas observaciones, no como un registro de horas de entrega intradía.
[API vintagedates](https://fred.stlouisfed.org/docs/api/fred/series_vintagedates.html).
FRED describe SP500 como cierre diario, normalmente a las 16:00 ET, y limita
su histórico a diez años. Ese cierre no acredita cuándo se incorporó cada
observación a FRED ni qué revisiones pudo recibir.
[Notas oficiales de SP500](https://fred.stlouisfed.org/series/SP500).

## Decisión

No aprobar SP500/FRED bajo el requisito vigente de disponibilidad histórica
real. No repetir una captura diaria que el servidor rechaza explícitamente.
Esto no prueba que ninguna otra fuente pueda ofrecer vintages del S&P 500.

La auditoría de las tres fuentes propuestas queda en este estado:

| Fuente | Lo que existe | Lo que falta |
|---|---|---|
| SP500/FRED | Snapshot completo de la ventana | Vintages y entrega histórica |
| VIX/ALFRED | Vintages y valores coincidentes con Cboe | Resolver fechas futuras; 2023 H1 queda en 93,34% con cuarentena |
| DTWEXBGS | Snapshot y muestras de vintages | Reconstrucción de revisiones/publicación semanal; no es DXY |

Ninguna de estas extracciones está aprobada para it.15. El requisito E1 del
[plan](implementation_plan_fase4b_ai_trading.md) exige usar datos después de su
disponibilidad real. Sustituir esa evidencia por un supuesto es una decisión
de diseño que debe quedar explícita, no una corrección técnica del auditor.

## Alternativa concreta para decidir, todavía no preregistrada

Una prueba exploratoria **solo SP500** podría usar el snapshot actual bajo dos
hipótesis: valores históricos representativos de los conocidos entonces y
disponibilidad asumida desde la fecha de observación a las 00:00 UTC más 48 h.
Ese desfase no demuestra ni garantiza la latencia de FRED.

La propuesta sería fijar antes de medir resultados: features `sp500_return_1d`
(dos observaciones distintas), `sp500_sma_distance_20` (20 observaciones
distintas) y edad de la fecha de observación; as-of estricto; edad máxima
168 h; cobertura mínima 95% por fold. Entrenamiento y control emparejados
partirían de it.13, con las mismas cinco semillas, target 4h, umbrales ±100 pb,
holding 4h, gate SMA50/200, costes y `risk-return-v1` sin cambios.

Antes de entrenar habría que aceptar las hipótesis, medir cobertura y
preregistrar el protocolo completo. Un resultado positivo sería condicional:
no acreditaría causalidad histórica ni autorizaría abrir automáticamente el
test reservado. La alternativa es mantener el requisito estricto y buscar
una fuente archivada con evidencia temporal suficiente.

## Validación y reproducción

**43 tests dirigidos pasan**, seis nuevos para este auditor. Los HTTP 400
no se convierten en datasets vacíos válidos. Se verifica paginación, orden,
unicidad, ventana y ausencia de claves en argumentos o respuestas guardadas.
El control actual solo solicita observaciones hasta 2023-12-31.

Artifacts: `data/external/sp500-api-audit-20261006/`.
No modelos, backtests ni evaluación de BTC 2024 o test 2025–2026.

```bash
python -m scripts.audit_sp500_api data/external/<carpeta-nueva> \
  --curl-executable /mnt/c/Windows/System32/curl.exe
```
