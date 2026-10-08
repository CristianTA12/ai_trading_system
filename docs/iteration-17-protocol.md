# Preregistro it.17 — Flujo agresor sobre receta BTC 4h

Fecha: 2026-10-08. Congelar antes de implementar y entrenar. La prueba
determinista de momentum diario fue un screening de arquitectura, no it.17.

## Hipótesis y alcance

El desequilibrio de volumen negociado por agresores compradores/vendedores
puede añadir información sobre presión negociadora ausente del volumen total
de v1. Comparar un único paquete de dos features, sin seleccionar ventanas,
features ni semillas después de observar rentabilidad. No combinar macro,
funding, momentum semanal ni la salida DOWN rechazada en it.16.

Investigación condicionada: asumir que los volúmenes históricos congelados
representan los observables en vivo y se reciben dentro de los 15 minutos
posteriores al cierre del agregado. El timestamp de recepción histórica no
existe en los archivos. El margen no es prueba de latencia y no elimina el
riesgo de revisiones. La continuación solicitada permite esta investigación
con la limitación documentada, sin declarar causalidad histórica acreditada.

## Datos, filas y features

Preparación `data/processed/aggressor-flow-preparation-20261008`, commit
`54dd56f`. Verificar todos los hashes de su manifiesto antes y después;
contrastar fórmulas con verificador escalar y raw con auditoría ya congelada.
BTC snapshot it.13: metadata SHA256
`a6a80da91f7956a49b5641038ae047b5422fba800a60fa1c7df23c7fd2b42c35`.
Solo 2020–2023. No leer/evaluar 2024 ni test 2025–2026.

Candidato `flow_regime`: 20 v1 + `flow_imbalance_15m` y `flow_imbalance_1h`.
Control `v1_regime`: solo 20 v1. Definiciones exactas en
[preparación](aggressor-flow-preparation.md): último agregado
[t−30min,t−15min), hora [t−75min,t−15min); ratio de sumas, no media de ratios.
Huecos/denominador cero invalidan, sin rellenado ni arrastre de barras viejas.

Filas comunes train: 68.981 / 86.357 / 104.021 / 121.326.
Evaluación: 17.360 / 17.648 / **17.302** / 17.648.
Orden: 2022 H1/H2, 2023 H1/H2. Solo dos filas de evaluación H1 se excluyen
por flujo no elegible. Mantener todas las barras de ejecución, forzando cash
si no hay señal, en ambos brazos. Ausencia de outcome futuro no elimina
predicciones elegibles: solo excluye train/scoring. Cobertura mínima ≥95%.

**Reentrenar ambos brazos**, 20 modelos cada uno, mismas semillas
42,123,456,789,2026. No reutilizar métricas it.13 como control emparejado.
Como train v1 no cambia, contrastar sus probabilidades con it.13 sobre el
subconjunto común como comprobación de reproducibilidad, no copiar backtests.

## Receta congelada

Target retorno close(t+3h45m)/open(t)−1, 16 barras consecutivas; label_end=t+4h.
Purga estricta antes de fronteras; clases DOWN<−1%, UP>1%, extremos NEUTRAL.
XGBoost 500 árboles, depth6, lr0,05, subsample/colsample0,8, hist CPU,
cuatro workers, pesos N/(3*n_clase) calculados solo en train. Sin tuning,
calibración ni early stopping. Entrada UP argmax y p_up≥0,5; mantener el
gate causal SMA50>SMA200 y política it.13 de holding mínimo240min; después,
salir si desaparece condición de entrada. Gate cerrado/ausente o predicción
ausente fuerza cash incluso dentro del mínimo. Sin cooldown ni apalancamiento.
Long/flat100%, capital10.000 por fold, liquidación final; taker0,0004/lado,
slippage base0,0001/stress0,0002; bruto sin fricción. B&H/cash mismas barras.
40 modelos, 120 backtests de brazos + ocho benchmarks = 128.

## Criterio, integridad y parada

`risk-return-v1` inalterado, SHA256
`12398837a044bd1b4519e22c67cf4d8bd68616eb12580d56d6f48dde5fec638a`.
≥4/5 semillas deben cumplir compuesto base>0, DD≤15% en cada fold y
concatenado, consistencia en ≥3/4 folds (Sharpe>B&H y DD≤B&H, excepción cash
vigente), compuesto stress>0. H1 no se convierte en requisito separado.
Evaluar ambos brazos y reportar cambios emparejados, incluso si empeoran.

Si falla, cerrar el paquete sin barrer lags, ventanas, holding o umbrales.
Si pasa, solo candidato exploratorio condicionado: no abrir automáticamente
test, paper ni live. Los folds son desarrollo reiteradamente consultado.

Guardar protocolo/commits, versiones, hashes, features, filas, 40 modelos,
predicciones, targets, equity/fills/trades, métricas/veredictos y MLflow.
Verificar recarga de modelos, predicciones comunes, política mediante replay
escalar independiente, métricas y evaluador desde artifacts. Abortos técnicos
se documentan; no cambiar receta económica ni sustituir semillas para rescatar.
