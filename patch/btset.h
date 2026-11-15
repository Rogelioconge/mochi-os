/* Settings > Bluetooth, the control layer (patch/btset.c, docs/modules/bluetooth.md "Control layer"): what the own page calls, no widget in it. */
#pragma once

/* What an action asks of the page. */
enum {
    BS_NONE = 0, /* nothing changed on screen */
    BS_REBUILD = 1 /* the lists or the switch changed: read the state again and lay the page out again */
};

/* One device of the show list (stock's pdeq_btshowlist, paired devices first as stock fills it). */
enum { BS_DEV_NONE = 0, BS_DEV_CONNECTING = 1, BS_DEV_CONNECTED = 2 };
struct bs_dev {
    char mac[32]; /* "AA:BB:CC:DD:EE:FF", the key every action takes */
    char name[256]; /* utf8 */
    unsigned char paired; /* checkPairDev(mac) */
    unsigned char
        state; /* BS_DEV_*, stock's second line "Connecting" / "Connected" (otherwise "Paired" when paired, nothing when not) */
};

/* bs_tick's result: bits for the page's tick. */
#define BS_T_REBUILD 1 /* lay the list out again */
#define BS_T_SPIN 2 /* set the spinner image search<n mod 8>; n is BS_T_SPIN_N(result) */
#define BS_T_SPIN_N(r) ((signed char)(((r) >> 8) & 0xff))

int bs_on(void);
int bs_starting(void);
int bs_scanning(void);
int bs_codec(void);
const char *bs_codec_key(int i);
const char *bs_name(void);
int bs_devices(struct bs_dev *out, int max);
int bs_volume_ok(void);
int bs_modal(void);

int bs_init_guard(void);
int bs_toggle(void);
void bs_open(void);
int bs_tick(void);
void bs_close(void);
int bs_search(void);
int bs_link(const char *mac);
int bs_forget(const char *mac);
int bs_codec_set(int c);
int bs_volume(int up);
