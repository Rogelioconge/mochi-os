# Mochi OS — Sprint 8: respuesta del scroll de Albums

**PROTOTIPO; no compilar ni instalar un update.bin para pruebas de hardware todavía.**

Base verificada: `imfing/m1plus-music` etiqueta `1.9.0`. Incluye los cambios de TouchGuard (Sprint 7).

## Hallazgo MIPS

En el `demo` 1.9.0, el primer MOVE que supera 10 px hace que AWTK envíe ABORT al elemento seleccionado y escriba `dragged=1` (instrucción en `0x610c34`), pero retorna antes de desplazar la lista. El siguiente MOVE aplica la variación de posición. `widget_on_pointer_move` usa `on_event_before_children` (`0x67169c`) y respeta `RET_STOP` (`0x6716a4`). `widget_dispatch` envía directamente al `on_event` nativo (`0x66cf2c`).

## Cambio propuesto

El parche `mochi_sprint8.patch`, junto con `scrollfirst.h` y `touchguard.h`, aplica dos medidas exclusivamente a Albums:

1. TouchGuard invalida una apertura cuando el dedo realmente arrastró, aunque regrese al origen, o cuando el scroll cambió durante el gesto.
2. El primer MOVE válido se envía al AWTK original para cancelar el toque; si el widget continúa registrado y en drag, se envía **el mismo MOVE** de nuevo para que aplique el desplazamiento. Se devuelve RET_STOP para que AWTK no ejecute un tercer MOVE.

El registro de la vista se pone al final de `al_begin()` y se elimina en `al_on_destroy()`, evitando cambiar Songs, Home o Settings. No cambia la inercia, el umbral táctil ni el código de audio.

## Evidencia y límites

Las pruebas auxiliares locales superaron 32 comprobaciones del primer movimiento y 15 de TouchGuard, usando ASan/UBSan. Ambos encabezados compilan para MIPS32r2 y el auditor encontró 8/8 palabras esperadas en el `demo` real 1.9.0, SHA-256 `0db76a1570e0f5cfb3aaf39f237f44a091871ad0c3620c05d1dc050f67f36f1d`. El parche se aplicó a una copia limpia.

**NO VALIDADO:** integración de la doble llamada con AWTK real, rendimiento táctil en el M1 Plus, compilación del firmware completo, recuperación y reproducción sostenida. No se ha producido un actualizador instalable.

La distribución autocontenida, instrucciones de aplicación/verificación y tests del experimento se entregaron también como ZIP en el chat. Las versiones de 1.9.0 que no coincidan con los hashes de la fuente original no deben aceptar el parche automáticamente.

Licencias: código original de imfing bajo MIT; estos archivos son experimentales de Mochi OS.
