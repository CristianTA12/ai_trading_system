# Preregistro — Iteración 14: clases 4h ±75 pb frente a ±100 pb

Fecha: 2026-10-05. Registrar en Git antes de entrenamiento/evaluación nuevos.
Única intervención: umbral de clases 0,0075 en vez de 0,01. No barrido ni
alternativa de 50 pb si falla. Motivación: comprobar si una definición menos
extrema del movimiento mejora la selección económica; el diagnóstico previo
no demuestra que el umbral sea la causa del fallo ni que 75 pb sea óptimo.
Se elige el menor cambio entre las dos alternativas del plan, sin resultados
de modelos entrenados a 50/75 pb. Investigación adaptativa sobre folds ya vistos.

## Receta congelada

Heredar íntegramente [it.13](iteration-13-protocol.md): snapshot y su hash,
20 features v1, decisiones cada 15m, target `close(t+3h45m)/open(t)-1`,
16 barras consecutivas, `label_end=t+4h`, mismas filas train/evaluación y purga
estricta. NaN de outcome excluye scoring, nunca predicción/operación.
Train expansivo desde 2020; folds 2022 H1/H2 y 2023 H1/H2. Sin consultar
2024 ni test 2025–2026. Cobertura >=95% por fold como it.13.

XGBoost mismo código/hiperparámetros: 500 árboles, profundidad 6, learning rate
0,05, subsample/colsample 0,8, hist CPU, 4 workers; sin tuning ni early stopping.
Semillas 42,123,456,789,2026. DOWN <-0,0075, UP >0,0075; extremos NEUTRAL.
Recalcular pesos N/(3*n_clase) exclusivamente en train: cambia la clase, no
la regla de ponderación. Esta intervención incluye ese cambio de pesos implícito.

Entrada argmax UP y p_up>=0,5. Gate diario SMA50>SMA200 causal, sin cambios.
Holding mínimo 240 min, salida posterior si deja de cumplirse entrada;
gate cerrado/señal ausente fuerza cash incluso antes. Sin cooldown. Fin de fold
liquida. Capital 10.000 por fold, long/flat 100%, sin apalancamiento.
Taker 0,0004 por lado, slippage base 0,0001/stress 0,0002; bruto cero fricción.

## Candidato y control emparejado

- `threshold_75_regime`: único candidato, 20 modelos nuevos.
- `threshold_100_regime`: control congelado de `four_hour_regime` it.13,
  artifacts `data/experiments/iteration-13-20260930-four-hour`.
  Reutilizar sus 20 modelos/predicciones; no seleccionar semillas.

Antes de entrenar: verificar it.13, librerías, hashes de snapshot/labels/gate,
filas train y predicciones exactamente iguales; recargar cada modelo control
y exigir probabilidades idénticas sobre las features actuales. Si difieren,
abortar, no sustituir silenciosamente el control. Registrar SHA256 de los
artifacts fuente usados. Reejecutar ambos brazos con el mismo motor y exigir
que el control reproduzca exactamente equity/fills/trades de it.13 en los tres
escenarios. Son 120 backtests de brazos, más B&H/cash base por fold (8).
El benchmark gate solo ya existe; no hace falta volver a simularlo.

## Veredicto fijo

`risk-return-v1.yaml` SHA256
`12398837a044bd1b4519e22c67cf4d8bd68616eb12580d56d6f48dde5fec638a`.
En >=4/5 semillas: compuesto base >0, DD<=15% por fold y concatenado,
>=3/4 folds con Sharpe>B&H y DD<=B&H (excepción cash vigente), stress compuesto>0.
Sin cambiar benchmark/criterio ni elegir semillas. Aprobar H1 no es un criterio
aislado ni sustituye los cuatro folds. Evaluar ambos brazos, sin promover control.
Si candidato pasa, congelar y diseñar protocolo final; no abrir test automáticamente.
Si falla, registrar rechazo sin probar otro umbral en esta iteración.

## Evidencia y trazabilidad

Guardar modelos, predicciones, clases/pesos implícitos, importancias, targets,
equity/fills/trades bruto/base/stress, métricas, curvas concatenadas, cobertura,
protocolo, versiones, commits y hashes. MLflow local, carpeta nueva sin sobrescribir.
Verificación independiente: reproducción exacta del control, política causal,
retornos/Sharpe/DD y criterio recalculados desde artifacts, modelos recargables.
Comparar descriptivamente exposición, entradas, edge bruto/neto, consistencia y
variación entre semillas. No interpretar más UP como mejora económica por sí misma.

El diagnóstico y este preregistro no convierten los folds usados repetidamente
en un holdout independiente. No se modifica el plan original ni se declara
completa la consolidación general del runner de fase B.
