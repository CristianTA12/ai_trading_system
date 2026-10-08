# Preparación de flujo agresor: contrato y dataset separado

Fecha: 2026-10-08. Continúa la [auditoría](aggressor-flow-audit.md).
Esta preparación no entrena ni evalúa rentabilidad. No cambia las 20 features
v1, el snapshot original, los modelos ni `risk-return-v1`.

## Contrato de las dos features

Para una decisión t, la última barra utilizable abre en t−30 min y cierra
en t−15 min. Se deja una barra completa de margen de entrega asumido.
No se usa la barra que acaba de cerrar en t. Una barra exige sus 15 minutos
observados, ordenados y únicos; no se interpolan huecos.

- `flow_imbalance_15m`: (2 × volumen comprador agresor − volumen total)
  dividido por volumen total en esa última barra elegible.
- `flow_imbalance_1h`: misma fórmula sobre las sumas de cuatro barras
  consecutivas, intervalo [t−75min,t−15min). No media simple de ratios.

Ambas usan volumen base BTC. Un valor positivo indica más volumen comprador
agresor que vendedor agresor; no identifica intenciones ni órdenes pendientes.
Volumen total cero produce NaN. Si falta una barra de la hora, la feature
horaria es NaN, sin sustituirla por una ventana más antigua. El campo
`eligible_under_assumption` exige que las dos features sean finitas.
Una barra individual sin operaciones puede integrar una hora con volumen
positivo; la feature de 15m sigue siendo ausente si su denominador es cero.

El margen temporal no demuestra latencia histórica ni ausencia de revisiones.
No trasladar aquí el supuesto +48h de SP500. Antes de una evaluación de
rendimiento, el protocolo debe declarar expresamente el carácter condicionado
de la disponibilidad; una captura futura podrá contrastar la entrega real.

## Datos y emparejamiento

48 ZIP de enero 2020 a diciembre 2023, con checksum de Binance y hash
idéntico al registrado en la auditoría. Las ocho filas con duración errónea
siguen excluidas. Solo se agregan minutos válidos. Los raw se vuelven a
comprobar al final; no se sobrescriben.

Se leen únicamente índices de las filas train y predicciones de it.13.
Las cinco semillas deben compartir exactamente el índice de evaluación.
No se leen valores de predicciones, labels ni outcomes. Los índices completos
se conservan en cada alignment; otro archivo guarda filas elegibles para
aplicarlas por igual a candidato y control en un futuro experimento.
No eliminar señales por falta de outcome futuro. No consultar 2024 ni test.

Artifacts: `data/processed/aggressor-flow-preparation-20261008/`:

- `flow_bars.parquet`: volúmenes 15m, timestamp de apertura y recuento de minutos.
- `alignment/<fold>/{train,evaluation}.parquet`: features, timestamps fuente
  y elegibilidad sobre los índices originales.
- Archivos `*_paired_rows.parquet`: índices comunes elegibles.
- `coverage.csv`, `report.json` y manifiesto de integridad final.

El directorio de salida debe ser nuevo; el preparador rechaza sobrescribirlo.
Se exige cobertura ≥95% en cada partición, sin ajustar margen o ventanas
si falla. Una reducción de filas obligaría a reentrenar el control emparejado;
no reutilizar un resultado previo como control si las filas cambian.

## Comprobaciones

Preparación terminada: **450.645 filas verificadas**, 450.643 elegibles.
Se reconstruyen 140.096 barras completas de flujo.

| Fold | Train elegible/original | Evaluación elegible/original |
|---|---:|---:|
| 2022 H1 | 68.981/68.981 | 17.360/17.360 |
| 2022 H2 | 86.357/86.357 | 17.648/17.648 |
| 2023 H1 | 104.021/104.021 | 17.302/17.304 |
| 2023 H2 | 121.326/121.326 | 17.648/17.648 |

La cobertura mínima es **99,9884%**, superior al 95% exigido. Las dos
filas ausentes permanecen en el alignment con elegibilidad falsa; solo
se excluyen del índice emparejado. En ejecución futura deberán aplicarse
las mismas reglas de señal ausente a candidato y control, sin eliminar
las barras de precios ni anticipar huecos.

Cada valor exportado se compara con un cálculo escalar por timestamps,
sin llamar al builder de features. Se verifican también NaN y elegibilidad.
Los tests cubren huecos, exclusión de barras recientes/futuras, ratio de
sumas, denominadores cero y volumen inválido.

Suite completa: **249 tests pasan, dos de integración omitidos**.
Código: [aggressor_flow.py](../src/features/aggressor_flow.py) y
[prepare_aggressor_flow.py](../scripts/prepare_aggressor_flow.py).

La preparación es un requisito de datos, no una nueva receta aprobada.
El siguiente paso es preregistrar una única comparación con control v1
emparejado, sin mezclar SP500/funding ni modificar a la vez target y política.
No hay autorización implícita de abrir el test ni de operar dinero real.
