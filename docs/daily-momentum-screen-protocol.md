# Fase F — Prueba de arquitectura: momentum diario

Fecha: 2026-10-08. Se cierra la familia it.13–16; se mantiene el mandato
de superar B&H con riesgo controlado. Esta prueba no entrena modelos y no
es una iteración candidata a promoción.

## Hipótesis y elección

Hipótesis: una regla de persistencia de retornos diarios puede capturar
movimientos sostenidos con menos decisiones que el clasificador intradía.
Primero se mide la regla simple; no se presupone que ML añada valor.
La ventana de siete días representa una semana natural de BTC 24/7 y se
fija por simplicidad, sin haber calculado su rendimiento en estos folds.
No procede de una optimización ni es una réplica exacta de un paper.

[Liu y Tsyvinski, 2018](https://www.nber.org/papers/w24877) documentan
momentum temporal en criptomonedas. Es motivación externa, no validación
de esta implementación, periodo, costes o límite de riesgo.
Se posponen modelos más grandes, macro, microestructura, shorts y sizing
dinámico: no hacen falta para responder esta pregunta delimitada.

## Regla congelada antes de implementar

- Cierre diario C[d]: cierre de la barra observada de 23:45 UTC del día d.
- Señal: C[d]/C[d−7]−1 > 0 implica long; cero o negativo implica cash.
- Exigir los ocho cierres diarios consecutivos; si falta alguno, cash.
- Disponibilidad: d+1 a las 00:00 UTC; unión as-of estricta (<), con edad
  máxima de un día. Primer uso normal a las 00:15 UTC. A medianoche sigue
  vigente la señal anterior. No anticipar el cierre ni rellenar días ausentes.
- Long/flat al 100%, sin gate adicional, holding mínimo, stop, umbral de
  confianza, escalado por volatilidad ni apalancamiento. Cambiar posición
  al siguiente open observado con señal elegible; liquidar al final de fold.
- Controles: B&H, cash y SMA50>SMA200 diario sin clasificador, usando
  `daily_regime` existente. Las cuatro estrategias usan todas las mismas
  barras observadas de cada semestre, sin filtrar por labels/features.

## Datos y ejecución

Snapshot BTC v1 `20260925T164411092396Z`; SHA256 de metadata
`a6a80da91f7956a49b5641038ae047b5422fba800a60fa1c7df23c7fd2b42c35`.
`load_dataset(train_only=True)` verifica hashes y limita las observaciones
a 2020–2023. No evaluar 2024 ni test 2025–2026. Warmup desde 2020.
Folds 2022 H1/H2, 2023 H1/H2; capital 10.000 por fold, sin posiciones
heredadas. Ejecución y métricas existentes, 15m para valorar equity y
retornos diarios UTC para Sharpe. Costes taker 0,0004 por lado, slippage
base 0,0001 y stress 0,0002; bruto sin fricción. 48 backtests:
cuatro estrategias × cuatro folds × tres escenarios. Cero semillas/modelos.

## Lectura y parada

Aplicar los gates económicos existentes: compuesto base>0, DD≤15% por
fold y concatenado, consistencia Sharpe/DD contra B&H en ≥3/4 folds
(misma excepción cash), compuesto stress>0. Reutilizar el evaluador de
una trayectoria, indicando que su identificador interno no es una semilla.
`risk-return-v1` permanece intacto, hash
`12398837a044bd1b4519e22c67cf4d8bd68616eb12580d56d6f48dde5fec638a`.
La estabilidad entre semillas no aplica y NO se considera satisfecha.
Nunca producir un aprobado global ni duplicar una trayectoria cinco veces.

Si falla cualquier gate económico, cerrar esta regla semanal, sin probar
otras ventanas, añadir SMA o ajustar sizing para rescatar el resultado.
No inferir que toda estrategia diaria o todo momentum es imposible.
Si pasa, solo justifica diseñar validación prospectiva de la arquitectura;
no abre test, paper ni live. Cualquier comparación futura con ML requiere
preregistro propio y demostrar aportación frente a esta regla simple.

Estos folds ya se han consultado reiteradamente: incluso un resultado
favorable sería exploratorio. Registrar resultados completos, exposición,
operaciones y verificación escalar independiente de las señales, sin elegir
el mejor semestre. Comprobar el protocolo registrado y código limpio antes
de ejecutar, conservar artifacts en directorio nuevo y registrar en MLflow.
