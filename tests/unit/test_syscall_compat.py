import importlib.util
import os
import unittest

spec = importlib.util.spec_from_file_location("sc", os.path.join(os.path.dirname(__file__), "..", "..", "tools", "syscall_compat.py"))
sc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sc)
UNISTD = "/home/user/katadelos/linux-3.0.35-lab126/arch/arm/include/asm/unistd.h"


class SyscallCompat(unittest.TestCase):
    def test_parsers(self):
        self.assertEqual(sc.traced_syscalls("123 openat(AT_FDCWD,\"x\",O_RDONLY) = 3\n123 getrandom(0x1,8,1) = 8\n    garbage\n"), {"openat", "getrandom"})
        self.assertEqual(sc.missing({"futex_time64", "getrandom", "read"}, {"futex", "read"}), ["getrandom"])
        self.assertEqual(sc.kernel_syscalls("#define __NR_read\t\t\t(__NR_SYSCALL_BASE+  3)\n#define __NR_x (__NR_SYSCALL_BASE+ 5)\n"), {"read", "x"})

    @unittest.skipUnless(os.path.exists(UNISTD), "Lab126 kernel source not available")
    def test_real_table_of_kernel_3_0_35(self):
        have = sc.kernel_syscalls(open(UNISTD).read())
        for n in ("read", "epoll_create1", "dup3", "pipe2", "accept4", "eventfd2", "inotify_init1", "futex", "clock_gettime", "recvmmsg"):
            self.assertIn(n, have, n)
        for n in ("getrandom", "memfd_create", "statx", "renameat2", "copy_file_range", "clock_gettime64", "futex_time64"):
            self.assertNotIn(n, have, n)  # added after 3.0


if __name__ == "__main__":
    unittest.main()
