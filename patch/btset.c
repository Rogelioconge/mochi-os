/* M1+ Music Settings > Bluetooth, the control layer (docs/modules/bluetooth.md "Control layer"): what our page calls, and no widget in it.
 *
 * Every state is stock's own (bluetoothflag, btcoding, the link and scan words, the three device lists); every action repeats what stock's handlers do with it, with stock's own functions, in their order
 * (tools/pod_pins.py BLUETOOTH_PINS): the row handler 0x4a3a7c (the switch, Search, a device tap, the forget), the Quality choice handler 0x4a4850, the page's init 0x4a411c, its 200 ms timer 0x4a3fa0 and its
 * close handlers. What stock does to its own widgets after an action (the rebuild of its list, the spinner image, the check images) is returned for the page to do. Stock's dialogs are shown the way stock
 * shows them (the confirm and the toasts, kind, text and time as stock's handlers fill them). A device is named by its MAC: the show list's index is looked up right before the call that takes it, as the
 * lists are refilled by getSearchResult (the page's tick, the idle handler) and an index taken earlier may mean another device. Taps are ignored while bt_connectstatus is set and answered by a toast
 * while the init runs, as in stock. The Wi-Fi switch's confirm is the one tools/coex.py leaves: OK keeps Wi-Fi on. */
#include "offsets.inc"
#include "stock.h"
#include "common.h"
#include "home.h"
#include "i18n.h"
#include "btset.h"

#define bt_flag (*(volatile unsigned char *)BT_FLAG)
#define wifi_flag (*(volatile unsigned char *)WIFI_FLAG)
#define bt_coding (*(volatile int *)BT_CODING)
#define init_status (*(volatile int *)BT_INITSTATUS)
#define init_time (*(volatile signed char *)BT_INITTIME)
#define connect_status (*(volatile int *)BT_CONNECTSTATUS)
#define link_status (*(volatile unsigned char *)BT_LINKSTATUS)
#define show_coding (*(volatile int *)BT_SHOWCODING)
#define search_time (*(volatile signed char *)BT_SEARCHTIME)
#define start_scan (*(volatile unsigned char *)BT_START_SCAN)
#define a2dp_direction (*(volatile int *)BT_A2DP_DIRECTION)
#define recv_volume (*(volatile int *)BT_RECV_VOLUME)
#define a2dp_event (*(volatile int *)BT_A2DP_EVENT)
#define recv_page (*(volatile int *)BT_RECV_PAGE)
#define refresh_flag (*(volatile unsigned char *)BT_REFRESH)
#define headset_output (*(volatile int *)HEADSET_OUTPUT)

#define BS_DEV_SIZE 0x124 /* stock's stBtDeviceInfo: status, MAC at +4 (0x20), name at +0x24 (0x100) */
#define BS_MAC_AT 4
#define BS_NAME_AT 0x24
#define BS_SCAN_TICKS 25 /* the scan's refresh period, 5 s */
#define BS_CONFIRM_PLAIN 1 /* the confirm dialog's kind of a yes / no question (stock's unpair and reconnect) */

static unsigned char bs_modal_on __attribute__((section(".scratch")));
static char bs_key[48] __attribute__((section(".scratch")));

/* ---------------------------------------------------------------------------
 * State
 */
int bs_on(void) { return bt_flag != 0; }
int bs_starting(void) { return init_status != 0; }
int bs_scanning(void) { return search_time > 0; }

/* The preferred codec, as config_init keeps it: 0 .. 7 (anything else is 0). */
int bs_codec(void) {
    int c = bt_coding;
    return (unsigned)c < 8 ? c : 0;
}

/* The tr key of codec i (0 .. 7), as stock's Quality rows get it from get_bluetoothcoding_text; 0 for another i. The text is in the page's language through TR(). */
const char *bs_codec_key(int i) {
    if ((unsigned)i >= 8) return (const char *)0;
    bs_key[0] = 0;
    if (get_bluetoothcoding_text(i, bs_key) != 1) return (const char *)0;
    bs_key[sizeof bs_key - 1] = 0;
    return bs_key;
}

