# Primer histórico: BTC/USDT spot, velas de 1 minuto

Esta fase descarga un mes completo desde Binance Public Data, conserva el ZIP
original y su `.CHECKSUM`, comprueba calidad y permite cargar TimescaleDB.
No necesita claves de exchange. Solo admite BTC/USDT spot 1m por ahora.

## Descargar, validar y cargar

Activar el entorno Python y arrancar los servicios (`make up`). Desde la raíz:

```bash
make download-data DATA_ARGS="--month 2026-08"
make validate-data DATA_ARGS="--month 2026-08"
make load-data DATA_ARGS="--month 2026-08"
```

Los comandos equivalentes son `trading download-historical`, `trading validate-data`
y `trading load-data`, con los mismos argumentos. Sin `--month`, seleccionan el
mes anterior en UTC. Binance publica los archivos mensuales el primer lunes del
mes siguiente; si aún no está publicado, el comando falla con un mensaje claro.

Los originales y el informe `.report.json` quedan en:

```text
data/raw/binance/spot/BTCUSDT/1m/
```

Se puede cambiar la raíz con `RAW_DATA_DIR` en `.env` o `--raw-dir RUTA` en los
tres comandos. `DATA_DIR` controla el almacenamiento Docker del Compose nativo,
no las descargas. En WSL, el valor predeterminado deja los archivos en la unidad
del repositorio. Los datos están excluidos de Git.

La descarga reutiliza archivos locales verificados. Para obtener una revisión
del archivo publicado por Binance, usar `--refresh` en `download-historical` y
volver a validar/cargar. No editar los CSV para hacer que pasen la validación.

## Qué se comprueba

- SHA-256 del ZIP contra el checksum publicado.
- Fechas UTC: milisegundos antes de 2025, microsegundos desde enero de 2025.
- Un mes completo, con una vela cerrada por minuto, incluidos ambos extremos.
- Ausencia de duplicados, huecos y fechas desordenadas o fuera del mes.
- Precios positivos y finitos, máximos/mínimos coherentes, volumen no negativo
  y número de operaciones entero no negativo.

Un fallo devuelve código distinto de cero y bloquea la carga. No se rellenan
huecos ni se borran filas automáticamente. Los errores de calidad se detallan
en el JSON; errores de formato o checksum se notifican antes de generarlo.

La carga se hace en lotes de 2.000 dentro de una única transacción. Si falla un
lote, no queda el mes parcialmente cargado. Repetirla conserva el número de
filas y omite escrituras si los valores no cambian. Una revisión válida del
archivo actualiza las velas existentes.

En `ohlcv`, estos datos usan `exchange='binance_spot'`, `symbol='BTC/USDT'` y
`timeframe='1m'`. El nombre distingue el mercado en el esquema actual; los futuros
deben usar un identificador diferente cuando se implementen. No mezclar estos
datos con registros antiguos que tengan únicamente `exchange='binance'`.

## Dashboard

Añadir una contraseña propia `GRAFANA_DB_PASSWORD` a `.env` y ejecutar:

```bash
make setup-dashboard
make up
```

El primer comando crea o actualiza el usuario `trading_grafana` con lectura sobre
`public.ohlcv`. El segundo provisiona el datasource y el dashboard en Grafana.
Funciona también con una base de datos ya inicializada, sin borrar volúmenes.

Abrir http://localhost:3000/d/trading-data-quality y entrar con las credenciales
Grafana de `.env`. Muestra número de velas, primer/último registro, cobertura y
minutos ausentes por mes cargado, cierre por hora y últimas velas. La cobertura
no incluye meses sin ninguna fila y no sustituye el informe de calidad. Las
consultas usan el histórico cargado, independientemente del selector temporal.

## Verificación

```bash
make test
RUN_DB_TESTS=1 make test-integration
```

Los tests unitarios generan archivos sintéticos y no acceden a Internet. La prueba
de integración crea un esquema temporal único en PostgreSQL y lo elimina al
terminar; comprueba repetición de carga y rollback, sin modificar `public.ohlcv`.

El siguiente paso, después de revisar este mes, es ampliar el histórico y crear
features con separación temporal de entrenamiento, validación y prueba. No se
ha implementado todavía streaming, ingesta de futuros ni entrenamiento.

Fuentes: [formato, publicación y checksums de Binance](https://github.com/binance/binance-public-data),
[datasource PostgreSQL de Grafana](https://grafana.com/docs/grafana/latest/datasources/postgres/configure/).
