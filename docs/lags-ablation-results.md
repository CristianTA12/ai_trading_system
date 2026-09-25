# Ablación de tres lags: ejecución y resultados

El [protocolo previo](lags-ablation-protocol.md) quedó registrado en `0b77438` antes
de ejecutar la comparación. El candidato conserva las 20 columnas v1 y añade solo
`return_1_lag_1`, `return_1_lag_4` y `rsi_14_cutler_lag_1`, con las mismas definiciones
usadas en v2. No se ajustan lookbacks ni umbrales tras observar resultados.

## Reproducir

```bash
DATASET=data/processed/btc-usdt-spot-15m-v1-2020-01-2026-08-20260925T164411092396Z
make experiment-lags DATA_ARGS="--dataset $DATASET"
```

Opciones: `--output` (directorio nuevo), `--tracking-uri` y `--no-mlflow`. El comando
usa el runner emparejado existente con `--variant lags`; el comando `experiment-regime`
conserva la receta v2 como variante predeterminada y sus artifacts anteriores no cambian.

Cada run guarda en un directorio `data/experiments/lags-ablation-*` el protocolo,
versiones y hashes, un Parquet nuevo de 23 features de train, cobertura, ocho modelos,
predicciones, posiciones, métricas brutas/netas, clasificación, operaciones y gráficos.
MLflow usa el experimento `spot-lags-ablation`. El walkthrough 007 se redacta aparte.

## Condiciones de lectura

V1 se reentrena con las mismas filas, etiquetas y pesos de clase que el candidato;
por eso puede diferir del resultado histórico de cobertura completa. Ambos operan
sobre las mismas velas del semestre completo. Falta de señal implica efectivo.

El target sigue siendo 15m, tres clases con ±0,25%; los hiperparámetros no cambian.
Entrada UP argmax y `p_up >= 0,50`, holding mínimo 1h y después salida al dejar de
cumplirse la entrada. Costes: taker 0,04% y slippage 0,01% por ejecución.
Capital inicial 10.000 USDT por semestre, sin posiciones entre folds.

Sharpe diario usa anualización 365 y tipo libre de riesgo cero; drawdown es positivo
y se mide al cierre de las velas. Efectivo tiene retorno y drawdown cero, pero Sharpe
indefinido (`null`), no un Sharpe igual a cero. El criterio histórico sigue siendo
retorno neto **estrictamente positivo en al menos 3/4** semestres. Las comparaciones
de Sharpe/drawdown son diagnósticos, no una sustitución retrospectiva del criterio.

Los cuatro folds son 2022 H1/H2 y 2023 H1/H2 con train expansivo y purga de labels.
2024 no se reevalúa; test 2025–2026 permanece reservado.

## Resultado: no supera el criterio histórico

Ejecución del 26-09-2026, 00:21 hora de Madrid (25-09-2026, 22:21 UTC).
**Lags obtiene 2/4 semestres positivos; el control emparejado obtiene 1/4.**
El gate ≥3/4 no se cumple y no se promueve la variante.

| Semestre | Brazo | Retorno neto | Sharpe diario anualizado | Máximo drawdown |
|---|---|---:|---:|---:|
| 2022 H1 | V1 emparejado | −15,26% | −1,098 | 22,19% |
| 2022 H1 | V1 + lags | −30,38% | −2,271 | 38,49% |
| 2022 H1 | Buy & Hold | −56,89% | −2,035 | 63,18% |
| 2022 H2 | V1 emparejado | −32,36% | −3,127 | 33,00% |
| 2022 H2 | V1 + lags | −30,95% | −2,411 | 38,38% |
| 2022 H2 | Buy & Hold | −17,13% | −0,384 | 37,76% |
| 2023 H1 | V1 emparejado | −3,69% | −0,412 | 9,56% |
| 2023 H1 | V1 + lags | +12,61% | +1,700 | 7,90% |
| 2023 H1 | Buy & Hold | +84,03% | +2,734 | 22,01% |
| 2023 H2 | V1 emparejado | +8,56% | +1,433 | 5,35% |
| 2023 H2 | V1 + lags | +1,74% | +0,446 | 4,84% |
| 2023 H2 | Buy & Hold | +38,62% | +1,888 | 21,02% |

