# USB DAC XRUN Recovery

**Sources:** `tools/mod_uac2.py`, `test/pod/uac2.py`.

Fixes stock V2.1's USB DAC mode getting stuck in a continuous `Playback error: -32` (`-EPIPE`)
dropout loop after a single ALSA underrun (XRUN).

## Root cause in stock V2.1

Stock's built-in `f_uac2` driver (`work/kernel/vmlinux`, `0x804be71c`–`0x804c0e28`) writes USB
isochronous OUT audio directly to `/dev/snd/pcmC0D0p` from a `system_wq` kernel worker:

- Its UAC2 descriptor advertises an Adaptive sink (`bmAttributes = 0x09`) with `bNumEndpoints = 1`
  (no asynchronous feedback IN endpoint), while `codec_es9069q.ko` clocks the DAC from fixed local
  oscillators without clock adaptation or resampling.
- `pcm_open` (`0x804bfbd8`) calls `SNDRV_PCM_IOCTL_HW_PARAMS` and `SNDRV_PCM_IOCTL_PREPARE` without
  `SW_PARAMS`, so ALSA leaves `runtime->start_threshold = 1` frame on a 128 KiB DMA ring
  (`aic_pcm_hardware` in `soc_aic.ko`: `16,384` frames for `S32_LE` stereo, `32,768` for `S16_LE`).
- `iso_complete` (`0x804c0928`) buffers `64,000` bytes on stream start and `48,000` bytes per
  steady-state chunk (`125.0 ms` at 48 kHz / 32-bit stereo), giving a `16,000`-byte (`41.7 ms`)
  underrun cushion at startup.
- Once clock drift or a transient CPU stall triggers a single XRUN, `u_audio_playback` (`0x804bfe24`)
  drops the failing `48,000`-byte chunk on `-EPIPE` and calls `SNDRV_PCM_IOCTL_PREPARE` on the next
  chunk without resetting `agdev->started`. Because `start_threshold == 1`, DMA starts immediately
  with only one `48,000`-byte chunk (`0` bytes of cushion), so subsequent chunks keep hitting
  `-EPIPE` and dropping whole `125 ms` blocks until the host stops and restarts the stream.

## Fix (`tools/mod_uac2.py`)

Rather than patching the compressed kernel (`recovery-update/xImage` stays stock), `tools/mod_uac2.py`
patches the loadable ALSA platform module `rootfs/module_driver/soc_aic.ko`:

- Replaces the empty 2-instruction `aic_dma_pcm_prepare` (`return 0`) by relocating `.text` to the
  end of the module, appending a 30-instruction position-independent leaf function (`120` bytes, no
  stack frame, no relocations, caller-saved registers only), and updating symbol `120`
  (`aic_dma_pcm_prepare`) so `aic_component.prepare` (`.rel.data` at `+0x310`) resolves to it.
- Only when **all** guards pass — non-NULL `substream`, `runtime`, and `runtime->status`, playback
  stream (`substream->stream == 0`), default `runtime->start_threshold == 1`, ALSA currently in
  XRUN (`runtime->status->state == SNDRV_PCM_STATE_XRUN`, `4`; `snd_pcm_pre_prepare` leaves state
  intact until `snd_pcm_post_prepare` runs after `do_prepare`), and a kernel thread
  (`current->flags & PF_KTHREAD`, bit 21) — it raises `runtime->start_threshold` to
  `(buffer_size >> 2) + (buffer_size >> 3)` (`3/8` of `buffer_size`, `49,152` bytes: `6,144` frames
  for PCM `S32_LE`, `12,288` frames for DSD `S16_LE`).
- **Normal startup and sample-rate switches** (`state == SNDRV_PCM_STATE_SETUP`, `1`) keep
  `start_threshold == 1`, so DMA starts on the first chunk (`64,000 B` on stream open, `48,000 B`
  on an in-stream rate switch) with zero added latency and no stranded chunk on early close.
- **XRUN recovery** (`state == SNDRV_PCM_STATE_XRUN`, `4`) raises `start_threshold` to `49,152 B`
  and holds DMA until two `48,000`-byte chunks (`96,000 B`, 75% of the 128 KiB ring) are queued,
  restoring a `48,000`-byte (`125 ms` at 48 kHz) cushion so playback recovers cleanly instead of
  looping on `-EPIPE`. Closing the stream mid-prefill (`PREPARED`) drops cleanly, and reopening
  resets `start_threshold` to `1`.
- Userspace playback (`hciplayer`, `aplay`, `usbdacbtplay`, `bluealsa`) has `PF_KTHREAD == 0` and
  is unaffected.

## Constraints and known limitations

- Stock `soc_aic.ko` is pinned by SHA-256, ELF headers, `.text` layout, symbol `120`, and the
  `aic_component.prepare` relocation; any mismatch fails the build. Mode and mtime stay stock.
- This is a kernel module edit, not a `demo` hook: `/mnt/mmc/m1plus-off` does not disable it.
- Clock drift between a host PC and the M1 Plus oscillator is inherent to stock's feedback-free UAC2
  gadget. A host that runs noticeably slower than the player can still hit an isolated XRUN after
  extended playback, but the stream now self-recovers with a `48,000`-byte cushion (~30 min at
  70 ppm, 48 kHz) instead of getting stuck in continuous dropouts.
