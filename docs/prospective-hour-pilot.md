# Validación en vivo de una hora completa — 2026-10-14

Seguimiento: [primer intento interrumpido y recuperación parcial](prospective-hour-pilot-interruption.md),
revisado el 2026-10-15. No completó la hora objetivo.
El [segundo intento completó la hora](prospective-hour-pilot-results.md),
con verificación adicional el 2026-10-16.

El runner `src.data.collectors.hour_pilot` captura desde su arranque hasta
30 segundos después del final de la siguiente hora UTC completa. La duración
planificada es entre 3.630 y 7.230 segundos. El collector v2 admite un máximo
de 7.500 segundos; su duración por defecto sigue siendo 600 segundos.
Mantiene límite de 50 MB, tres intentos y parada automática, sin servicio
persistente ni arranque automático. No modifica el reloj.

```powershell
python -m src.data.collectors.hour_pilot --output data/prospective/nuevo-piloto-horario
```

La carpeta debe ser nueva. `plan.json` registra el objetivo UTC, duración,
presupuestos y hashes de los módulos de revisión. `capture/` contiene la sesión
raw con su manifiesto propio y hash del collector ejecutado.

Al finalizar, el runner verifica esa captura y escribe fuera de ella:

- `verification.json`: integridad y replay por recepción.
- `aggregates.json`: barras disponibles al cierre y hash del manifiesto raw.
- `result.json`: resultado de la validación de la hora objetivo.
- `review_manifest.json`: hashes de todos esos archivos y la captura.

El resultado técnico exige una barra completa para la hora objetivo, parada
por duración, cero mensajes inválidos y cero saltos detectados de reloj mayores
de un segundo. Los huecos fuera de esa hora siguen visibles en `capture/report.json`;
el resultado no significa que toda la sesión carezca de huecos. No exige que
Windows declare sincronización ni acredita latencia absoluta. Salida 0 si cumple
y 2 si no; errores inesperados dejan `failure.json` y una salida de error.

La suspensión del equipo, pérdida de red o cierre forzado pueden impedir
completar la hora. No se rellena con REST ni datos históricos, ni se relanza
para ocultar el fallo. Si el proceso se interrumpe de forma abrupta puede no
existir informe final. La ausencia de `result.json` no es un resultado exitoso.

Seis casos de prueba cubren planificación en los extremos de hora, criterio de
resultado y límite máximo, además de los tests de captura y agregación.
No se entrenan modelos, se evalúa PnL ni se envían órdenes. El propósito es
comprobar el pipeline con una hora completa real; no validar una estrategia.
