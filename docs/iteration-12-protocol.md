# Preregistro — Iteración 12: filtro diario SMA50 > SMA200

Fecha: 2026-09-29. Registrar en Git antes de calcular resultados de estrategia.
Intervención elegida tras la revisión del arquitecto: filtro explícito de régimen,
sin modificar features, target, modelo, probabilidades, umbrales ni costes.

## Hipótesis y alcance

Permitir largos solo cuando SMA50 diaria > SMA200 diaria podría evitar parte de
las operaciones desfavorables de v1 y mejorar riesgo/rentabilidad netos. Se prueba
una única regla, sin optimizar ventanas, añadir condición de precio ni elegir
la dirección del cruce según resultados. Una serie lenta puede servir de contexto
para decisiones rápidas; su frecuencia por sí sola no demuestra utilidad o inutilidad.

No se presupone que long-only deba perder en cada mercado bajista, ni que los
rechazos anteriores identifiquen exclusivamente la estrategia como causa. El
informe recibido invierte la desigualdad en una tabla: aquí la regla elegida
es explícitamente **SMA50 > SMA200**. Nunca se asigna cash retrospectivamente a
un semestre usando su retorno conocido. Tampoco se reducen costes por suponer
órdenes maker con fills garantizados.

## Datos y construcción causal

- Mismo snapshot spot v1 que la iteración 11. Solo se deserializan datos <2024.
- Cierre diario UTC: cierre de la vela completa de 15m abierta a las 23:45.
  No se necesita el volumen ni el resto de OHLC diarios; huecos intradiarios
  no invalidan un cierre final observado. Si falta esa vela, el día es NaN.
- SMA50 y SMA200 aritméticas sobre 50/200 días calendario consecutivos, con
  todos sus cierres presentes. Sin interpolación ni medias de solo días disponibles.
  Un cierre ausente invalida las ventanas que lo contienen.
- El cierre diario pasa a estar disponible a las 00:00 siguientes. Exigir
  `daily_available_at < decision_at`: primera aplicación a las 00:15 UTC.
  A las 00:00 sigue vigente el valor del día anterior si aún tiene <=24h de edad.
- As-of hacia atrás con caducidad 24h desde disponibilidad. Igualdad válida.
  Gate abierto solo con medias válidas y SMA50 estrictamente mayor que SMA200.
  Igualdad, ausencia, warmup o caducidad => cash. Ningún dato futuro decide el gate.
- Warmup comienza en enero 2020 y no recorta entrenamiento: el gate es una
  política externa, no feature ni selector del train. La comprobación previa
  de disponibilidad (sin retornos de estrategia) dio **100% de cobertura** en
  los cuatro folds: 17.376 / 17.664 / 17.370 / 17.664 velas de ejecución.
  Exigir >=95% por fold; guardar cobertura separada de fracción de gate abierto.

## Modelos congelados y control

Reutilizar los 20 modelos/predicciones `v1_matched` de
`data/experiments/iteration-11-20260929-funding`. Fuente: commit `9ccd153`,
semillas **42, 123, 456, 789, 2026**, cuatro folds 2022 H1/H2, 2023 H1/H2.
El manifiesto [iteration-12-inputs.json](iteration-12-inputs.json) fija 244 hashes
de metadata, receta, cobertura, veredicto y archivos de modelos/predicciones/
targets/equity/fills/trades. Comprobarlos antes de evaluar.

No se vuelve a entrenar. Los modelos v1 originales usan train expansivo purgado
y la máscara de la iteración 11 (16 filas iniciales excluidas). Funding no es
predictor de estos modelos ni se incorpora ahora. No se comparan con un control
de cobertura diferente. Recargar UBJ, reproducir probabilidades con las 20 features
v1 y comprobarlas exactamente contra el archivo. Comprobar también retornos y
fechas de predicciones contra los folds actuales, y reproducir los targets/equity
del control. La política nueva recibe las mismas predicciones, fechas y velas.

## Brazos y ejecución

1. **`v1_control`**: mismas predicciones UP argmax y `p_up >=0,50`, holding mínimo
   60 minutos; después sale si deja de cumplirse entrada. Reproduce iteración 11.
2. **`v1_regime`**, único candidato: entrada como control y gate abierto;
   mientras gate abierto mantiene la política hold_60m. Si gate se cierra o falta
   señal, efectivo en la apertura observada, incluso dentro de los 60 minutos.
   Gate reabierto exige nueva entrada elegible y reinicia el reloj del holding;
   no se multiplica la posición latente del control por un filtro.
3. **`regime_only`**, diagnóstico determinista: 100% long cuando gate abierto,
   efectivo cuando cerrado. Sin XGBoost ni holding mínimo. Guardar base/bruto/stress.
   No tratar cinco copias idénticas como estabilidad multi-semilla ni promover
   esta referencia automáticamente: su selección exigiría un protocolo propio.
4. Buy & Hold y cash, costes base, mismas velas, como referencias.

Conservar todas las fechas y velas. No acortar semestres. Liquidación al final
de cada fold, 10.000 USDT iniciales, spot long/flat, fracción 100%, sin posiciones
entre folds. Las excepciones del gate pueden producir trades de menos de 60m.

## Criterio fijo y escenarios

[risk-return-v1.yaml](risk-return-v1.yaml), sin cambios; SHA-256
`12398837a044bd1b4519e22c67cf4d8bd68616eb12580d56d6f48dde5fec638a`.
Base: taker 0,04% y slippage 0,01% por ejecución. Stress: slippage 0,02%.
Bruto: ambos cero, solo diagnóstico. Recalcular capital/fills con las mismas
señales para cada escenario; no restar costes a posteriori.

Promoción del candidato solo si >=4/5 semillas cumplen conjuntamente retorno
compuesto >0, DD <=15% por fold y concatenado, consistencia >=3/4 contra B&H
con la excepción cash del criterio, y compuesto stress >0. El control recibe
el mismo evaluador; su veredicto debe reproducir el anterior. No añadir un gate
favorable tras observar resultados. Gate histórico >=3/4 positivos solo referencia.

## Diagnósticos, artifacts e interpretación

Guardar manifiesto/receta/criterio, commits/hashes/versiones, estados diarios y
gate por barra, cobertura, fracción gate abierto y cambios por fold, predicciones
fuente y targets, modelos por referencia con hashes, operaciones/fills/equity,
métricas bruto/base/stress, comparación CSV, curvas concatenadas y veredictos.
Registrar en MLflow local. Verificar resultados reconstruyendo métricas y decisión
desde artifacts, igualdad del control y ausencia de posición con gate cerrado.

Analizar descriptivamente exposición, número/duración de operaciones y diferencias
contra control y filtro solo. Menor exposición no prueba mejor selección. Cash
en un semestre no garantiza pasar rentabilidad ni consistencia frente a un B&H
positivo. Un cruce de medias retrasado no es un clasificador perfecto de régimen.

**2024 no se reevalúa; test 2025–2026 reservado.** Este protocolo es prospectivo
respecto a esta ejecución, pero la hipótesis nace de los mismos folds explorados;
no elimina selección acumulada ni demuestra significación independiente.
Si pasa, congelar y diseñar validación final, sin abrir test automáticamente.
Si falla, documentar todas las semillas, sin ajustar SMA ni añadir condiciones.
El horizonte 4h–24h queda para otra iteración y otro preregistro, cualquiera que
sea el resultado de esta; no se elige aquí umbral/target por resultados de esta prueba.
