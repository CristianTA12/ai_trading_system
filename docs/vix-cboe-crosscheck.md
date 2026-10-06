# Contraste con Cboe: valores confirmados, disponibilidad histórica pendiente

Fecha: 2026-10-06. Continuación del [contraste API FRED](vix-api-crosscheck.md).

**Los 1.059 cierres actuales de Cboe coinciden exactamente con FRED en
2019-11-01–2023-12-31.** Las doce fechas presentes en las vintages futuras
también existen en Cboe, con el mismo valor y distinto del cierre anterior.
No hay evidencia de que sean valores inventados por FRED ni mero arrastre del
día anterior. La inconsistencia pendiente es su disponibilidad histórica.

## Evidencia cuantitativa

| Comparación | Resultado |
|---|---:|
| Cierres Cboe en la ventana | 1.059 |
| Observaciones FRED no nulas | 1.059 |
| Fechas/valores no nulos diferentes | 0 |
| Fechas anómalas confirmadas en Cboe | 12/12 |
| Anómalas diferentes del cierre Cboe anterior | 12/12 |
| Cierre Cboe 2021-04-16 | 16,25 |

El CSV oficial actual del 16-01-2023 contiene apertura 19,44, máximo 19,63,
mínimo 19,41 y cierre 19,49. El viernes 13 cerró en 18,35. El dato del lunes
no es una repetición del viernes. La API ALFRED, sin embargo, ya devuelve
19,49 fechado el lunes dentro de la vintage del viernes.

Fuente del snapshot: [histórico oficial Cboe](https://www.cboe.com/tradable_products/vix/vix_historical_data),
[CSV diario](https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv).
La coincidencia se refiere a dos snapshots actuales; no son dos pruebas
independientes de publicación histórica, pues FRED redistribuye la serie Cboe.

## Calendario: VIX no debe heredar el calendario de acciones

El aviso Cboe C2023010300 documenta negociación GTH de opciones SPX/VIX/XSP
desde el domingo 15 de enero de 2023 a las 20:15 ET hasta el lunes 16 a las
11:30 ET, sin sesión regular ese lunes. Las bolsas de acciones del aviso
estaban cerradas. Esto acredita actividad de opciones durante ese festivo,
no la hora de publicación del cierre del CSV.
[Aviso contemporáneo Cboe](https://cdn.cboe.com/resources/schedule_update/2023/Cboe-Holiday-Reminder-Modified-Trading-Hours-on-Monday-January-16-2023.pdf).

La metodología fechada 20-03-2023 contempla cálculo y difusión de VIX tanto
en RTH como en GTH y ajustes por sesiones reducidas. Es coherente con que
exista VIX cuando no hay cierre del S&P 500; no permite trasladar el dato del
lunes al viernes anterior. Tampoco se ha verificado individualmente el aviso
histórico de cada uno de los otros once festivos.
[Metodología Cboe 2023, página 4](https://res-certification.cboe.com/api/global/us_indices/governance/Volatility_Index_Methodology_Cboe_Volatility_Index.pdf).

**Inferencia limitada:** la discrepancia de calendarios tiene una explicación
plausible en GTH. La asignación de las vintages ALFRED sigue sin explicación
demostrada. No se corrigen fechas ni se adjudica una causa interna al proveedor.

## Decisión y siguiente paso

- Mantener VIX/ALFRED **no aprobado con el protocolo actual** y conservar las
  30 cuarentenas. Cboe confirma valores, no cuándo estaban disponibles en FRED.
- No sustituir automáticamente las vintages por el CSV actual de Cboe: faltaría
  acreditar revisiones y disponibilidad histórica de ese archivo.
- No cambiar el lag ni la caducidad para recuperar el 95% de cobertura.
  La medición anterior de 2023 H1 sigue en 93,34% bajo sus supuestos.
- Cerrar este diagnóstico VIX y pasar a auditar disponibilidad histórica de
  S&P 500 mediante la API oficial ya habilitada. Un fallo del endpoint público
  ALFRED no basta para concluir que la API carece de esa información.

Si se desea retomar VIX con un supuesto temporal nuevo, requerirá documentar
un protocolo distinto antes de cualquier entrenamiento. Esta investigación
no ha entrenado modelos, ejecutado backtests ni evaluado los folds reservados.

## Reproducción y custodia

Artifacts: `data/external/vix-cboe-audit-20261006/` contiene el CSV acotado,
metadatos de descarga con hash completo y acotado, comparación completa,
doce casos anómalos e informe JSON. El endpoint entrega todo el histórico:
se recibió en memoria, se filtró por fecha y solo se conservaron e interpretaron
valores de 2019-11-01–2023-12-31. No se afirma que la descarga estuviera acotada
en el servidor. No se analizaron valores externos a esa ventana.

**37 tests dirigidos pasan**. Se validan unicidad, orden, límites temporales,
integridad OHLC y exclusión de valores fuera de ventana antes de interpretarlos.

```bash
python -m scripts.audit_vix_cboe data/external/vix-cboe-audit-20261006
# Para una captura nueva:
python -m scripts.audit_vix_cboe data/external/<carpeta-nueva> --fetch \
  --curl-executable /mnt/c/Windows/System32/curl.exe
```
