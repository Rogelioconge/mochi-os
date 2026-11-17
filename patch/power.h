/* External power (patch/power.c, docs/modules/charging.md "External power"): the one reading Battery History and the Charge Limit share. The test parses the #defines in this file.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 */
#pragma once

#define PWR_STATUS \
    "/sys/class/power_supply/battery/status" /* Charging / Full / Not charging = external power, Discharging = battery, anything else = unknown */
#define PWR_ONLINE_USB \
    "/sys/class/power_supply/usb/online" /* a supply of that name may not exist (the kernel registers "battery" only, as far as its strings go): then unknown */
#define PWR_ONLINE_AC "/sys/class/power_supply/ac/online"
#define PWR_GPIO_DEV "/dev/gpio" /* stock's gpio_open (libhardware2 0x556c): open(.., O_RDWR) */
#define PWR_GPIO_NAME "PD17" /* usb_detect's pin (0x4d6f30): low = external power */
#define PWR_GPIO_GET \
    0x2000477au /* gpio_get_value's ioctl request (libhardware2 0x57bc): the argument is the pin name, the return value the level */

/* Read every source: 1 external power, 0 battery, -1 unknown; any source saying external wins. */
int pwr_external(void);