const char *bs_name(void) { return (const char *)BT_LOCALNAME; }

/* The show list as the page lists it, in stock's order (the paired devices first), capped at max. Each one's second line is stock's btdevice_listitem_layout (0x4a33c8) rule: it is read off the last link
 * item only (getBtLinkItem(getBtLinkSize() - 1)): the device with that MAC is Connecting while bt_connectstatus is 1, Connected while the item's status is 3 and the codec in use is 1 .. 4 or 13; any other
 * device (or one connected whose codec is not known yet) shows Paired or nothing. Returns the number written. */
int bs_devices(struct bs_dev *out, int max) {
    void *q = *(void *volatile *)BT_SHOWLIST;
    unsigned n = q ? deque_size(q) : 0, i, k;
    int st = 0, code = show_coding;
    char lm[32];
    memset(lm, 0, sizeof lm);
    getBtLinkItem(getBtLinkSize() - 1, &st, lm);
    if (max < 0) max = 0;
    if (n > (unsigned)max) n = (unsigned)max;
    for (i = 0; i < n; i++) {
        const char *rec = (const char *)deque_at(q, i);
        struct bs_dev *d = out + i;
        int same;
        if (!rec) break;
        for (k = 0; k < sizeof d->mac - 1 && rec[BS_MAC_AT + k]; k++) d->mac[k] = rec[BS_MAC_AT + k];
        d->mac[k] = 0;
        for (k = 0; k < sizeof d->name - 1 && rec[BS_NAME_AT + k]; k++) d->name[k] = rec[BS_NAME_AT + k];
        d->name[k] = 0;
        same = strcmp(d->mac, lm) == 0;
        d->state = BS_DEV_NONE;
        if (same && connect_status == 1)
            d->state = BS_DEV_CONNECTING;
        else if (same && st == 3 && ((unsigned)(code - 1) < 4u || code == 13))
            d->state = BS_DEV_CONNECTED;
        d->paired = checkPairDev(d->mac) != 0;
    }
    return (int)i;
}

/* The show-list index of the device with this MAC, -1 when it is not there (any more). */
static int bs_index(const char *mac) {
    void *q = *(void *volatile *)BT_SHOWLIST;
    unsigned n = q ? deque_size(q) : 0, i;
    for (i = 0; i < n; i++) {
        const char *rec = (const char *)deque_at(q, i);
        if (rec && strcmp(rec + BS_MAC_AT, mac) == 0) return (int)i;
    }
    return -1;
}

/* Whether adjustA2dpVolume (0x4d28ac) does anything: it always answers 1, and acts only with Bluetooth on, a link up, its codec known and no receiver page (the reading it takes first is ignored when
 * it is 128 or more). */
int bs_volume_ok(void) { return bt_flag != 0 && link_status != 0 && show_coding > 0 && recv_page == 0; }

/* A stock dialog of ours is up (modal): the page's tick has nothing to do meanwhile. */
int bs_modal(void) { return bs_modal_on; }

/* ---------------------------------------------------------------------------
 * Stock's dialogs, filled as its handlers fill them
 */
static int bs_confirm(int kind, const char *key) {
    struct {
        int kind, ms;
        char text[MSGINFO_TEXT], text2[MSGINFO_TEXT];
    } info;
    const char *t = TR(key);
    unsigned i;
    memset(&info, 0, sizeof info);
    info.kind = kind;
    for (i = 0; t[i] && i < sizeof info.text - 1; ++i) info.text[i] = t[i];
    bs_modal_on = 1;
    i = (unsigned)pod_confirm_dialog(&info);
    bs_modal_on = 0;
    return (int)i == CONFIRM_YES;
}

