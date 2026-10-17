# ¿Qué aporta el clasificador sobre SMA50/200? — 2026-10-17

**Aporta selección y reducción de riesgo observadas, pero no una receta robusta
que supere el criterio.** La explicación «solo reduce exposición y pierde
subidas» era incompleta. El modelo supera el retorno bruto compuesto del filtro
solo en 5/5 semillas; la rotación elimina esa superioridad neta en 4/5. En 2023 H1
también pierde frente al filtro antes de costes: no basta con abaratar ejecución.

## Comparación emparejada

Se leen exclusivamente artefactos de it.13, cuatro semestres 2022–2023 y cinco
semillas. Ya existían B&H, régimen solo y clasificador 4h + régimen, con curvas
base y curvas sin costes. Mismas barras, gate, capital y costes de ejecución.
La política del modelo conserva su holding mínimo 4h; el régimen solo mantiene
posición mientras el gate permite long. No se cambia ninguna de las dos.

| Receta | Compuesto neto | Compuesto bruto | DD concatenado | Operaciones | Exposición media |
|---|---:|---:|---:|---:|---:|
| B&H | −8,87% | No guardado | 67,51% | 4 | 100% |
| SMA50/200 solo | +26,34% | +26,85% | 24,21% | 4 | 40,16% |
| Modelo + gate, rango de cinco semillas | +14,58% a +29,90% | +31,27% a +50,02% | 9,95% a 14,90% | 136–144 | 3,14%–3,33% |

El compuesto enlaza folds liquidados y reiniciados, no una inversión B&H continua
de dos años. La exposición es la media de las fracciones de barras por semestre.
No se agregan las cinco semillas como si fueran una cartera o cinco mercados.
El filtro solo incumple riesgo; no es un sustituto promovible del modelo.

## Los cuatro semestres

| Fold | B&H neto | Filtro neto | Modelo neto, media de semillas | Lectura |
|---|---:|---:|---:|---|
| 2022 H1 | −56,89% | −7,05% | +1,92% | Modelo mejora retorno, Sharpe y DD frente al filtro en 5/5 |
| 2022 H2 | −17,13% | 0% | 0% | Gate cerrado; no permite atribuir valor al clasificador |
| 2023 H1 | +84,03% | +30,96% | +9,48% | Modelo pierde retorno y Sharpe frente al filtro en 5/5, aunque reduce DD |
| 2023 H2 | +38,62% | +3,79% | +9,55% | Modelo mejora retorno, Sharpe y DD frente al filtro en 5/5 |

Corrección importante de referencias anteriores: en estos artefactos emparejados,
B&H de 2023 H1 es **+84,03%**; el +30,96% corresponde al filtro solo.
En 2023 H2 solo las semillas 456 y 2026 superan el Sharpe de B&H, aunque las
cinco superan el Sharpe del filtro. Por tanto, «mejora el filtro» no equivale a
cumplir risk-return-v1. Se conserva el rechazo de it.13: 2/5, se requieren 4/5.

## Costes y rotación: identidad exacta

Se expresa la diferencia en puntos de **retorno logarítmico**, que permiten
sumar contribuciones de barras y folds sin confundirlas con puntos porcentuales
de retorno simple:

`ventaja neta = ventaja bruta − penalización adicional por costes`.

La penalización se obtiene de las curvas netas y brutas ya guardadas; incluye
fees, slippage y su efecto compuesto. No es simplemente la suma nominal de fees.

| Semilla | Ventaja bruta modelo−filtro | Penalización adicional | Ventaja neta |
|---|---:|---:|---:|
| 42 | +8,31 | 13,30 | −4,99 |
| 123 | +8,20 | 13,60 | −5,40 |
| 456 | +16,78 | 14,00 | +2,78 |
| 789 | +3,43 | 13,20 | −9,77 |
| 2026 | +13,56 | 13,60 | −0,04 |

Los 132–140 round trips adicionales por semilla explican esa penalización bajo
el coste del motor, cercano a 10 pb por operación completa. La semilla 2026
queda ligeramente por debajo del filtro neto; el redondeo no debe convertirla
en un empate o victoria. No se elige la semilla 456 por este resultado.

