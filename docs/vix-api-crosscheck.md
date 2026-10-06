# Contraste VIX con la API oficial FRED

Fecha: 2026-10-06. Continuación de la
[reconstrucción diaria](vix-vintage-reconstruction.md).
Actualización: el [contraste posterior con Cboe](vix-cboe-crosscheck.md)
confirma todos los valores actuales; la disponibilidad histórica sigue pendiente.

**La autenticación funciona y la API reproduce las 30 anomalías del gráfico.**
Se examinaron 37 vintages: las 30 en cuarentena y siete controles alrededor
de enero de 2023 y de la incorporación tardía de abril de 2021. No hay
diferencias de valores con los CSV históricos guardados. No se repite la
extracción de 1.522 versiones: este contraste no aporta evidencia para
levantar la cuarentena ni aprobar entrenamiento.

## Consulta reproducible y alcance

Endpoint `https://api.stlouisfed.org/fred/series/observations`, `series_id=VIXCLS`,
`realtime_start=realtime_end=vintage`, `observation_start=2019-11-01`,
`observation_end=2023-12-31`, `units=lin`, `output_type=1`, orden ascendente.
Se valida la ventana de respuesta y de cada observación, el recuento completo,
la ausencia de paginación pendiente y las fechas ordenadas y únicas.
Las observaciones futuras se conservan como evidencia diagnóstica.
[Documentación del endpoint](https://fred.stlouisfed.org/docs/api/fred/series_observations.html).

| Comprobación | Resultado |
|---|---|
| Vintages consultadas | 37 |
| Con valores posteriores a su vintage | 30 |
| Diferencias numéricas con el gráfico | 0 |
| Vintage 2023-01-13 | Contiene 2023-01-16 = 19,49 |
| Observación 2021-04-16 | Ausente en 2021-04-16, 2021-04-19 y 2021-06-02; presente con 16,25 en 2021-06-03 |

La extracción diaria previa sitúa la primera aparición aceptada del último
caso 48 días después de la observación; la API confirma los puntos consultados
y el límite 2/3 de junio. Este muestreo no acredita toda la historia de la API
ni explica por qué existen esas fechas futuras. Sí descarta que estos casos
sean exclusivamente una peculiaridad del endpoint de gráficos.

## Decisión

Mantener las 30 exclusiones completas y los límites temporales fijados.
La cobertura diagnóstica anterior de 2023 H1 sigue siendo 93,34%, condicionada
al supuesto de 48 horas. No recalcularla con una caducidad mayor para superar
el 95%. No tratar la fecha de vintage como prueba de publicación intradía.

VIX/ALFRED queda **no aprobado con este protocolo**. El siguiente trabajo útil
es contrastar calendario y valores con la fuente primaria Cboe para explicar
las anomalías; una serie de cierres actuales por sí sola tampoco acreditaría
disponibilidad histórica. Si no se resuelve la evidencia temporal, evaluar
otra fuente macro con un protocolo propio antes de entrenar it.15.
No se han entrenado modelos, ejecutado backtests ni evaluado 2024 o el test
reservado 2025–2026.

## Seguridad, validación y artifacts

La clave se lee de `FRED_API_KEY` en el entorno o `.env`, excluido de Git.
Se transmite solo al endpoint oficial por HTTPS mediante configuración curl
en stdin; no figura en argumentos de proceso, parámetros persistidos ni logs.
No se siguen redirecciones. Los errores de transporte omiten detalles que
puedan contener credenciales y se rechaza una respuesta que refleje la clave.

**32 tests dirigidos pasan**, incluidos ocho nuevos para validar ventanas,
respuestas incompletas, preservación de evidencia futura y protección de la
clave. Ruff y formato pasan.

Artifacts: `data/external/vix-api-audit-20261006/`, con 37 respuestas JSON raw,
`comparisons.json` con parámetros sin clave y hashes, y `report.json`.

```bash
python -m scripts.audit_vix_api data/external/<carpeta-nueva> \
  --curl-executable /mnt/c/Windows/System32/curl.exe
pytest tests/test_vix_api.py tests/test_vix_reconstruction.py \
  tests/test_macro_source_audit.py tests/test_macro_vintages.py -q
```