static void bs_toast(const char *key, int ms) {
    bs_modal_on = 1;
    pod_toast_ms(TR(key), ms);
    bs_modal_on = 0;
}

/* Every row of stock's page answers a toast and nothing else while the init runs. 1 when it did (the action is over). */
int bs_init_guard(void) {
    if (init_status == 0) return 0;
    bs_toast("msg_btinit_run", 2000);
    return 1;
}

/* Stock's output restore after a disconnect or an unpair of the connected device: the output goes back from Bluetooth when it differs (stored before the status call, as stock's delay slot does), and the
 * jacks are set unless the player is stopped (status 1). */
static void bs_restore_output(void) {
    int out = judge_outputdevice(headset_output, 2);
    if (headset_output == out) return;
    headset_output = out;
    if (mclGetSavePlayStatus() != 1) set_outputchannel(headset_output, 3, 0);
}

/* ---------------------------------------------------------------------------
 * Actions
 */

/* The switch row. On while Wi-Fi is on asks first (msg_bt_open, kind 5): Cancel changes nothing; OK leaves Wi-Fi on (tools/coex.py turns stock's wifi_switch(1) after the confirm into a branch). Then stock's
 * one call, switchBluetooth(the current state, 1): on starts the init (a scan follows it), off stops everything and saves BLUETOOTH. BS_REBUILD whenever stock rebuilds; BS_NONE while the init runs. */
int bs_toggle(void) {
    if (bs_init_guard()) return BS_NONE;
    if (!bt_flag && wifi_flag && !bs_confirm(CONFIRM_KIND_WRAP, "msg_bt_open")) return BS_REBUILD;
    switchBluetooth(bt_flag, 1);
    return BS_REBUILD;
}

/* The Search row: stock calls btStartSearch and nothing else (a scan that runs is not restarted: the call is ignored; the spinner follows from the tick). */
int bs_search(void) {
    if (bs_init_guard()) return BS_NONE;
    btStartSearch();
    return BS_NONE;
}

/* The page's init (stock's 0x4a411c, minus its handlers and widgets): the scan count-down, the redraw flag and the scan request are cleared; Bluetooth on with no init running: the name read again and a scan
 * started. */
void bs_open(void) {
    search_time = 0;
    refresh_flag = 0;
    start_scan = 0;
    if (bt_flag && init_status == 0) {
        memset((void *)BT_LOCALNAME, 0, 0x100);
        memset((void *)BT_LOCALMAC, 0, 0x20);
        getLocalBtName((char *)BT_LOCALNAME, (char *)BT_LOCALMAC);
        btStartSearch();
    }
}

/* One tick of stock's 200 ms timer (0x4a3fa0), minus its widgets. The redraw flag is consumed; with Bluetooth on: while the init runs its spinner counts down (BS_T_SPIN), else a scan counts down: at 1 it is
 * stopped and the results read (BS_T_REBUILD), at a multiple of 25 (5 s) the results are read (BS_T_REBUILD), otherwise only the spinner moves; with no scan, bt_start_scan starts one. */
int bs_tick(void) {
    int r = 0, n;
    if (refresh_flag) {
        refresh_flag = 0;
        r |= BS_T_REBUILD;
    }
    if (!bt_flag) return r;
    if (init_status > 0) {
        if (init_time > 0) {
            init_time = (signed char)(init_time - 1);
            r |= BS_T_SPIN | (((unsigned char)init_time) << 8);
        }
        return r;
    }
    if (init_status != 0) return r;
    if (search_time > 0) {
        search_time = (signed char)(search_time - 1);
        n = search_time;
        if (n == 1) {
            btStopSearch();
            getSearchResult();
            r |= BS_T_REBUILD;
        } else if (n % BS_SCAN_TICKS == 0) {
            getSearchResult();
            r |= BS_T_REBUILD;
        } else
            r |= BS_T_SPIN | (((unsigned char)n) << 8);
    } else if (start_scan) {
        btStartSearch();
        start_scan = 0;
    }
    return r;
}

