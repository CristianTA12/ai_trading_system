# Histórico y primeras variables para backtesting

## Ampliar el histórico

Desde Ubuntu/WSL, activar el entorno Python y ejecutar:

```bash
make sync-history DATA_ARGS="--start 2020-01 --end 2026-08 --allow-gaps --quarantine-duration-errors"
```

Los extremos son meses incluidos. Sin `--end`, se selecciona el último mes
completo UTC. El comando conserva los ZIP y checksums, valida y carga por mes;
repetirlo reutiliza las descargas y omite escrituras de velas que no cambian.
Los fallos quedan en `data/reports/history-2020-01-2026-08.json`, se continúa con
los meses restantes y se devuelve un error si alguno falla. Repetir el comando
revalida todos los meses y reintenta los fallidos. No ejecutar dos sincronizaciones
simultáneas del mismo rango: comparten el informe de progreso.

Cuando se permite cargar meses con huecos, la transacción también retira de ese
mercado/mes las velas que ya no estén en el archivo validado (`removed_rows`).
Así, una revisión o exclusión no deja datos antiguos aparentando cubrir un hueco.

Dos opciones explícitas permiten conservar un histórico real con discontinuidades:

- `--allow-gaps`: acepta únicamente ausencia de minutos, manteniendo el rechazo
  de precios inválidos, duplicados y fechas desordenadas. No rellena huecos.
- `--quarantine-duration-errors`: requiere la anterior; excluye velas cuya duración
  en el archivo de origen no corresponde a un minuto. Registra el número de
  fila, timestamp y duración en `quarantine` dentro del informe de cada mes.
  Las filas originales siguen disponibles en el ZIP. Incluye duraciones
  truncadas, negativas o mayores a un minuto; sin esta opción se rechaza el mes.

El informe mensual mantiene `valid=false` cuando falta algún minuto, aunque la
carga con esta política se acepte (`accepted_with_gaps=true`). Los comandos
mensuales anteriores siguen siendo estrictos por defecto. La cobertura en
Grafana reflejará esos minutos ausentes, no un 100 % artificial.

## Construir el dataset

Después de completar la ingesta:

```bash
make build-features DATA_ARGS="--start 2020-01 --end 2026-08"
```

Lee TimescaleDB y genera una carpeta nueva en `data/processed/`. `--output RUTA`
permite elegirla; si ya existe se rechaza para no sustituir experimentos anteriores.
Todo el dataset permanece fuera de Git. Se bloquea la exportación si falta algún
mes completo en la base de datos o alguna partición temporal queda vacía.

| Archivo | Contenido |
| --- | --- |
| `bars.parquet` | Velas completas 15m, índice UTC de apertura |
| `features.parquet` | Solo predictores, índice `available_at` |
| `labels.parquet` | Resultado futuro y precios de referencia, separado de los predictores |
| `splits.parquet` | Asignación temporal train/validation/test/purged |
| `metadata.json` | Versión, rango, exclusiones, columnas, particiones y SHA-256 de los archivos |

Se agregan exactamente 15 minutos por vela, alineados a UTC. Una vela parcial se
descarta. Los indicadores se reinician tras cada discontinuidad y necesitan
50 velas consecutivas para disponer de todas las variables. No se interpolan
precios ni se rellenan indicadores hacia atrás.

## Variables v1

Todos los periodos siguientes se expresan en velas de 15 minutos:

La receta v1 está definida en `src/features/dataset.py`; los parámetros de modelos
del YAML no la alteran. Los metadatos guardan el hash de esa receta y las versiones
de pandas, NumPy y PyArrow utilizadas.

| Variables | Definición |
| --- | --- |
| `return_1`, `return_4`, `return_16` | Retorno cierre/cierre a 15m, 1h y 4h |
| `log_return_1` | Logaritmo del cociente de cierres consecutivos |
| `volatility_20` | Desviación típica muestral de los últimos 20 retornos, sin anualizar |
| `sma_distance_20/50` | Cierre / media simple de 20 o 50 cierres − 1 |
| `ema_distance_20/50` | Cierre / media exponencial − 1; `adjust=False`, inicio en primer cierre del segmento |
| `rsi_14_cutler` | 100 × ganancia media / (ganancia + pérdida medias), medias simples de 14 cambios; mercado plano = 50 |
| `atr_14_sma_ratio` | Media simple de 14 true ranges / cierre; no es el suavizado Wilder |
| `range_ratio`, `body_ratio` | (Máximo − mínimo) / cierre y (cierre − apertura) / apertura |
| `volume_relative_20`, `volume_zscore_20` | Volumen respecto a media y desviación de 20 velas, incluida la actual |
| `trades_relative_20` | Número de operaciones / media de 20 velas |
| `hour_sin/cos`, `weekday_sin/cos` | Hora y día UTC de disponibilidad codificados de forma cíclica |

No se entrenan escaladores ni se normaliza usando todo el histórico. Cuando se
añada un modelo, cualquier transformación aprendida deberá ajustarse solo con
la partición de entrenamiento.

## Disponibilidad, objetivos y separación temporal

Una vela abierta a las 10:00 queda disponible a las 10:15. Sus variables llevan
índice **10:15**, y pueden utilizar el cierre, volumen y máximo/mínimo de esa vela.
No son utilizables para operar a las 10:00.

El objetivo `target_return_next_15m` es el cierre/apertura − 1 de la vela siguiente
(10:15–10:30 en el ejemplo). Se exporta aparte, junto con `entry_open`, `exit_close`
y `label_end`. Estos campos **nunca deben entrar como predictores**. Se omiten
objetivos si la vela siguiente no existe o es incompleta.

La apertura siguiente es una referencia idealizada de ejecución. Los objetivos
son brutos: todavía no incluyen comisiones, spread, slippage ni latencia. Este
dataset no es un resultado de rentabilidad ni un motor de backtesting.

La división inicial es temporal:

- Entrenamiento: 2020–2023.
- Validación: 2024.
- Prueba reservada: 2025–agosto de 2026.

Se configura con `--train-end 2024-01-01 --validation-end 2025-01-01`. Los límites
son exclusivos. Las filas cuyo objetivo alcance la siguiente partición quedan
marcadas `purged` y deben excluirse del ajuste. Esta partición inicial no sustituye
la validación walk-forward prevista en el proyecto.

## Lectura

```python
from pathlib import Path
import pandas as pd

folder = Path("data/processed/<carpeta-generada>")
x = pd.read_parquet(folder / "features.parquet")
y = pd.read_parquet(folder / "labels.parquet")
splits = pd.read_parquet(folder / "splits.parquet")
train_index = splits.index[splits["split"] == "train"]
x_train = x.loc[train_index]
y_train = y.loc[train_index, "target_return_next_15m"]
```

Las pruebas comprueban que cambiar o eliminar datos futuros no modifica las
variables pasadas, que los indicadores se reinician tras huecos y que los
objetivos no atraviesan discontinuidades ni límites de partición.
