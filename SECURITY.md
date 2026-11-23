# Security, firmware safety and reporting

Mochi OS modifies embedded firmware on the Shanling M1 Plus. An error can prevent normal boot or lead to data loss.

- **Status:** experimental; no supported end-user release.
- **Never flash** files from `prototypes/`, preview PNGs or an unverified `update.bin`.
- Preserve a verified stock restoration route. A successful flash on one device does **not** prove hardware-level unbrick/recovery.
- Keep official firmware, extracted partitions, secret keys, personal music files, generated artifacts and logs with personal paths **out of Git**.
- For a vulnerability, use GitHub private vulnerability reporting if enabled; otherwise contact the maintainer privately. Do not publish exploitation instructions or secret data in a public issue.
- Document tested hardware revision, source hash, toolchain, test receipts and rollback notes before offering a public firmware build.
