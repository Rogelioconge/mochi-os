# Mochi OS — Sprint 9: medición de latencia en Songs y Albums

**Estado: código de diagnóstico en borrador. NO instalar un firmware ni fusionar esta rama por ahora.**

Esta rama parte de `experiments/m1plus-190-sprint8-albums-scroll`, cuya fuente base es `imfing/m1plus-music` **1.9.0**.

## Qué se implementó

Los archivos `songs.c.patch` y `albums.c.patch` se aplican a las versiones de `patch/songs.c` y `patch/albums.c` **después** de aplicar Sprint8, e incluyen `mox_perf.h`. El perfilador mide:
- **Songs:** tiempo de `sg_load`, lecturas `cc_albums` y `sg_query`, preparación del índice, pintura de filas, carga de portadas y eventos de desplazamiento.
- **Albums:** apertura inicial después de crear la ventana, pintura de cuadrícula/lista, decodificación de portadas y eventos de desplazamiento.
- Acumula en RAM número de muestras, tiempo acumulado, máximo y operaciones que superaron 16/33 ms. El perfilador **no escribe a la microSD durante los eventos táctiles o la pintura**. Al salir de cada página escribe seis líneas CSV.

Activación opcional para **una futura build validada**: colocar un archivo vacío `/mnt/mmc/mochi-perf-enable`. Los resultados quedan en `/mnt/mmc/mochi-performance.csv`; retirar el marcador para desactivar. Este procedimiento **no sirve con el firmware 1.9.0 sin recompilar**, pues la funcionalidad aún no está incluida en el reproductor.

## Evidencia

- Prueba local de 17 verificaciones bajo AddressSanitizer y UndefinedBehaviorSanitizer.
- Encabezado compilado como objeto ELF **MIPS32r2 little endian** (no build del firmware completo).
- `git apply --check` de ambos parches aprobado en una copia de la fuente Sprint8.
- Contenido del encabezado y diffs en GitHub cotejado byte a byte con los artefactos locales mediante FNV64.
- Todos los scripts y pruebas, incluidos el analizador CSV y un instalador de fuente con verificación SHA256, están en el **paquete Sprint 9 adjunto en la conversación**.

SHA256 de la fuente requerida **antes del Sprint9**:
- `patch/albums.c`: `9b2f38cee2e387e9d72de332f143fb57aac8708d62a365b0286fa336b4036611`
- `patch/songs.c`: `895c3affe1abf6b5742ce8d19ebeb86558a13d84246b7bb05817df576fd8e9f8`

## Para aplicar solo a una copia de la fuente

1. Usar el paquete Sprint8 para aplicar TouchGuard + FirstMove a una copia limpia de imfing 1.9.0.
2. Usar `Mochi_Sprint9/apply_after_sprint8.py` para verificar hashes y aplicar el perfilador; este script solo modifica fuentes, no el `update.bin`.
3. Se deben validar build completo, dependencias de AWTK, reproducción y rutas de recuperación antes de producir una actualización.

**La PR está deliberadamente en estado borrador.** Todavía no tenemos mediciones reales de la latencia táctil en el dispositivo, ni prueba integral de la doble llamada AWTK de Sprint8. El mejor siguiente trabajo es realizar esas validaciones, no tocar a ciegas el firmware de uso diario.

La base `imfing/m1plus-music` está bajo licencia MIT; el repositorio solo contiene el código del parche y la instrumentación, no imágenes de firmware de terceros.