Efectivo: retorno y drawdown 0% en cada semestre, Sharpe indefinido.
Lags mejora retorno y Sharpe frente a v1 en 2022 H2 y 2023 H1, pero empeora ambos en
2022 H1 y 2023 H2. Frente a Buy & Hold, su Sharpe es inferior en los cuatro semestres;
reduce drawdown en tres, con la excepción de 2022 H2. Estas comparaciones son
descriptivas y no redefinen el gate registrado.

| Semestre | Operaciones lags | Exposición lags | Media neta por operación |
|---|---:|---:|---:|
| 2022 H1 | 449 | 11,14% | −7,28 pb |
| 2022 H2 | 210 | 5,13% | −16,91 pb |
| 2023 H1 | 125 | 2,95% | +10,00 pb |
| 2023 H2 | 60 | 1,40% | +3,13 pb |

La mediana de duración es 60 minutos en los cuatro semestres. La mejora de 2023 H1
es concreta, pero no permite afirmar que los lags aporten una ventaja consistente.

## Cobertura y sensibilidad del control

El nuevo Parquet contiene **139.177 filas y 23 columnas**, frente a 139.245 filas v1:
se pierden **68 filas (0,049%)**. Los cuatro folds pierden solo cuatro predicciones
en total. No existe aquí el warmup de 30 días que reducía mucho la cobertura en v2.

| Fold | Train original | Train emparejado | Predicciones originales | Predicciones emparejadas |
|---|---:|---:|---:|---:|
| 2022 H1 | 69.221 | 69.157 | 17.375 | 17.375 |
| 2022 H2 | 86.597 | 86.533 | 17.663 | 17.663 |
| 2023 H1 | 104.261 | 104.197 | 17.319 | 17.315 |
| 2023 H2 | 121.581 | 121.513 | 17.663 | 17.663 |

El control histórico sin esta máscara había conseguido 2/4 positivos; el control
reentrenado ahora obtiene 1/4. Cambiar unas pocas filas puede alterar splits de árboles,
pesos y muestreo interno aunque la semilla y los hiperparámetros se mantengan. La
sensibilidad observada del control es otra razón para no atribuir robustez a un único
resultado favorable. No se cambiaron semillas ni se repitió la búsqueda para mejorarlo.

Esta ablación no mide de forma aislada el efecto del drawdown/tendencia de v2 ni el
coste de su cobertura: eso requeriría el tercer brazo descrito en el protocolo. Tampoco
demuestra que cualquier uso de lags sea inútil. Rechaza esta receta bajo el criterio fijo.

## Artifacts y verificación

- Protocolo previo: commit `0b77438`.
- Directorio: `data/experiments/lags-ablation-20260925T222138341061Z/`.
- MLflow: experimento `spot-lags-ablation`, run `eca3cde7c4a744fe8e5af58dc60741f6`.
- Decisión: `lags_passes_preregistered_gate=false`, `promoted=false`.
- `comparison.csv` contiene métricas completas de ambos brazos y las referencias.
- `coverage.csv`, `protocol.json`, `features_metadata.json` y `report.json` permiten
  revisar la cobertura, configuración y decisión; cada fold conserva ambos modelos.
- 84 tests pasan, incluidos causalidad, reinicio tras huecos, lag por tiempo sin
  comprimir filas ausentes, identidad de los lags respecto a v2 y gate histórico.

No se reescriben los resultados anteriores ni el protocolo después de observarlos.
Las tablas y artifacts anteriores quedan disponibles como base para el walkthrough 007.
