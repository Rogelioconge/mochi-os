# MOX OS — ruta hacia un Home realmente nativo (Sprint 8)

**Estado: preparación, no sustitución del launcher.** Los recursos `mox_home.bin` y `m1plus_menu.bin` ya tienen rutas de apertura distintas. Sin embargo, `m1plus_home_init()` todavía invoca `stock_home_init_trampoline(win, ctx)` antes de `home_boot(win)`. La cuadrícula de Shanling se construye en memoria. El archivo `/mnt/mmc/mox-native-enable` sigue siendo solo un candidato sin efecto sobre esta ruta.

## Primer bloqueo identificado: recuperación estructural

La recuperación actual vuelve a mostrar el widget `app_gesture` que Shanling **ya había construido**. Si dejamos de llamar a la inicialización original, esa operación por sí sola no podrá recrear las páginas ni sus eventos.

Este sprint añade `hm_stock_rescue_ready()` en `patch/home.c`: antes de aceptar el Home MOX, exige `app_gesture`, `home_sview` de tipo `slide_view`, de 1 a 8 páginas y que cada página sea un `view`. Si no se cumple, falla con nota persistente sin aceptar el Home como válido. Las pruebas de C inyectan cuatro árboles incompletos. La comprobación no sustituye la prueba de botones, eventos y renderizado en un dispositivo real.

**Importante:** el guardado y la restauración de Shanling siguen usando el inicializador original. Por diseño, esta validación impide asumir que un Home sin cuadrícula sea seguro. Es un paso para preparar un cambio de arquitectura, no una autorización para retirar el inicializador.

## Segunda investigación: dónde se construye la cuadrícula

Las notas de ingeniería sitúan una llamada de `home_page_init` al constructor de páginas en `0x534de4`, con destino `0x534064`; este último utiliza la rutina de iconos `0x533d8c`. `tools/mox_cutover_audit.py` verifica que el `demo` compilado para V2.1 contiene esa llamada con destino directo. Solo **lee** el ELF y crea `out/mox-cutover/audit.json`. El análisis falla ante un destino o un ELF diferente y **siempre** marca `bypass_authorized: false`.

El punto de llamada no demuestra que sea seguro omitirla. La inicialización original puede también configurar eventos, datos globales y controles del Home. No debemos parchear esta instrucción sin trazar las dependencias y poder llamar a un inicializador de recuperación sin repetir efectos secundarios.

## Condiciones necesarias antes de cualquier corte nativo

1. Identificar las operaciones y efectos secundarios de `home_page_init`, con trazas del `demo` V2.1 original.
2. Implementar y probar una construcción **tardía e independiente** del Home de Shanling, para cuando falle MOX aun si nunca hubo cuadrícula inicial.
3. Ensayar errores de inicialización, falta de recursos, fallo de pintado, cierre prematuro y fallo de almacenamiento mediante el emulador MIPS.
4. Garantizar recuperación real incluso si el dispositivo no monta la microSD al inicio, y documentar un procedimiento comprobado de restauración del firmware oficial.
5. Validar pantalla, navegación táctil, botones, reproducción y varios reinicios en el M1 Plus **antes de habilitar la ruta que omita Shanling**.

Comando de investigación, después de `make test TEST=home`:

```sh
uv run --locked python -I tools/mox_cutover_audit.py
```

El resultado **NO** genera `update.bin` ni instala nada en el DAP.

## Sprint 9 — dependencias reales posteriores al constructor (solo auditoría)

Un desmontaje de `demo` V2.1 muestra que la llamada al constructor de páginas
`0x534de4 → 0x534064` **no es el final** de `home_page_init`.

La ejecución continúa en `0x534dec`: entre ese punto y `0x535038` hay, al menos,
**11 sitios de registro de eventos** (valores de `$a1` preparados antes de
`jalr $t9`) sobre el Home o el gestor de ventanas, además de la llamada directa
`0x534e54 → 0x5349e4` a `home_timer_start`. Entre los identificadores destacan
`0x103` (eventos táctiles), `0x113` (liberar tecla) y `0x110` (pulsación larga).
También hay ramas y llamadas indirectas de memoria de reproducción, modos del
reproductor y temporizadores que no se han aislado todavía. Los 11 registros
son **sitios del código**, no una afirmación de que todos se ejecuten en cada arranque.

`tools/mox_rehydrate_audit.py` confirma esos anclajes en el ELF construido por
tu Mac, comprueba el delay slot del constructor y genera
`out/mox-cutover/rehydration.json`. Si alguno difiere, el auditor falla en vez
de aprobar un reemplazo. La verificación es de solo lectura: no deshabilita la
cuadrícula ni construye un sustituto.

**Decisión:** no se debe saltar el inicializador completo ni llamar a
`stock_home_init_trampoline()` sobre una ventana ya inicializada, porque eso
podría duplicar manejadores, páginas y temporizadores. Todavía necesitamos
separar el constructor de páginas de los otros efectos secundarios, confirmar
un contrato ABI seguro de reconstrucción tardía y probarlo en el emulador MIPS
antes de intentar una ruta de inicio sin cuadrícula. El bypass sigue bloqueado.

## Sprint 10 — contrato real del constructor y prueba de reconstrucción aislada

El contrato MIPS V2.1 de `0x534064` **no es de un solo argumento**.
`home_page_init` carga `$a1=1` en `0x534dd4`; el delay slot de
`0x534de4` pasa la ventana en `$a0`; el constructor guarda `$a1` en
`$s5` (0x534080) y lo utiliza en la rama de `0x53414c`. Al invocarlo
por separado, `$t9` también debe apuntar a su dirección de entrada para
que el prólogo PIC calcule correctamente `$gp`. El éxito observado retorna
0 y hay una ruta de fallo que retorna 0x10.

`tools/mox_rebuild_contract.py` verifica estos anclajes sobre el ELF de
`demo`; `test/mox_rebuild_contract.py` verifica cambios de instrucciones.
`patch/mox_grid_rebuild.c` y `.h` son un **prototipo sin conexión al firmware**:
solo se compilan en el ejecutable de pruebas `test/mox_grid_rebuild.py`,
con widgets simulados. El prototipo evita construir de nuevo una cuadrícula
parcial, impide intentos duplicados y verifica un árbol reconstruido antes
de aceptar el resultado. No sustituye al constructor original; no está
enlazado a `demo` ni se llama en `home.c`.

**El bypass sigue BLOQUEADO.** Aún debe demostrarse que el constructor
soporta una invocación tardía en la AWTK real, que no duplica manejadores
y que se puede volver a Shanling tras fallos reales, incluidos bloqueos.
