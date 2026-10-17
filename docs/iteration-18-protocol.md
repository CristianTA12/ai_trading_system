# It.18 — Frecuencia de decisión alineada al horizonte 4h

Fecha: 2026-10-17. Preregistro antes de implementación y evaluación.
Una sola intervención de política sobre probabilidades congeladas de it.13;
cero modelos nuevos, sin features adicionales ni búsqueda de umbrales.

## Hipótesis y límites

El [diagnóstico emparejado](classifier-value-diagnostic.md) muestra selección
bruta favorable, penalización por rotación y déficit bruto en 2023 H1.
Evaluar cada 15 minutos pronósticos de 4h muy solapados podría generar cambios
de posición que no corresponden a una oportunidad nueva. Se fija la cadencia
al horizonte que el modelo ya predice, no a una ventana elegida por rentabilidad.
No garantiza menos trades ni mejor retorno; puede omitir buenas entradas o
retrasar salidas. No pretende resolver por sí sola el déficit bruto de H1.

## Regla congelada

Control: `four_hour_regime` de it.13, mismos targets y ejecución reproducidos.
Candidato: `four_hour_grid`.

- Conserva las probabilidades de cada uno de los 20 modelos de it.13.
- Gate diario SMA50>SMA200 sin cambios. Datos y ejecuciones siguen en barras 15m.
- Decisiones ordinarias solo en 00:00, 04:00, 08:00, 12:00, 16:00 y 20:00 UTC.
  Se usa la predicción existente en ese timestamp, ya disponible según el
  contrato de it.13. No se desplaza a la siguiente barra si falta la de la rejilla.
- En una decisión ordinaria, target long si argmax es UP y p_up>=0,50;
  en caso contrario cash. Empates mantienen orden DOWN, NEUTRAL, UP.
- Entre decisiones, mantener el último target. Esto produce holding mínimo
  normal de 4h sin añadir otro parámetro de holding.
- Gate cerrado/ausente o predicción ausente en **cualquier barra observada**:
  cash inmediato, también entre decisiones. Una señal posterior no reabre
  posición hasta la próxima decisión ordinaria. Sin posiciones latentes.
- Primer estado del fold cash; liquidación al final por el motor existente.
- No cooldown, stop, sizing, umbral de salida distinto ni salida solo por DOWN.
  No probar otros desplazamientos de reloj, cadencias o variantes si falla.

La diferencia con it.16 es la cadencia, no el significado de NEUTRAL: en cada
decisión ordinaria sigue causando salida. It.16 operaba sobre SP500 y mantenía
posición hasta DOWN; aquí se conserva la clasificación y se usa it.13 v1.

## Comparación, ejecución y trazabilidad

Fuente: `data/experiments/iteration-13-20260930-four-hour`.
Folds 2022 H1/H2, 2023 H1/H2; semillas 42,123,456,789,2026.
Mismas barras por fold, sin excluir filas por ausencia de outcome futuro.
No deserializar datos >=2024. Se puede verificar hash del archivo completo.

Capital 10.000 por fold; long/flat 100%, spot, sin apalancamiento.
Bruto: fee/slippage cero. Base: taker 0,0004 por lado, slippage 0,0001.
Stress: mismo fee, slippage 0,0002. No modelo de ejecución maker.

Antes del candidato, reproducir 60 backtests control (20 pares x 3 escenarios)
y exigir igualdad exacta de targets/equity/fills/trades originales. Abortar si
no coincide; no corregir datos o tolerancias para obtener aprobación.
Registrar hashes de predicciones, targets, gate y artefactos usados antes/después.
El manifiesto original parcial no acredita todos esos archivos; se registra
esa limitación y la reproducción del control, sin inventar un manifiesto histórico.

Luego ejecutar 60 backtests candidatos y ocho benchmarks B&H/cash base.
Regla de rejilla comprobada también con un recorrido independiente. Guardar
targets, curvas, fills, trades, tablas, veredicto y manifiesto en carpeta nueva.
Registrar en MLflow. Código y preregistro en Git antes de evaluar candidato.

## Criterio inalterado y decisión

`risk-return-v1`, SHA256
`12398837a044bd1b4519e22c67cf4d8bd68616eb12580d56d6f48dde5fec638a`.
Exigir >=4/5 semillas con todos los gates: compuesto neto positivo, DD<=15%
por fold y concatenado, compuesto stress positivo y consistencia Sharpe/DD
frente a B&H en >=3/4 folds con excepción cash vigente.

Informar retorno bruto/neto, costes, exposición, trades y consistencia por fold.
No elegir retrospectivamente semilla, semestre o métrica favorable. Menos
operaciones sin pasar el criterio no es aprobación. Si falla, cerrar esta
formulación sin probar otra rejilla. Si pasa, es desarrollo adaptativo sobre
folds reutilizados, no confirmación independiente ni permiso para desplegar
o abrir automáticamente el test reservado. No se promueve el control rechazado.
