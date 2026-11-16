# Documentation

## Guides

| Guide | Use it for |
|---|---|
| [Install](install.md) | Prepare the card, update the player, disable the mod or restore stock |
| [User guide](guide.md) | Get started with browsing and playback |
| [Library and playback](library-guide.md) | Browse, manage the queue and set up artist photos |
| [Settings](settings-guide.md) | Find settings and their device paths |
| [Equalizer](equalizer-guide.md) | Adjust EQ and manage presets |
| [Features and extras](features-guide.md) | Radio, Subsonic, podcasts, audiobooks and scrobbling |
| [Development](workflow.md) | Set up uv, build, test, format and prepare releases |

## References

| Reference | Contents |
|---|---|
| [Architecture](architecture.md) | Build overview and the index of every module doc |
| [UI](ui.md) | Preview, layout rules, fonts, assets and rendering |
| [Firmware](firmware.md) | Stock hashes, updater behaviour, partitions and space recovery |
| [History](history.md) | Milestones, device findings and lessons |
| [Payload](modules/payload.md) | Segment layout, trampolines, stock calls and hooks |
| [Addresses](modules/addresses.md) | Stock symbols, offsets and record layouts |
| [Safety](modules/safety.md) | Allowed entry points and required invariants |
| [Validation](modules/validation.md) | Test boundaries and what they prove |

Read the relevant module doc before changing a feature.

## Source layout

| Directory | Contents |
|---|---|
| `tools/` | Host build, validation, assets, previews and binary analysis |
| `patch/` | Runtime C payload, stock offsets and linker script |
| `test/` | MIPS/host tests and package goldens |
| `assets/` | Fonts, icon sources, boot logo and wallpaper |

Use `tools/pod.py` for current pins and sources.
