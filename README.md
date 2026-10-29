# Rossini OS

An independent, open-source operating system for e-readers, aiming first at the Amazon Kindle Basic (2024, KT6).
Rossini OS is the product; Rossini Reader is an application inside it; KOReader is, at most, a possible rendering engine later.

**Honest status (read this first):** nothing here runs on a Kindle yet. The userland (library, reader, shell, updater,
recovery, installer logic) is implemented and tested on a PC and boots in QEMU on an x86_64 development target. There is
no Kindle kernel, device tree, bootloader work, E-Ink driver or flashing procedure, and the installer refuses every real device.
The exact state per component is in [docs/STATUS.md](docs/STATUS.md); what blocks the hardware port is in
[docs/hardware/README.md](docs/hardware/README.md).

## Try it

```bash
./tools/setup-macos.command      # once (macOS); on Linux: pip install -r requirements.txt
./tools/build-all.command        # squashfs slots, initramfs, recovery, signed update packages -> build/out
./tools/test-all.command         # unit + integration + QEMU boot chain (QEMU part takes ~7 minutes without KVM)
```

Preview the shell without any build: `python3 -c "from rossini.shell.demo import make_app; ..."` (see docs/development/README.md).

## Layout

| Path | Content |
|---|---|
| `rossini/library` | SQLite library, metadata extraction, indexer |
| `rossini/reader` | decoders (epub, fb2, txt, cbz), pagination, reading session |
| `rossini/display` | E-Ink refresh policy and backends, evdev input and gestures |
| `rossini/shell` | UI (home, library, reader, discover, settings) |
| `rossini/settings`, `rossini/system` | settings store, power policy, sysfs HAL, PID 1 init, supervisor, boot self-test |
| `rossini/connect` | OPDS client, WLAN transfer server, folder sync |
| `rossini/updater` | signed packages, A/B boot state, installer of slot images |
| `rossini/installer`, `rossini/recovery`, `rossini/sdk` | installation gate, recovery tools, app manifest |
| `boards/` | per-device profiles (all Kindle profiles are `research`) |
| `system/init` | initramfs stage (bootloader stand-in for QEMU), recovery init |
| `tools/` | macOS/Linux build, test, release and diagnosis scripts |
| `docs/`, `LICENSES/` | architecture, hardware, installation, recovery, development, licenses |

The repository layout deliberately differs from the first sketch (`applications/`, `shell/`, ...): all Python code lives in
one importable package so components share interfaces without path hacks. See docs/architecture/README.md.

License: GPL-3.0-or-later for Rossini code, see [LICENSES/](LICENSES/) and docs/architecture/licenses.md for third-party components.
