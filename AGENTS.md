# AGENTS.md

Firmware mods for the Shanling M1 Plus, built from official V2.1 and packaged as a TF-card
`update.bin`. Read [README](README.md), then the relevant reference below.

## Required references

| Work | Read |
|---|---|
| Setup, commands, worktrees, formatting, releases | [Development workflow](docs/workflow.md) |
| Runtime changes and safety boundaries | [Payload safety](docs/modules/safety.md), [architecture](docs/architecture.md) |
| Binary searches or patches | [Payload](docs/modules/payload.md), [pinned addresses](docs/modules/addresses.md) |
| UI changes | [UI reference](docs/ui.md), [UI rules](docs/modules/ui-rules.md), the feature's module |
| Testing and hardware evidence | [Validation](docs/modules/validation.md) |
| Installation, restore and firmware facts | [Install](docs/install.md), [firmware](docs/firmware.md) |

The [documentation index](docs/README.md) lists the remaining guides.
Read relevant ranges; avoid loading entire large files or history.

## Working rules

- Follow the [workflow](docs/workflow.md) and [safety](docs/modules/safety.md) rules before
  editing. Never execute extracted firmware or reference-clone code.
- UI fixes need a reproducer. Use the shared layout/text model and the built font for previews.
- Pin every binary edit and fail on mismatch; hooks fall back to stock.
- Never expand the approved global paint or main-loop scope (paint: only the palette's three
  hooks, [accent](docs/modules/accent.md)). Keep the crash guard and the `/mnt/mmc/m1plus-off`
  kill switch. Never write the bootloader or recovery kernel. Pinned boot-reachable hooks that fall back to stock and do bounded work are a
  paved path.
- Preserve widget names. Hidden widgets must also be insensitive.
- Feature branches leave `VERSION`, goldens and history unchanged; release integration owns them.
- No compatibility flags or code paths solely for old packages.
- Bluetooth work only for approved features ([Bluetooth](docs/modules/bluetooth.md)). `hciplayer`
  is patched only for the parametric EQ and Mono / Crossfeed ([peq](docs/modules/peq.md),
  [stereo](docs/modules/stereo.md)). Any other Bluetooth or `hciplayer` change needs a decision
  first.
- Keep module docs concise: behavior, interfaces, constraints, source references. No device-test
  status, planning, history or test inventories.
- Preserve borrowed-code attribution, including the README acknowledgements. Clone references
  outside this repository.
