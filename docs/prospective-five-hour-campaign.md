# Campaña acotada de cinco horas — 2026-10-16

Autorizada para este PC durante su disponibilidad de más de cinco horas.
Runner: `python -m src.data.collectors.campaign --output CARPETA_NUEVA`.
Presupuesto monotónico global de 18.000 segundos; máximo tres sesiones,
las dos primeras de hasta 7.200 segundos y la última con el tiempo restante.
El cierre y la revisión final pueden añadir algunos segundos al plazo.

Máximo 50 MB por captura, 150 MB entre las tres; informes derivados ocupan
espacio adicional. No hay servicio persistente, arranque automático ni cambios
de energía. Cada sesión guarda su propio manifiesto. La revisión guarda los
agregados y verificación fuera de esa sesión. No se rellenan huecos ni se unen
sesiones para fabricar continuidad: el cierre/revisión/reconexión introduce
una interrupción entre bloques y puede impedir alguna barra completa.

`plan.json` identifica duración y hashes del código. `progress.json` enumera
sesiones completadas; `result.json` aparece al terminar. Un error inesperado
deja `failure.json`. Un corte abrupto puede no dejar ninguno de los dos últimos;
no debe interpretarse como éxito. La campaña se detiene si una sesión acaba
por fallo, límite de bytes o solicitud del usuario. La integridad se verifica
por sesión; finalizar no implica automáticamente cobertura sin huecos.

Para solicitar parada anticipada, crear el archivo `STOP` en la carpeta de
campaña, fuera de las subcarpetas `session-XX`. Esperar al cierre antes de apagar.
No eliminar ni editar archivos de las capturas. No se relanza automáticamente
una campaña fallida. Tres pruebas del runner validan límites temporales,
máximo de sesiones y parada ante fallo/solicitud; diez tests del collector pasan.

Esta campaña recoge calidad de datos; no entrena modelos, envía órdenes ni
consulta el test histórico reservado. La precisión absoluta del reloj sigue
sin acreditarse y no bloquea la recogida.
