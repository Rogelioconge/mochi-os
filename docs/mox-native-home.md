# MOX OS Sprint 7 — recurso Home independiente

Se agrega `mox_home.bin` como una ventana **AWTK nativa** separada de `m1plus_menu.bin`.
`tools/mod_mox_native.py` la genera a partir del menú ya decorado e iconizado, al terminar
`mod_icons` **y después de `mod_polish`**, que ajusta el ancho final de la cabecera. El archivo original permanece idéntico. Solo se cambian el nombre de la ventana
y el estado inicial de visibilidad/sensibilidad de la barra superior.

- `open_page(POD_ENTRY_PAGE, 1)` abre `mox_home`, con sus 26 tarjetas, controles y
  funciones del menú. Un menú normal todavía abre el recurso `m1plus_menu`.
- Una ventana que no puede abrirse hace que `m1plus_open_entry()` falle y que
  `home.c` restaure el Home de Shanling con una nota de recuperación.
- El recurso no agrega marca MOX a la pantalla principal.
- El nuevo archivo está registrado como `--allow-added` en el repaquetador.
- Si el recurso difiere de la estructura esperada, falla el build o su prueba.

**No es todavía un reemplazo del launcher**: la función original
`stock_home_init_trampoline()` todavía construye la cuadrícula de Shanling.
Este sprint aísla el recurso UI que podrá utilizar la futura ruta sin cuadrícula.
`EVT_AFTER_PAINT` tampoco demuestra que la pantalla física funcione.
No generar ni flashear un update.bin de esta etapa sin pruebas adicionales.

## Sprint 7.3 — rutas de apertura y regresión corregida

- Inicio automático de MOX: `open_page(POD_ENTRY_PAGE, 1)` carga `mox_home.bin`
  y verifica disposición y pintado mediante los mecanismos de recuperación existentes.
- Al tocar el icono desde la cuadrícula de Shanling sin restauración de sesión:
  `open_page(POD_ENTRY_PAGE, 0)` carga `m1plus_menu.bin`, con Atrás visible.
- Después de elegir «Open Shanling Home», un toque que sí restaura MOX
  utiliza el recurso nativo de Home; si falla, vuelve a la cuadrícula.
- La prueba de Home emulada comprueba ambos recursos por nombre y verifica
  la ruta normal incluso cuando `mox_home` no puede abrirse.

Sin flasheo: estas pruebas no certifican interacción física en el M1 Plus.

## Sprint 13 — Now Playing independiente (recursos, todavía sin apertura)

`tools/mod_mox_nowplaying.py` genera `mox_now_playing.bin` (ventana AWTK de 320 × 450 px) y un tema de ventana `styles/mox_now_playing_page.bin`. La ventana se define en código original de Mochi; el tema se construye a partir de los estilos de botones de `playing_page`, con estados play/pausa, favoritos y modos, respetando los recursos y créditos existentes.

El paso se ejecuta después de `mod_nowplaying` y `mod_mox_native`. Ambos recursos se registran para el empaquetado con `--allow-added`; no se modifica `playing_page.bin` ni la ruta de audio. Todavía **ningún hook abre esta ventana**, ni hay sincronización de carátula, datos o controles en el dispositivo. La barra de progreso es un slider normal: no representa una waveform real.

La prueba `test/mox_nowplaying.py` inspecciona la estructura, los controles, el tema, el build y la escritura determinista. No equivale a ejecutar AWTK en el dispositivo. No flashear ni publicar `update.bin` de esta etapa sin integración y recuperación verificadas.
