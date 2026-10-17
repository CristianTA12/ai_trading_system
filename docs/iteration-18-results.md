# It.18 — Decisiones cada 4h: menos rotación, menor retorno

Fecha: 2026-10-17. **Rechazada: 0/5 semillas frente a 2/5 del control.**
Se requieren 4/5. Preregistro `cd34886`, implementación `8eb3046`, ambos
anteriores a evaluar el candidato. [Protocolo](iteration-18-protocol.md).

La única intervención fue consultar la señal en una rejilla UTC de cuatro
horas. Probabilidades de it.13 congeladas, sin entrenamiento. Gate y salidas
por ausencia de señal inmediatos; criterio, costes, umbral y universo sin cambios.

## Resultado emparejado

| Semilla | Control neto compuesto | Rejilla neto | Rejilla stress | Rejilla DD concatenado | Consistencia |
|---|---:|---:|---:|---:|---:|
| 42 | +20,19% | +10,38% | +9,92% | 9,58% | 2/4 |
| 123 | +19,70% | +10,45% | +9,97% | 7,64% | 2/4 |
| 456 | +29,90% | +6,52% | +6,12% | 11,80% | 2/4 |
| 789 | +14,58% | +7,55% | +7,06% | 7,65% | 2/4 |
| 2026 | +26,29% | +8,15% | +7,63% | 4,14% | 2/4 |

Cinco semillas pasan rentabilidad, riesgo y stress. Cero pasan consistencia;
no se cambia el benchmark para aprobar menor exposición. No se elige una semilla.

| Métrica | Control | Rejilla 4h |
|---|---:|---:|
| Operaciones, suma de cinco semillas y cuatro folds | 697 | 109 |
| Compuesto bruto, rango entre semillas | +31,27% a +50,02% | +8,57% a +12,91% |
| Compuesto neto, rango entre semillas | +14,58% a +29,90% | +6,52% a +10,45% |
| Exposición media por fold/semilla | 3,23% | 0,54% |
| Semillas que cumplen todo | 2/5 | 0/5 |

La rotación baja **84,36%**, pero cae el retorno bruto en 5/5 y el neto en 5/5.
El ahorro de costes no compensa lo que deja de capturar esta política.
Las operaciones agregadas son un descriptor, no una cartera conjunta.

## Lectura por semestre

Medias aritméticas entre semillas, sin seleccionar ninguna:

| Fold | Retorno control | Retorno rejilla | Trades control | Trades rejilla |
|---|---:|---:|---:|---:|
| 2022 H1 | +1,92% | +0,81% | 16,4 | 0,6 |
| 2022 H2 | 0% | 0% | 0 | 0 |
| 2023 H1 | +9,48% | +5,56% | 77,8 | 15,2 |
| 2023 H2 | +9,55% | +2,07% | 45,2 | 6,0 |

Reducir decisiones no prolongó suficientemente exposición útil: la cadencia
también restringe cuándo puede entrar el modelo. La media de exposición pasó
de 7,29% a 1,49% en H1 2023, y de 4,10% a 0,60% en H2. No se afirma que
otra fase de reloj hubiera arreglado el problema, ni se probará para comprobarlo
retrospectivamente. La rejilla elegida queda descartada conforme al preregistro.

## Qué cambia en el diagnóstico

El [diagnóstico de selección bruta](classifier-value-diagnostic.md) sigue siendo
válido para la política original. It.18 añade evidencia contra una solución
concreta: reducir la frecuencia de decisión a la del target no conserva ese valor.
No demuestra que todos los métodos de control de rotación sean inútiles, ni que
el clasificador tenga edge fuera de muestra. El resultado es desarrollo adaptativo
sobre folds muy reutilizados, no una prueba independiente.

**Decisión:** cerrar it.18, mantener it.13 rechazada y no lanzar otra variante
de holding, rejilla o umbral. No añadir fuentes, features o arquitectura para
rescatar esta prueba. Una nueva intervención necesitaría una justificación
adicional concreta; estos resultados no la proporcionan por sí solos.

## Verificación y artefactos

- Los 60 backtests del control coincidieron exactamente en targets, equity,
  fills y trades con it.13, antes del primer candidato. Su veredicto también coincide.
- 60 backtests candidatos y ocho benchmarks: **128 en total; cero modelos nuevos**.
- Targets candidatos contrastados con una reconstrucción independiente de estado.
- **59 tests** relevantes pasados: política, gate y evaluador.
- Revisión posterior: **432 archivos** del manifiesto verificados, 128 juegos
  de métricas recalculados desde artefactos y ambos veredictos reproducidos.
  Esta revisión no ejecuta backtests adicionales; comparte funciones de métricas
  y evaluador con el runner, sin presentarse como un motor de ejecución independiente.
- No se deserializó 2024 ni el test 2025–2026. El loader verificó hashes completos
  de archivos y cargó únicamente la partición anterior a 2024.

Carpeta: `data/experiments/iteration-18-20261017-decision-grid`.
MLflow: experimento 22, run `f6ba3e231ebb4c83a56021cd920ef6a5`.
Verificador: `scripts/verify_decision_grid_experiment.py`.
Revisión y documentación complementaria en `data/experiments/iteration-18-review-20261017`.
No se promueve receta, abre test reservado ni inicia captura o trading.