/* Stock stops the scan on its return button and in its to-background and close handlers: the same one call. */
void bs_close(void) { btStopSearch(); }

/* A device row. Ignored while a connect runs; the scan is stopped first. A device that is connected is disconnected (the output restored, "Disconnected", the player restarted; stock's branch skips the results read the unpair has); else it
 * is connected, or paired first (the connect thread does the rest and the idle handler finishes it); SyncLink over Bluetooth gets "Please close SyncLink" (stock's -1). BS_REBUILD when stock rebuilds. */
int bs_link(const char *mac) {
    int s, r;
    if (bs_init_guard()) return BS_NONE;
    if (connect_status != 0) return BS_NONE;
    btStopSearch();
    s = bs_index(mac);
    if (s < 0) return BS_REBUILD;
    r = handleBluetoothLink(s);
    if (r == -1) {
        bs_toast("msg_closesynclink", 2000);
        return BS_NONE;
    }
    if (r == 1) {
        bs_restore_output();
        bs_toast("msg_disconnected", 2000);
        save_start_player(1);
    }
    return BS_REBUILD;
}

/* Forget a paired device (stock's tap on its bt_del icon, from the confirm on): "unpair?" (kind 1), then handleBluetoothPair; when it was the connected device the output is restored; "Unpaired" for 4 s, the
 * results read, the player restarted. A device that is not paired is not touched. */
int bs_forget(const char *mac) {
    int s, r;
    if (bs_init_guard()) return BS_NONE;
    if (connect_status != 0) return BS_NONE;
    btStopSearch();
    if (bs_index(mac) < 0) return BS_REBUILD;
    if (!checkPairDev(mac)) return BS_NONE;
    if (!bs_confirm(BS_CONFIRM_PLAIN, "msg_unpairing")) return BS_NONE;
    s = bs_index(mac);
    if (s < 0) return BS_REBUILD;
    r = handleBluetoothPair(s);
    if (r != 1 && r != 2) return BS_NONE;
    if (r == 2) bs_restore_output();
    bs_toast("msg_unpaired", 4000);
    getSearchResult();
    save_start_player(1);
    return BS_REBUILD;
}

/* The Quality page's choice (stock's 0x4a4850, minus the check images): ignored while a connect runs and for the choice that is already made. While a device is connected (a link up and its codec known) it
 * asks "Reconnect Bluetooth?" first (Cancel changes nothing) and then drops the link's state, five words and the output, as stock does. The choice is stored, switchBtPriority applies it, BTCODING is saved;
 * a connected device is connected again (bluetoothLink(2)); stock's redraw flag is set. BS_REBUILD when the choice was taken (the page shows the new check), else BS_NONE. */
int bs_codec_set(int c) {
    int connected;
    if ((unsigned)c >= 8) return BS_NONE;
    if (connect_status != 0) return BS_NONE;
    if (c == bt_coding) return BS_NONE;
    connected = link_status != 0 && show_coding > 0;
    if (connected) {
        if (!bs_confirm(BS_CONFIRM_PLAIN, "msg_btreconnect")) return BS_NONE;
        save_stop_player();
        link_status = 0;
        show_coding = 0;
        a2dp_direction = 0;
        recv_volume = -1;
        a2dp_event = 0;
        bs_restore_output();
    }
    bt_coding = c;
    switchBtPriority(c);
    write_int_config(bt_coding, "SYSSET", "BTCODING");
    if (connected) bluetoothLink(2);
    refresh_flag = 1;
    return BS_REBUILD;
}

/* The Headset Volume Control row's buttons: stock's adjustA2dpVolume (up 1, down 0). Answers whether it acted (bs_volume_ok). */
int bs_volume(int up) {
    int ok = bs_volume_ok();
    adjustA2dpVolume(up);
    return ok;
}
