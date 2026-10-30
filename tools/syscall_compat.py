#!/usr/bin/env python3
"""Which Linux syscalls does the Rossini userland use, and does the target kernel have them?

  syscall_compat.py unistd <path to kernel arch/arm/include/asm/unistd.h>   -> list of syscall names the kernel defines
  syscall_compat.py trace <rootfs dir> <kernel unistd.h> -- <cmd...>        -> run cmd in the ARM rootfs with qemu-arm -strace,
                                                                              print the syscalls it used that the kernel lacks
The comparison is a static check against the kernel's syscall table. It does not prove runtime behaviour: a missing syscall that the
userland probes and falls back from (getrandom, statx, ...) is reported as "missing" and must be judged separately (see docs)."""
import os
import re
import subprocess
import sys

# 32-bit ARM names in strace output that map to a different kernel name
ALIASES = {"clock_gettime64": "clock_gettime", "clock_nanosleep_time64": "clock_nanosleep", "futex_time64": "futex",
           "clock_settime64": "clock_settime", "ppoll_time64": "ppoll", "pselect6_time64": "pselect6", "utimensat_time64": "utimensat",
           "clock_getres_time64": "clock_getres", "timerfd_settime64": "timerfd_settime", "timerfd_gettime64": "timerfd_gettime",
           "mq_timedsend_time64": "mq_timedsend", "mq_timedreceive_time64": "mq_timedreceive", "rt_sigtimedwait_time64": "rt_sigtimedwait",
           "recvmmsg_time64": "recvmmsg", "sched_rr_get_interval_time64": "sched_rr_get_interval", "io_pgetevents_time64": "io_pgetevents",
           "semtimedop_time64": "semtimedop"}


def kernel_syscalls(unistd_text):
    """Names of __NR_xxx defined by an ARM unistd.h (plus __NR_SYSCALL_BASE-relative ones)."""
    names = set(re.findall(r"#define\s+__NR_([a-z0-9_]+)\s+\(__NR_SYSCALL_BASE\+\s*\d+\)", unistd_text))
    names |= set(re.findall(r"#define\s+__NR_([a-z0-9_]+)\s+\(__NR_SYSCALL_BASE\+\s*\w+\)", unistd_text))
    return names


def traced_syscalls(strace_text):
    """Unique syscall names in `qemu-arm -strace` output ('1234 openat(AT_FDCWD, ...' lines)."""
    return set(m.group(1) for m in re.finditer(r"^\d+\s+([a-z_0-9]+)\(", strace_text, re.M))


def missing(used, available):
    return sorted(n for n in (ALIASES.get(u, u) for u in used) if n not in available)


def main(argv):
    if argv[0] == "unistd":
        print("\n".join(sorted(kernel_syscalls(open(argv[1]).read()))))
        return 0
    if argv[0] == "trace":
        root, unistd = argv[1], argv[2]
        cmd = argv[argv.index("--") + 1:]
        avail = kernel_syscalls(open(unistd).read())
        r = subprocess.run(["qemu-arm", "-L", root, "-strace"] + cmd, capture_output=True, text=True, cwd=root)
        used = traced_syscalls(r.stderr)
        print(f"{len(used)} distinct syscalls used, exit code {r.returncode}")
        print("not in the target kernel:", ", ".join(missing(used, avail)) or "none")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
