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
| PyMuPDF / MuPDF | rootfs (PDF) | **AGPL-3.0** (or commercial from Artifex) | Included in images: any distributed image must offer corresponding source under the AGPL; Rossini's GPL-3.0-or-later code is compatible with AGPL-3.0. Decide before any distribution: comply with AGPL or license MuPDF commercially |
| pyphen | rootfs | GPL-2.0+ / LGPL-2.1+ / MPL-1.1 | hyphenation dictionaries come from LibreOffice (LGPL/MPL) |
| djvulibre (ddjvu, djvused) | rootfs (DjVu) | GPL-2.0+ | run as separate processes |
| libarchive (bsdtar) | rootfs (CBR) | BSD-2-Clause | |
| wpa_supplicant | Buildroot ARM image | BSD-3-Clause | |
| Buildroot | build/arm | GPL-2.0+ | build system only |
| Amazon Linux kernels (3.0.35-lab126, 4.9) | fetched at build time, patches in kernel/patches | GPL-2.0 | Amazon's published source releases; BUILD_HOW-TO disclaimers apply to their build scripts |
| Amazon U-Boot (UFBL) | read for analysis only, not built or shipped | GPL-2.0+ | |
| musl libc, Buildroot internal toolchain | build/arm lab126 image | MIT / GPL | |
| KOReader | **not included** | AGPL-3.0 | not needed any more for PDF/DjVu/MOBI; remains a candidate for crengine-quality layout |

Redistributing any image requires shipping or offering the corresponding sources of the GPL/LGPL components; this has not
been prepared and no image is meant for distribution yet.