## Exposición y selección: qué se puede afirmar

Como diagnóstico descriptivo, se compara el retorno bruto del filtro en las
barras donde el modelo mantiene posición y donde permanece en cash:

| Fold | Retorno log bruto del filtro por barra seleccionada, pb | Por barra omitida, pb | Parte de exposición del filtro conservada |
|---|---:|---:|---:|
| 2022 H1 | +1,36 | −0,99 | 19,51% |
| 2023 H1 | +1,31 | +0,08 | 9,23% |
| 2023 H2 | +1,89 | −0,08 | 5,55% |

Son medias descriptivas entre semillas, no estimaciones independientes, tests
de significación ni retornos alcanzables comprando cada barra. La selección
incluye holding, entradas/salidas y conocimiento del modelo, no solo predicción
instantánea. Las curvas marcan a cierre; los movimientos entre cierre y open
pueden contribuir en intervalos de salida incluso si el target de la barra es cash.

La descomposición adicional usa `q = exposición modelo / exposición filtro`:

`ventaja bruta = (q−1) × log(retorno-factor filtro) + [log(retorno-factor modelo) − q × log(retorno-factor filtro)]`.

El segundo término es un residual de selección y timing, **no alpha identificado**
ni una cartera de exposición igualada ejecutada. En 2023 H1 la media de términos
es −24,57 por reducción de exposición +14,24 de residual = −10,34 puntos log
brutos; los costes adicionales de 7,68 llevan la diferencia neta a −18,02.
En 2022 H1 y 2023 H2 el diferencial neto medio es +9,18 y +5,35 respectivamente.

## Decisión centrada en el objetivo

1. **No sustituir el modelo por SMA solo:** el filtro incumple el límite de DD.
2. **No concluir que el clasificador carece de información útil:** la selección
   observada y el control de riesgo aportan valor, aunque no prueban generalización.
3. **No atribuir todo a costes:** 2023 H1 mantiene déficit bruto en las cinco semillas.
4. Si se plantea una intervención, debe abordar la política que transforma las
   probabilidades congeladas en exposición y rotación, con costes taker intactos,
   frente a la política actual y en los cuatro folds. No basta con volver a probar
   salida DOWN: esa variante ya fue rechazada en it.16 sobre otra receta.
5. Este diagnóstico **no justifica todavía un umbral o una nueva regla concreta**.
   No se inicia un barrido ni se afirma que prolongar posiciones vaya a mejorar.
   Primero hay que definir una única política con mecanismo y criterio de descarte
   previos. Si no se puede justificar, se mantiene cerrada la familia.

Se responde así a la pregunta inicial: el modelo no es inútil, pero la receta
actual no convierte su selección observada en superioridad neta consistente.
La siguiente decisión debe ser de política, no de fuentes nuevas o tamaño del modelo.

## Reproducibilidad y límites

Script: `scripts/diagnose_classifier_value.py`; dos tests de las identidades
de atribución y del caso cash pasan. Resultados derivados separados en
`data/experiments/classifier-value-diagnostic-20261017`:
`paired_attribution.csv`, `benchmarks.csv`, `summary.json`, `source_hashes.json`.
Se conservan script y cálculo complementario de compuestos/DD en esa carpeta.

Se comprueba igualdad de índices, targets dentro del gate, exposición y retorno
final frente a la tabla guardada. Se leen 74 archivos: uno tiene hash en el
manifiesto parcial del protocolo original; para todos se registra hash observado
y se comprueba que no cambiaron durante el diagnóstico. No se presenta esto
como verificación de origen completa de los 74 artefactos. It.13 ya disponía
de su verificación anterior; esta revisión es descriptiva y adicional.

Cero entrenamientos y cero backtests nuevos. No se accede al dataset de precios
ni a 2024/test 2025–2026. No se seleccionan semillas ni se cambia risk-return-v1.
Los folds han sido reutilizados muchas veces; estos resultados no son evidencia
fuera de muestra independiente ni una demostración de edge futuro.
