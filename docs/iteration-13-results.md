# Iteración 13 — Horizonte 4h: mejora de edge observado, aprobación insuficiente

Fecha: 2026-09-30. Protocolo `adb8758`, implementación `df241c5`, ambos registrados
antes de entrenar. **El candidato 4h + gate cumple en 2/5 semillas; se requieren
4/5. Receta rechazada para promoción.** Los dos controles obtienen 0/5.
2024 no se reevalúa y test 2025–2026 permanece reservado.

Se ejecutó una única combinación: target 4h con clases ±1%, holding mínimo 4h,
las mismas 20 features v1 de 15m y filtro diario SMA50 > SMA200. No se buscaron
ventanas, umbrales o semillas alternativos ni se redujeron costes.

## Veredicto y cambio respecto a las hipótesis

Las cinco semillas superan rentabilidad base, rentabilidad stress y límite de
drawdown. **El único gate que impide la aprobación de las tres semillas restantes
es consistencia**: no superan el Sharpe de B&H en suficientes semestres.

| Semilla | 4h + gate compuesto neto | Stress | DD concatenado | Consistencia | Cumple todo |
|---|---:|---:|---:|:---:|:---:|
| 42 | +20,19% | +16,94% | 11,15% | 2/4 | No |
| 123 | +19,70% | +16,40% | 10,29% | 2/4 | No |
| 456 | +29,90% | +26,21% | 13,58% | 3/4 | Sí |
| 789 | +14,58% | +11,50% | 14,90% | 2/4 | No |
| 2026 | +26,29% | +22,81% | 9,95% | 3/4 | Sí |

| Gate, candidato | Semillas que cumplen |
|---|:---:|
| Compuesto base >0 | 5/5 |
| DD <=15% por fold y concatenado | 5/5 |
| Consistencia >=3/4 semestres | 2/5 |
| Compuesto stress >0 | 5/5 |
| Todos conjuntamente | **2/5** |

2022 H1 cumple consistencia en las cinco semillas por comparación de Sharpe/DD,
aunque dos retornos sean negativos. 2022 H2 permanece íntegramente en cash por
el gate y cumple su excepción. **2023 H1 no cumple en ninguna semilla.**
En 2023 H2 sí cumplen 456 y 2026; las restantes no superan el Sharpe de B&H.
No se eligen esas dos semillas para abrir test ni se mezclan sus folds.

## Comparación emparejada de los tres brazos

Los brazos 4h comparten modelo y probabilidades; difieren únicamente en el gate.
El control 15m + gate se reentrena con las mismas features, timestamps de train
y predicción y purga 4h. Mide la comparación con la receta de horizonte corto;
no es la reutilización del resultado histórico de iteración 12.

| Semilla | 4h + gate | 4h sin gate | 15m + gate emparejado |
|---|---:|---:|---:|
| 42 | +20,19% | −8,36% | −4,82% |
| 123 | +19,70% | −5,25% | +6,62% |
| 456 | +29,90% | +21,92% | −8,63% |
| 789 | +14,58% | −27,53% | +7,07% |
| 2026 | +26,29% | +0,69% | −6,82% |

El candidato mejora el compuesto de ambos controles en cada semilla. Sin gate,
4h tiene DD concatenados **40,36%–52,71%** y pierde en 2022 H1/H2 con todas
las semillas: el horizonte largo por sí solo no resuelve el riesgo.

El control 15m emparejado pasa rentabilidad base y stress en 2/5, riesgo en 5/5,
y consistencia en 0/5. Su diferencia con it.12 refleja cambios de filas/purga,
muestreo y entrenamiento. Refuerza la sensibilidad ya observada: no debe
atribuirse toda diferencia entre iteraciones al cambio de horizonte. La evidencia
principal aquí es el contraste dentro del experimento emparejado.

## Resultados semestrales del candidato

| Semilla | 2022 H1 | 2022 H2 | 2023 H1 | 2023 H2 |
|---|---:|---:|---:|---:|
| 42 | +4,43% | 0% | +8,31% | +6,26% |
| 123 | −0,63% | 0% | +12,98% | +6,62% |
| 456 | −1,14% | 0% | +15,70% | +13,56% |
| 789 | +5,63% | 0% | +1,29% | +7,09% |
| 2026 | +1,31% | 0% | +9,13% | +14,24% |

Frente a 15m + gate, 4h mejora en nueve de las diez comparaciones de 2023.
La excepción es 789 en 2023 H1: +1,29% frente a +8,80%, con DD 14,90% frente
a 5,72%. No hay superioridad uniforme. El gate conserva los mismos cambios
diarios de it.12; no se modificó para mejorar estos resultados.

## Retorno observado por operación y exposición

Medias aritméticas sobre todas las operaciones cerradas de las cinco ejecuciones
y cuatro folds; no son una cartera conjunta ni pruebas de significación.

| Brazo | Operaciones agregadas | Media bruta por trade | Media neta por trade | Mediana duración | Exposición media por fold/semilla |
|---|---:|---:|---:|---:|---:|
| 4h + gate | 697 | +25,64 pb | +15,62 pb | 240 min | 3,23% |
| 4h sin gate | 2.740 | +10,88 pb | +0,88 pb | 240 min | 12,80% |
| 15m + gate | 784 | +9,50 pb | −0,51 pb | 60 min | 0,92% |

