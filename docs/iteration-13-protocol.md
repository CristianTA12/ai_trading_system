# Preregistro — Iteración 13: target y holding de 4h con gate diario

Fecha: 2026-09-30. Registrar en Git antes de entrenar o evaluar estrategia.
Una sola receta y horizonte; sin barrido 4h/8h/24h. Costes, medias y criterio
permanecen fijos. No se descargan datos ni se evalúa 2024 o test 2025–2026.

## Hipótesis y límites de interpretación

Un objetivo y un holding más largos podrían capturar movimientos suficientemente
grandes para sobrevivir a las fricciones manteniendo el control de exposición
del gate diario. Se mide la combinación **target 4h + umbral de clases 100 pb +
holding 4h**, no el efecto aislado de uno de estos elementos.

La escala sqrt(16)=4 describe volatilidad bajo supuestos; no garantiza multiplicar
el retorno esperado de una señal ni el edge neto por cuatro. Los 100 pb fijan una
clase del target, no un beneficio esperado por operación. Un horizonte mayor no
garantiza menos pérdidas, mejor Sharpe ni menos operaciones. El gate puede cortar
una operación antes de 4h: las dos intervenciones son combinables, pero interactúan.

## Datos y features

Snapshot: `data/processed/btc-usdt-spot-15m-v1-2020-01-2026-08-20260925T164411092396Z`.
SHA-256 de `metadata.json`:
`a6a80da91f7956a49b5641038ae047b5422fba800a60fa1c7df23c7fd2b42c35`.
Verificar todos los Parquet contra los hashes de esa metadata. Loader `train_only`
filtra observaciones <2024; los hashes completos solo comprueban integridad.

**Las mismas 20 features v1, sin recalcular lookbacks ni añadir funding.**
Se sigue decidiendo cada 15 minutos. Cambia el horizonte de outcome y holding,
no se agregan velas de ejecución a 4h. Sin escaladores ni normalización aprendida.

## Target 4h y fronteras

El índice `t` de features es la apertura de ejecución, después del cierre de la
vela usada para features. Entrada `open[t]`, salida hipotética del label al cierre
de la vela abierta en `t+3h45m`; `label_end=t+4h`:

`target_return_4h[t] = close[t+15 barras] / open[t] - 1`.

Son 16 velas completas consecutivas. La expresión `close[t+16]/open[t+1]` solo
sería equivalente con un índice referido a la vela previa; aplicarla directamente
al índice de disponibilidad desplazaría incorrectamente la entrada 15 minutos.
No se puentean huecos. Labels sin las 16 velas son ausentes.

Clasificación tres clases: DOWN <−0,01; UP >+0,01; extremos e intervalo interior
son NEUTRAL. Control 15m conserva ±0,0025 y retorno `close[t]/open[t]-1`.

Folds 2022 H1/H2, 2023 H1/H2. Train expansivo desde 2020. Para todos los brazos,
purga común estricta `t+4h < frontera` en train y evaluación. La ausencia futura
de un label 4h excluye entrenamiento y scoring, **nunca una predicción/operación
de evaluación**. Mantener filas elegibles y velas completas del semestre; NaN
en outcomes de evaluación no implica señal ausente.

Los modelos 15m y 4h entrenan en idénticos timestamps con ambos targets presentes.
Se recalculan pesos de clase con cada target, exclusivamente en train; no pueden
ser iguales si la clase cambia. Evaluación comparte timestamps de predicción.

Medición de cobertura previa, sin entrenamiento ni métricas de estrategia:

| Fold | Train v1 original | Train común | Predicciones comunes | Outcomes 4h puntuables |
|---|---:|---:|---:|---:|
| 2022 H1 | 69.221 | 68.981 | 17.360 | 17.360 |
| 2022 H2 | 86.597 | 86.357 | 17.648 | 17.648 |
| 2023 H1 | 104.261 | 104.021 | 17.304 | 17.289 |
| 2023 H2 | 121.581 | 121.326 | 17.648 | 17.648 |

