# Mochi OS — Reproductor nativo, prototipo de arquitectura 0.1

**Estado:** desarrollo local / NO instalar. Base de pruebas: copia de fuentes de MOX-OS proporcionada en el chat, correspondiente al entorno de Sprint 7.3; el M1 Plus del usuario contiene cambios más recientes (Sprint 12 y revisión `make dev`). Este paquete NO presume equivalencia de versiones y NO contiene un `update.bin`.

## Qué se construyó

- **AVISO DE PUBLICACIÓN**: el prototipo privado original contenía el recurso AWTK generado localmente, un recurso basado en los datos serializados del firmware Shanling. **Este paquete público lo excluye**. El código fuente conservado requiere reconstrucción local con entradas autorizadas.
- Se propone un fondo plano `#121417`, sin degradados decorativos.
- `mochi_wave.c/.h`: **motor C decorativo anterior**. Representa tres lóbulos prediseñados, NO señal real. Se conserva solo para comparación; se sustituirá por `mochi_wave_peaks.c/.h` con 64 amplitudes reales analizadas con `tools/mochi_waveform.py`.
- `mochi_wave_awtk.c`: adaptador para pintura AWTK; **aún NO enlazado** al firmware. Debe probarse en el emulador MIPS, conectar correctamente los eventos y revisar la limpieza de controladores al destruir las ventanas.
- `previews/mochi-reproduciendo-{jade,violeta}.png` y `previews/mochi-ajustes-colores.png`: vistas **aproximadas hechas con Pillow**, no capturas del motor AWTK real. Las portadas son ilustraciones originales de marcador de posición.
- `player_ui.py`: conserva la compatibilidad de nombres (`slider_play`, `btn_play`, `btn_prev`, `btn_next`, `btn_more`, `btn_fav`, `img_playcover`) antes de crear la variante Mochi.
- `test_player.py`: valida formato de recurso, geometría, área de interacción y equivalencia del cálculo de barras entre Python y C.

## Decisiones de producto

- **Firmware independiente** del proyecto M1+ Music, no dos temas seleccionables en un mismo firmware.
- Mantener como componentes reutilizables: Cover Flow, PEQ, AutoEQ y la conexión con audio / base de datos.
- Reproductor como inicio: restaurar última sesión pero **sin iniciar audio automáticamente**. Todavía no implementado.
- Nada de marca Mochi OS permanente en Inicio. El logo se reservará para boot, apagado y Acerca de (arte por la hermana).
- Temas: fondo plano y acentos limitados. Paleta inicial: Grafito, Jade, Azul, Violeta, Coral y Ámbar. El selector AWTK persistente aún no está implementado.
- Funciones tipo Pod: no aparecerán en la interfaz final. Primero ocultar, después retirar módulos cuando no existan dependencias.

## Próxima integración técnica

1. Rebasar estos cambios sobre **los fuentes actuales** del proyecto, no sobre un snapshot antiguo.
2. Integrar recurso y su PNG en el pipeline de assets y comprobar las referencias AWTK (la ventana aún necesita las imágenes `np_*` del proyecto base).
3. Enlazar, probar y activar la pintura de onda tras los cambios de valor del slider sin interceptar eventos táctiles. Comprobar una canción completa, búsqueda y pistas largas.
4. Actualizar pruebas específicas del viejo Now Playing, comprobar modo claro/oscuro y asegurar 1107/1107 pruebas integrales.
5. Solo después generar candidato `make dev` para prueba física; mantener rescate de Shanling durante la transición.

**Nunca copiar prototipos a la microSD:** no son un firmware instalable.

## Desarrollo y créditos

Mochi OS nace como firmware alternativo independiente para Shanling M1 Plus. Se reutiliza parte de la arquitectura de M1+ Music; se deben mantener los avisos de licencia MIT y revisar todas las licencias de terceros antes de redistribuir el firmware a la comunidad.
