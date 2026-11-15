/* M1+ Music Settings > General > Language (docs/modules/language.md): the state behind our Language row and its picker.
 *
 * The state is stock's own: the word `language` (0 .. 12, the row of stock's systemset/language_page; config_init loads it from [SYSSET] LANGUAGE). Stock's page stays reachable through All System Settings
 * and shows the same word. Nothing of ours is saved. lang_set repeats stock's row handler (0x4a7cb0, tools/pod_pins.py LANGUAGE_PINS) in its order and nothing else: the word, the save, switch_language,
 * the two flags the Home screen reads, and navigator_back_to_home. The handler's own widget changes (the old and the new row's check) are those of stock's page, which is not open. */
#include "offsets.inc"
#include "stock.h"
#include "entries.h"

#define LANG_COUNT \
    13 /* stock's language page: simplified, traditional, English, Japanese, Korean, French, German, Spanish, Italian, Thai, Polish, Russian, Ukrainian */

#define lang_word (*(volatile int *)LANGUAGE_WORD)
#define lang_changed (*(volatile unsigned char *)LANGUAGE_CHANGED)
#define homemenu_changed (*(volatile int *)HOMEMENU_CHANGED)

/* The language's own name, stock's keys (the same text in every table), in the order of stock's table at 0x97c880. */
const char *lang_key(int v) {
    static const char *const key[LANG_COUNT] = {
        "lan_simplified", "lan_traditional", "lan_english", "lan_japanese", "lan_korean",  "lan_french",   "lan_german",
        "lan_spanish",    "lan_italian",     "lan_thai",    "lan_polish",   "lan_russian", "lan_ukrainian"};
    return key[v >= 0 && v < LANG_COUNT ? v : 0];
}

/* The language that is loaded: stock's word, and zh_CN (row 0) for a word switch_language does not know (0x4cca5c), as stock's page shows no check then. */
int lang_get(void) {
    int v = lang_word;
    return v >= 0 && v < LANG_COUNT ? v : 0;
}

/* Choose it as stock's page does: nothing when it is the word already; else the word is stored, [SYSSET] LANGUAGE saved, the locale switched (every open window is translated again, the CJK font forms follow),
 * the Home screen told to rebuild its menu (change_lanflag 1, homemenu_changeflag 2: its foreground callback resets the index and rebuilds in the new language), then every window above Home is closed, Settings
 * and the picker included. 0, or -1 for a choice stock does not have. */
int lang_set(int v) {
    if (v < 0 || v >= LANG_COUNT) return -1;
    if (v == lang_word) return 0;
    lang_word = v;
    write_int_config(v, "SYSSET", "LANGUAGE");
    switch_language(lang_word);
    lang_changed = 1;
    homemenu_changed = 2;
    navigator_back_to_home();
    return 0;
}
