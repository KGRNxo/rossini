# Components and licenses

| Component | Where | License | Notes |
|---|---|---|---|
| Rossini code | this repo | GPL-3.0-or-later | `LICENSES/GPL-3.0-or-later.txt` |
| Linux kernel (QEMU image) | build/out/vmlinuz from Ubuntu `linux-image-virtual` | GPL-2.0 | not distributed in this repository; source via Ubuntu |
| BusyBox | rootfs/initramfs | GPL-2.0 | host `busybox-static`; corresponding source from Debian/Ubuntu |
| Python 3.13 | rootfs | PSF License | |
| Pillow | rootfs | HPND | pulls FreeType (FTL/GPL-2), libjpeg-turbo, zlib, libpng, lcms2, others as shared libs from the host |
| cryptography | rootfs | Apache-2.0 / BSD | bundles OpenSSL (Apache-2.0) |
| SQLite | via Python | public domain | |
| e2fsprogs (e2fsck) | recovery | GPL-2.0 | |
| Source Serif 4 | assets/fonts | SIL OFL 1.1 | `LICENSES/OFL-SourceSerif4.txt` |
| Inter | assets/fonts | SIL OFL 1.1 | `LICENSES/OFL-Inter.txt` |
| glibc and other shared libraries | rootfs | LGPL-2.1+ and others | copied from the build host by `ldd`; a full per-library list is not generated yet |
| KOReader | **not included** | AGPL-3.0 | future engine candidate; AGPL requires source offer for network use |

Redistributing any image requires shipping or offering the corresponding sources of the GPL/LGPL components; this has not
been prepared and no image is meant for distribution yet.
