# Development

```bash
python3 -m unittest discover -s tests -t . -k unit -k integration     # fast, ~10 s
python3 tools/build_images.py && python3 -m unittest tests.qemu.test_qemu   # QEMU boot chain, ~7 min without KVM
```
Linux needs: python3, Pillow, cryptography, busybox-static, squashfs-tools, cpio, e2fsprogs, qemu-system-x86, linux-image-virtual.
macOS: `./tools/setup-macos.command` (Colima + Docker for the Linux part; the QEMU/Linux path has been run on Linux only, the macOS scripts are untested).

Preview the shell:
```python
import tempfile; from rossini.shell.demo import make_app
app, _ = make_app(tempfile.mkdtemp()); app.render().save("home.png")
```
Dev signing keys are generated into `build/out/keys` on first build and are never committed; release keys must be generated and held offline.
Fonts: `ROSSINI_FONT_DIR` overrides `assets/fonts`.