Se exige >=95% de cobertura train y predicciones respecto al v1 original, y >=95%
de disponibilidad del gate en cada fold. No se arrastra el recorte de 16 filas
del warmup funding: se parte de v1 y se aplica la máscara común nueva. Por ello
el control 15m se reentrena; no se reutilizan los resultados it.12 como si fueran
un control emparejado de este experimento.

## Modelos y brazos fijados

XGBoost tres clases `multi:softprob`, 500 árboles, profundidad 6, learning rate
0,05, subsample/colsample 0,8, hist CPU, cuatro workers. Sin early stopping ni
tuning. Pesos N/(3*N_clase) por train. Semillas **42, 123, 456, 789, 2026**.
40 modelos en total: uno 4h y uno 15m por fold/semilla. Los dos brazos 4h comparten
exactamente el mismo modelo y sus probabilidades.

| Brazo | Target/umbral | Holding mínimo | Gate | Función |
|---|---|---|---|---|
| `four_hour_regime` | 4h / ±100 pb | 240 min | Sí | Único candidato para promoción |
| `four_hour_control` | 4h / ±100 pb | 240 min | No | Aísla la política de régimen para 4h |
| `fifteen_min_regime` | 15m / ±25 pb | 60 min | Sí | Comparación emparejada del cambio de receta de horizonte |

Evaluar risk-return-v1 en los tres, pero no promover automáticamente un control
si el candidato falla. Cualquier selección distinta exige decisión/protocolo
propios. No elegir la mejor semilla ni mezclar folds.

## Gate y ejecución

Regla diaria de la iteración 12 sin cambios: SMA50 > SMA200; cierre de la vela
completa de 23:45 UTC, medias de días calendario consecutivos, NaN ante cierre
ausente. Disponibilidad a medianoche, elegibilidad estricta `< decision_at`,
primer uso a 00:15 y caducidad de 24h. Igualdad o dato ausente => gate cerrado.

Entrada UP argmax y p_up >=0,50. Holding mínimo medido en tiempo desde ejecución.
Después, salida si deja de cumplirse entrada. Señal ausente o gate cerrado fuerza
cash en la apertura observada, incluso antes del mínimo; al reabrir se exige
entrada nueva. Fin de fold liquida posiciones. El mínimo no fija la duración
máxima de una operación ni garantiza que retorno del trade coincida con su label.

Mismas velas spot de 15m, capital 10.000 USDT por fold, fracción 100%, long/flat,
sin apalancamiento ni posiciones entre folds. Mantener días y velas sin operar.
Benchmarks B&H y cash en base, y gate solo en bruto/base/stress, descriptivos;
no simular cinco semillas independientes para el gate determinista.

## Evaluación fija y artifacts

Taker 0,0004 por ejecución; slippage base 0,0001 y stress 0,0002. Escenario bruto
sin fees/slippage solo diagnóstico. Recalcular ejecuciones/equity con las mismas
predicciones, no aproximar costes ni suponer fills maker.

[risk-return-v1.yaml](risk-return-v1.yaml), SHA-256
`12398837a044bd1b4519e22c67cf4d8bd68616eb12580d56d6f48dde5fec638a`.
En >=4/5 semillas: compuesto base >0; DD <=15% por fold y concatenado; >=3/4
semestres con Sharpe > B&H y DD <= B&H, salvo excepción cash; compuesto stress >0.
Gate histórico solo diagnóstico. Cualquier cambio del criterio queda fuera.

Guardar protocolo/criterio, código/inputs/versiones/hashes, cobertura, labels
4h y máscaras, clases por train/fold, modelos UBJ y recarga exacta, predicciones
con outcomes puntuables y NaN, targets, gate, equity/fills/trades por escenario,
comparación, curvas concatenadas y tres veredictos. Registrar en MLflow local.
Verificar emparejamiento, label_end/purga, scoring separado de predicción, política
temporal y veredictos desde artifacts. Comparar edge bruto/neto por operación,
duración, exposición, rotación y consistencia, sin seleccionar variantes.

Si pasa, congelar receta y diseñar protocolo final; no abrir test automáticamente.
Si falla, registrar todas las semillas sin ajustar ventanas, umbrales o holding.
Estos folds ya han guiado decisiones: el preregistro de esta ejecución no hace
independiente la validación ni convierte semillas en muestras nuevas de mercado.
