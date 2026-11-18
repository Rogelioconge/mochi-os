# The updater's version compare

**Sources:** `UPDATE_SITE` and `UPDATE_PINS` in `tools/pod.py`.
The TF-card updater refuses a package whose line-2 version equals the built-in literal `"V2.1"`
(error -14). Shanling's official V2.1 package carries exactly that, so an unpatched `demo` would
refuse it once the mod is installed. One pinned word changes the compare, so the official package
installs over the mod and restores stock.

## Readers of the literal

The literal (`demo` `.rodata` `0x74773c`) has four readers.

| Reader | Use | Patched |
|---|---|---|
| `update_firmware` `0x4e1124` | `strcmp(package version, literal)`: equal -> error -14 | yes |
| `check_otginfo` `0x4d92ac` | online check: equal -> "already the latest" | no |
| `systemset_fwdownload_page_init` `0x4a7028` | online update page: equal -> back out | no |
| About row `Firmware` `0x4a14cc` | prints the literal | no |

## The change

`0x24a5773c` (`addiu a1,a1,0x773c`) becomes `0x24a5772c`, so `update_firmware` compares the
package version with `"about_version"` (`0x74772c`, an AWTK widget key; no package tag can equal
it). The literal is untouched, so:

- official V2.1, `V2.1R`, our releases (`V2.1-x.y.z`) and dev tags all install over the mod;
- the online check still compares against `"V2.1"`, as in stock;
- the stock About row keeps showing `V2.1`; our About card shows the build tag
  ([settings](settings.md) "About").

The build refuses on any mismatch of the neighbouring words, the literal or the replacement
string. `update_firmware` is not reachable from boot.
