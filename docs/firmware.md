# Shanling M1 Plus V2.1 firmware notes

Stock pins (SHA-256):

```
db7bdbc42ffe6d5c1e3fdca9363edb78a01898b9a725c34793394cf6abfa33c0  M1 Plus Firmware V2.1.zip
1ccb4667e3e9bdf9a35be4dc58d09b898ca53c5fd58396b7667fb91fe895f925  update.bin
3b326f04f20690af82fd7b2d3d61f9d01478c75081f30e99973a4e11b58fbcd8  recovery-update/xImage
8794ca4bbbf0ee70b4c23ca6ade589cf61d7213170164d9dc9e6aedb96be0db1  recovery-update/rootfs.squashfs
```

## 1. Stock format and updater

| Item | Shanling M1 Plus V2.1 |
|---|---|
| SoC / arch | Ingenic X2000, MIPS32r2 LE |
| Kernel | Linux 5.10.21+ uImage (xImage), 5,410,880 bytes |
| Userland | Buildroot 2020.02.1, glibc, BusyBox, AWTK UI |
| Main app | `/release/bin/demo` (AWTK, dynamic symbols kept, spare PT_NULL phdr) |
| Audio daemon | `/usr/bin/hciplayer` (MPlayer 1.3.0 modified, spare PT_NULL phdr; patched only for the [EQ and stereo stage](modules/peq.md)) |
| Package | `update.bin` = plain GNU tar: `firmware_v20.info`, `recovery-update/xImage`, `recovery-update/rootfs.squashfs` |
| rootfs | squashfs 4.0, LZO, 128 KiB blocks, 55,738,368 bytes |
| Signing | none, MD5 only |

The unsigned, unencrypted package is handled by `demo`'s `update_firmware`
(disassembled with `tools/disasm.py`):

1. `tar xvf /mnt/mmc/update.bin -C <tmp>` ; `sync`
2. read 4 lines of `firmware_v20.info`
3. line 1 must `strcmp` equal `"Shanling M1 Plus"`
4. line 2 must contain the letter `V` (`strchr`) and must NOT equal the built-in `"V2.1"`
   (identical version is refused with error -14; there is no "newer than" check). The mod points this
   compare at another string, so official V2.1 installs too ([version](modules/version.md))
5. MD5 of `recovery-update/xImage` and `rootfs.squashfs` must match lines 3 and 4
6. `flash_erase /dev/mtd6` ; write marker `ota:kernel2` to mtd6 with `nandwrite` ; reboot

The separate `kernel2` recovery system performs the flash. **The recovery kernel and bootloader
are absent from `update.bin` and remain unchanged.** The M1 Plus recovery button combination is
unknown.

**Device flash layout** (`/proc/mtd`): 128 MiB NAND, 128 KiB erase blocks.

| mtd | name | size | what it is |
|---|---|---|---|
| 0 | uboot | 1 MiB | the bootloader |
| 1 | kernel | 6 MiB | the kernel `update.bin` replaces |
| 2 | rootfs | 75 MiB | the rootfs `update.bin` replaces: squashfs, read-only (`root=/dev/mtdblock_bbt_ro2`); the release fills 50.75 MiB of it |
| 3 | kernel2 | 6 MiB | the recovery kernel the OTA flag boots (step 6) |
| 4 | rootfs2 | 12 MiB | the recovery kernel's own root file system |
| 5 | userid | 128 KiB | a config blob |
| 6 | ota | 128 KiB | the OTA flag (`ota:kernel2`) |
| 7 | userdata | 24.75 MiB | the UBI volume `userdata`, UBIFS at `/mnt/data` (`/dev/ubi1_0`, mounted `sync`): 17.7 MiB, 16 MiB free with a library database |

Recovery (mtd3/4) is separate from updated partitions (mtd1/2). The device-tree NAND table
(8 MiB kernel, 247 MiB rootfs, alongside a NOR table) is unused. The command line is
`console=ttyS3,115200n8 quiet mem=128M@0x0 init=/linuxrc flashtype=nand root=/dev/mtdblock_bbt_ro2 rootfstype=squashfs ro`:
128 MiB RAM and a UART3 console (board pads unlocated; possible boot-loop access).
Although the partition has ~19 MiB spare above stock, `fwtool` still enforces the stock image-size limit.

## 2. Safety assessment

- Only kernel and rootfs are flashed; bootloader + recovery kernel stay stock.
- The rootfs is read-only squashfs, so a mod cannot corrupt itself at runtime.
- The watchdog script in the stock rootfs reboots the device if `demo` is not running, so a
  crashing UI can cause a reboot loop. The recovery button path remains unverified.
- Keep the rebuilt `rootfs.squashfs` no larger than stock (fwtool enforces this).
- Charge the battery first and do not pull the card during the update.
- Repacking changes compressed bytes; packing checks stock metadata, allowed file changes and
  size. Restore packages reuse stock squashfs unchanged. The space step is described
  below.

## 3. Battery and version string

