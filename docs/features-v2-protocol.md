# Features v2: protocolo previo a resultados

Estado inicial: definición fijada antes de entrenar o evaluar v2. Fecha: 25-09-2026.
Hipótesis: contexto de drawdown, dirección/persistencia y lags puede mejorar la
selectividad del modelo long-only en los semestres internos, especialmente en 2022.
El patrón histórico motiva la hipótesis; no demuestra que el régimen sea la única causa.

## Definición cerrada: 20 variables v1 + 5 variables nuevas

Todas se calculan sobre velas **cerradas** de 15m y están disponibles al cierre.
Se mantienen nombres, valores y orden de las 20 features v1 y se añaden:

| Feature | Fórmula | Justificación |
|---|---|---|
| `drawdown_from_peak_2880` | `close / rolling_max(high, 2880) - 1` | Distancia al máximo observado de 30 días de velas continuas; contexto de deterioro más largo que los indicadores v1. Incluye el high de la vela recién cerrada. |
| `return_1_lag_1` | `return_1.shift(1)` | Retorno de la vela previa al retorno actual. |
| `return_1_lag_4` | `return_1.shift(4)` | Retorno de hace una hora respecto al retorno actual. |
| `rsi_14_cutler_lag_1` | `rsi_14_cutler.shift(1)` | Estado previo del RSI ya usado por v1. |
| `trend_strength_96` | `(close - close.shift(96)) / rolling_sum(abs(close.diff()), 96)` | Eficiencia direccional de un día: +1 subida persistente, −1 bajada persistente, cerca de 0 desplazamiento pequeño respecto al recorrido. Mercado constante: 0. No es ADX. |

No se prueban otros lookbacks ni variantes después de ver resultados. No se calculan
máximos del futuro ni un máximo global de toda la serie. RSI conserva la definición
Cutler de v1; no se cambia por Wilder en esta comparación.

## Huecos, warmup y comparación justa

Se reinician ventanas y lags tras cualquier hueco, igual que v1. Se exigen **2880 velas
continuas** para el drawdown de 30 días; no se interpolan precios ni se rellenan features.
Esto elimina más filas que v1. Se registrará la cobertura por fold.

Para no atribuir a las features una mejora causada simplemente por operar menos fechas:

- **Referencia histórica:** v1 + holding 1h, cobertura original: 2/4 semestres positivos
  (−33,09%, −36,36%, +9,68%, +12,04%). Se conserva como contexto, sin cambiar sus resultados.
- **Control emparejado:** reentrenar v1 con exactamente las mismas filas de train y de
  predicción disponibles para v2, mismas etiquetas y pesos de clase.
- **Candidato v2:** las 25 variables con esas mismas filas. Fuera de cobertura, ambos
  controles pasan a efectivo en la siguiente apertura observada.

Cada brazo usa las mismas velas de ejecución del semestre completo, 10.000 USDT iniciales
y los mismos costes. No se comparan curvas que omitan silenciosamente las fechas sin
features. La máscara depende solo del pasado y no de la rentabilidad futura.

## Modelo, política y particiones fijas

Se reutiliza el **target original de 15m, tres clases**, con umbrales ±0,25%. No se usa
el target binario de 1h: cambiar ambos factores impediría aislar las nuevas variables.
500 árboles, profundidad 6, learning rate 0,05, subsample/colsample 0,8, hist CPU,
cuatro workers, semilla 42 y pesos inversos de clase calculados solo con train.

Entrada: UP argmax y p_up >= 0,50. Holding mínimo 60 minutos, después salir cuando
deje de cumplirse la entrada; **no** se añade la regla de salida exclusiva por DOWN.
Falta de señal y final de semestre mantienen las excepciones ya documentadas al holding.

Cuatro folds expansivos: 2022 H1/H2 y 2023 H1/H2. Labels con final >= corte quedan purgados.
Se construyen variables únicamente con las velas del train original 2020–2023, pudiendo
usar historia previa al semestre para el warmup causal. No se evalúan 2024 ni test 2025–2026.
Los modelos de cada fold solo se ajustan con filas anteriores a ese fold.

## Criterio de decisión fijado por el usuario

**V2 debe obtener retorno neto estrictamente positivo en al menos 3 de los 4 semestres.**
Cero no cuenta como positivo. Se reportará también el número de semestres positivos
del control emparejado y las diferencias por semestre, sin añadir reglas de aceptación
después de ver resultados. Cumplir 3/4 sería superar este criterio de investigación,
no demostrar significación estadística ni autorizar trading real. Si el control emparejado
también mejora por el cambio de cobertura, se hará explícito.

Exposición, operaciones, media neta por operación, drawdown, comisiones, resultados
brutos y clasificación se registran como diagnósticos secundarios. No se seleccionan
features ni umbrales con ellos. Buy & Hold y efectivo sirven de referencias adicionales.

## Trazabilidad

Se conservarán el snapshot v1, un Parquet nuevo de features v2 de train, protocolo,
hashes de datos/código, versiones, cobertura, los ocho modelos (cuatro por brazo),
predicciones, objetivos de posición, operaciones, equity y comparativa en MLflow.
Las salidas van a un directorio nuevo. El protocolo se registra antes de los resultados.
