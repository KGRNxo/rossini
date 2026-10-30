# Kernel patches

Amazon's kernels are third-party GPL-2.0 sources and are fetched at build time (never copied here). The patches in this directory only make
them compile with a current toolchain (GCC 13, binutils 2.42); they do not change behaviour.

| Directory | Applies to | Source |
|---|---|---|
| `lab126-3.0.35/` | Lab126 Linux 3.0.35 (i.MX6SL: PW2, PW3, Voyage, KT2, Oasis 1) | https://github.com/katadelos/linux-3.0.35-lab126 @ 7ac2585f (re-upload of Amazon's `Kindle_src_5.10.1.1` release) |
| `amazon-rossini-4.9/` | Linux 4.9 of the Kindle 2024 release (MediaTek, "Rossini") | `gplrelease/linux-4.9.tar.gz` in Amazon's `Kindle_src_5.19.6_4832540042.tar.gz` (sha256 in boards/_families/amazon-rossini.json) |

Changes: ARM assembler section/type syntax (`#alloc` -> `"a"`, `#object` -> `%object`), a `compiler-gcc13.h` stub (3.0.35), disabling a
blanket `-Werror` (4.9). Extra compiler flags for 4.9 are passed on the command line by `tools/build-kt6-kernel.sh`.
`tests/unit/test_kernel_patches.py` checks that the patches still apply to the pinned sources.
