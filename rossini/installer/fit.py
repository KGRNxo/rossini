"""Builds the unsigned FIT image that Amazon's U-Boot `booteink` expects for the 2024 Kindle (code name Rossini):
a flattened image tree stored in the eMMC partition `kernel`, with a configuration named `conf-<dtb name>`.
Facts from the published U-Boot source (see boards/_families/amazon-rossini.json). An *unsigned* image is rejected by a
locked production device; this exists for engineering/unlocked devices and for tests. Addresses are DRAM base + 0x8000
(MT8110 DRAM starts at 0x40000000) and unverified."""
import os
import shutil
import subprocess
import tempfile

DRAM_BASE = 0x40000000
KERNEL_LOAD = DRAM_BASE + 0x8000
MAX_BYTES = 65536 * 512  # booteink refuses images larger than 64K blocks (32 MiB)
SAFE_NAME = set("abcdefghijklmnopqrstuvwxyz0123456789-_")


def its(kernel, dtb, dtb_name, ramdisk=None, anti_rollback=None, bootargs=None):
    """Return the image source text. dtb_name e.g. 'mt8110-cava' -> configuration 'conf-mt8110-cava'."""
    if not dtb_name or set(dtb_name) - SAFE_NAME:
        raise ValueError("dtb_name may only contain a-z 0-9 - _")
    ver = f"\n\t\t\tanti-rollback-version = <{int(anti_rollback)}>;" if anti_rollback is not None else ""
    rd_node = rd_ref = ""
    if ramdisk:
        rd_node = f"""
		ramdisk {{
			description = "rossini initramfs";
			data = /incbin/("{ramdisk}");
			type = "ramdisk"; arch = "arm"; os = "linux"; compression = "none";
			load = <0x{DRAM_BASE + 0x2000000:08x}>; entry = <0x{DRAM_BASE + 0x2000000:08x}>;
			hash-1 {{ algo = "sha256"; }};
		}};"""
        rd_ref = '\n\t\t\tramdisk = "ramdisk";'
    return f"""/dts-v1/;
/ {{
	description = "Rossini OS";
	#address-cells = <1>;
	images {{
		kernel {{
			description = "Linux (zImage)";
			data = /incbin/("{kernel}");
			type = "kernel"; arch = "arm"; os = "linux"; compression = "none";
			load = <0x{KERNEL_LOAD:08x}>; entry = <0x{KERNEL_LOAD:08x}>;
			hash-1 {{ algo = "sha256"; }};
		}};
		fdt {{
			description = "{dtb_name}";
			data = /incbin/("{dtb}");
			type = "flat_dt"; arch = "arm"; compression = "none";
			hash-1 {{ algo = "sha256"; }};
		}};{rd_node}
	}};
	configurations {{
		default = "conf-{dtb_name}";
		conf-{dtb_name} {{
			description = "Rossini OS on {dtb_name}";
			kernel = "kernel";
			fdt = "fdt";{rd_ref}{ver}
		}};
	}};
}};
"""


def build(out, kernel, dtb, dtb_name, ramdisk=None, anti_rollback=None):
    mk = shutil.which("mkimage")
    if not mk:
        raise RuntimeError("mkimage (u-boot-tools) fehlt")
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "image.its")
        with open(src, "w") as f:
            f.write(its(os.path.abspath(kernel), os.path.abspath(dtb), dtb_name, os.path.abspath(ramdisk) if ramdisk else None, anti_rollback))
        r = subprocess.run([mk, "-f", src, out], capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError("mkimage failed: " + r.stderr.strip())
    size = os.path.getsize(out)
    if size > MAX_BYTES:
        os.unlink(out)
        raise ValueError(f"FIT is {size} bytes; Amazon's U-Boot refuses images above {MAX_BYTES}")
    return size