In `ui/system_bar.bin` the battery is an `image` (`img_battery`) with an AWTK `progress_bar`
(`pgbar_battery`) as its fill. On every refresh `demo` sets the bar to the real capacity (100 when
charge is complete). `tools/mod_battery.py` redraws the state images as an outline and lays the
bar out as a horizontal fill inside it ([battery](modules/battery.md)), with no binary patch.

The installed version string stays "V2.1" (the online check and About read it), but
`update_firmware`'s own compare is repointed ([version](modules/version.md)). So:

- the TF-card updater accepts any package tag, including Shanling's official V2.1, which is the
  user's way back to stock; `V2.1R` (`build.py --restore`) stays a developer tool;
- any future official release installs normally.

The lock screen page is owned by [lockscreen](modules/lockscreen.md). Stock behaviour it relies
on: `demo` calls `digit_clock_set_format` only for the date-time settings row and for the status
bar clock (`hh:mm` 24 h, `HH:TT` 12 h). The statically linked `wstr_format_date_time` takes these
tokens, which are not portable to other AWTK builds (`HH:TT` renders `05:PM` on the Q2):

| token | output | token | output |
|---|---|---|---|
| `Y` / `YY` | 2026 / 26 | `h` / `hh` | hour 0-23 / 00-23 |
| `M` / `MM` / `MMM` | 1-12 / 01-12 / month name | `H` / `HH` | hour unpadded / 01-12 |
| `D` / `DD` | 1-31 / 01-31 | `m` / `mm`, `s` / `ss` | minute, second |
| `w` / `W` | weekday 0-6 / name | `T` / `TT` | minute / minute + ` AM` or ` PM` |

## 4. Space recovery (`mod_space.py`)

A plain fwtool rebuild of stock is 12 KB under the stock size, which fwtool enforces as the limit.
`build.py` therefore applies a space step to the release (not to `--restore`):

| step | rootfs.squashfs | saved | headroom |
|---|---|---|---|
| stock image | 55,738,368 | | |
| fwtool rebuild, no change | 55,726,080 | | 12,288 |
| + `mksquashfs -tailends` (`fwtool repack --tailends`) | 55,697,408 | 28,672 | 40,960 |
| + `.pdr` zeroed in `demo` | 55,635,968 | 61,440 | 102,400 |
| + 10 unused files removed (**default result**) | 53,141,504 | 2,494,464 | 2,596,864 |

(mksquashfs pads to 4 KiB.) The release step also deletes stock's whole `release/assets/theme1` tree
(271 files, 2.3 MB uncompressed; `remove_theme1`, safe only with the `config_init` clamp of
[theme](modules/theme.md)), which shrinks the mod's rootfs.squashfs by 458,752 bytes (55,296,000 -> 54,837,248).

- **-tailends** packs the last partial block of every file into fragments. Data layout only; names,
  modes, owners and times are unchanged. Directory sizes in a listing change (squashfs directory-table
  length follows the inode layout).
- **.pdr** (MIPS procedure descriptors, a debugger table) is zeroed in `/release/bin/demo` only
  (415,744 bytes), as q2-pod does for the Q2; every other ELF ships untouched. The section is found by name in the section headers and must be `PROGBITS`, without
  `SHF_ALLOC`, address 0, outside every program header, not overlapping another section or the
  headers, with no relocations against it. The loader only maps program headers, so these bytes are
  never mapped; `.pdr` is used by debuggers (gdb), and nothing on the rootfs is known to read it from
  disk. File size, section headers and every other byte are unchanged (cross-checked with
  pyelftools). `demo` is pinned by its stock SHA-256.
- **removed**, each pinned by SHA-256: `usr/bin/strace`, `strace-log-merge`, `sqlite3`, `hcidump`;
  `usr/lib/libdbus-1.so.3.19.8`; `usr/lib/lib{gio,glib,gmodule,gobject,gthread}-2.0.so.0.5400.3`
  (6,438,409 bytes). Nothing on the rootfs references them: the sonames resolve to newer copies,
  and no script or binary invokes the tools. fwtool accepts the missing inodes only via an
  explicit `--allow-removed PATH` list.

The checkappprocess.sh watchdog (`usr/bin/checkappprocess.sh`, started by `demo`) polls
`pgrep /release/bin/demo` every 2 s and reboots if it is gone; the release leaves it as it is.

The space step is part of every package. `fwtool diff` against stock lists exactly `demo` (content), the removed files and
the mod's own files.

## 5. Rebuilding

See the [development guide](workflow.md) for commands. `tools/build.py` owns the pipeline,
`tools/fwtool.py` unpacks, repacks, verifies and diffs, and `tools/stock.py` wraps stock UI and
disassembly searches. fwtool rebuilds the squashfs with the stock parameters and re-applies every
stock inode's mode, owner and time; an unmodified round trip diffs clean against stock.

## 6. The code payload

`demo` is an `ET_EXEC` with a spare final `PT_NULL` program header. The payload is appended at va
`0xb00000` through pinned sites; see [payload](modules/payload.md) for trampolines, kill switch
and entry points, and [pipeline](modules/pipeline.md) for the build.
