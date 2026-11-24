# Sprint 12 — candidato táctil conservador (NO instalar)

## Estado

Después de la primera compilación de la fuente aislada M1+ Music 1.9.0 con Sprints 8 y 9, el build llegó al árbol y ejecutó 1,123 grupos de pruebas; 1,119 aprobaron y cuatro fallaron.

- `docs`: resuelto en la fuente local al recuperar el historial Git original y corregir una referencia. Se verificó `1,413/1,413`.
- `ipod/asset_tests`: resuelto regenerando **solo** el PNG de la rueda iPod con Pillow 13.0.0 en la Mac. Se verificó `25/25`.
- `albums/stock_widget_tests`: una expectativa antigua presupone que sin el hook se abrirá accidentalmente un álbum. TouchGuard debe impedirlo; corregir la prueba para comprobar el comportamiento, no saltársela.
- `scroll`: la doble llamada del primer MOVE introducida en Sprint 8 excede el presupuesto de 20 instrucciones (se midieron 26), y no está validada con AWTK real. **Separar temporalmente FirstMove de la primera build candidata**.

## Estrategia

Mantener TouchGuard y el perfilador de Sprint 9; retirar solo la doble-dispatch FirstMove y su registro global; adaptar la expectativa de Albums para que con/sin el hook rechace aperturas accidentales. Ejecutar pruebas dirigidas y el build entero antes de avanzar a una actualización.

El paquete de aplicación local `Mochi_OS_Sprint12_Safe_TouchGuard.zip` se entregó en la conversación. Es un script de fuente **dry-run por defecto**, con guardas de estructura y respaldos; no contiene `update.bin`. No se ha ejecutado aún el test integral de MIPS después de ese cambio en la Mac del usuario.

**La rama y su nota son experimentales y no autorizan merge, flash ni distribución de firmware.**