La receta larga mejora el margen observado por trade, pero también mantiene
capital expuesto durante más tiempo. Frente al control corto, hay 87 operaciones
menos (**11,10%**), no una reducción automática a un cuarto. En este dataset
ningún trade 4h terminó antes de 240 minutos; la política permite esa excepción
ante cierre de gate/señal ausente y está probada en tests.

Los **100 pb son el umbral de la clase del target**, no beneficio esperado ni
beneficio medio. La media bruta obtenida es 25,64 pb, no los 40–60 pb inicialmente
sugeridos. sqrt(16)=4 no transforma volatilidad en edge predecible. Tampoco el
resultado positivo demuestra rentabilidad futura ni elimina dependencia de régimen.

La referencia determinista solo gate conserva compuesto base +26,34%, stress
+26,24% y DD concatenado 24,21%, como en it.12; sigue incumpliendo el riesgo.

## Alineación temporal, cobertura y modelos

El índice de features ya es el instante de decisión/apertura. Se usa
`close[t+3h45m]/open[t]-1`, 16 velas consecutivas, con `label_end=t+4h`.
No se añade otro desplazamiento de entrada. Los huecos invalidan el label,
no autorizan eliminar señales futuras de la evaluación.

| Fold | Train v1 original | Train común | Predicciones comunes | Outcomes 4h puntuables |
|---|---:|---:|---:|---:|
| 2022 H1 | 69.221 | 68.981 | 17.360 | 17.360 |
| 2022 H2 | 86.597 | 86.357 | 17.648 | 17.648 |
| 2023 H1 | 104.261 | 104.021 | 17.304 | 17.289 |
| 2023 H2 | 121.581 | 121.326 | 17.648 | 17.648 |

Hay 15 timestamps de 2023 H1 sin outcome 4h completo: se conservan en predicciones
de cada semilla (75 filas en total) y solo se excluyen del scoring de clasificación.
Train usa targets completos y purga común estricta `t+4h < frontera`. Las velas
de ejecución abarcan los semestres completos. Gate válido en el 100% de esas velas.

40 modelos: 20 para target 4h y 20 para target 15m; clasificación tres clases,
mismos hiperparámetros v1 y semillas. Los pesos se calculan en cada train para
su target; cambian con la distribución de clases. No early stopping ni tuning.
Features con frecuencia y lookbacks v1, sin añadir derivados ni recalcular a 4h.

La extensión del clasificador separa predicción de scoring cuando falta un
outcome de evaluación. El gate admite holding configurable y conserva 60 minutos
por defecto, con SMA/disponibilidad diaria inalteradas.

## Validación y trazabilidad

- [Protocolo preregistrado](iteration-13-protocol.md), snapshot fijado por hash de
  metadata y verificación de los cuatro Parquet originales.
- **161 tests pasan, 2 omitidos** por requerir DB; cinco casos nuevos para precios
  exactos/fronteras, huecos, filas comunes y purga, scoring sin filtrar predicción,
  y holding 4h con prioridad del gate. Los tests previos también pasan.
- Ruff y hooks de commit pasan. Modelos guardados y recargados con probabilidades
  exactamente iguales a las usadas en la ejecución.
- **200 backtests**: 180 de los tres brazos y 20 de referencias.
- Verificador reconstruye labels mediante búsqueda independiente por timestamp,
  comprueba máscaras/targets y purga, repite las políticas con una máquina de
  estados independiente, verifica ausencia de posición con gate cerrado, recalcula
  métricas desde equity/fills/trades y reproduce exactamente los tres veredictos.
- Artifacts: `data/experiments/iteration-13-20260930-four-hour/`, con cobertura,
  labels, gate, filas train, modelos, predicciones, clasificación, targets,
  importancias, operaciones/curvas bruto/base/stress y verificación final.
- MLflow: experimento **9**, `spot-iteration-13-four-hour`, ejecución
  [`880a9b2c239c4fab801294b65c1d0141`](http://localhost:5000/#/experiments/9/runs/880a9b2c239c4fab801294b65c1d0141).

```bash
make experiment-four-hour
python scripts/verify_four_hour_experiment.py data/experiments/iteration-13-20260930-four-hour
```

El runner crea otro directorio y rechaza sobrescribir resultados. Inputs,
ventanas, threshold y semillas están fijados; opciones de ejecución: `--output`,
`--tracking-uri`, `--no-mlflow`. Las herramientas no abren el test.

## Lectura y siguiente decisión

La hipótesis recibe apoyo descriptivo: la receta de 4h con gate consigue margen
neto por trade positivo y rentabilidad bajo stress en todas las semillas de estos
folds, mejorando ambos controles. **Todavía no alcanza la estabilidad de
consistencia exigida.** Solo 456 y 2026 añaden 2023 H2 a los dos semestres
consistentes de 2022; ninguna supera B&H en Sharpe en 2023 H1.

Conservar esta receta y sus resultados como línea de investigación, sin promoverla,
seleccionar semillas, reajustar SMA/umbral ni relajar risk-return-v1. El DD de 789,
14,90%, está cerca del límite: pasar ese gate aquí no es una garantía futura.

Antes de proponer otra iteración, estudiar con estos artifacts la falta de
consistencia de 2023 H1 y la sensibilidad al train, sin entrenar variantes hasta
fijar una hipótesis nueva. Objetivo, threshold, pesos y holding cambiaron juntos;
este experimento no identifica un único mecanismo causal. Los labels 4h se
solapan y los mismos folds han guiado trece decisiones: ni muchas filas ni cinco
semillas equivalen a validación independiente. Test 2025–2026 continúa reservado.
