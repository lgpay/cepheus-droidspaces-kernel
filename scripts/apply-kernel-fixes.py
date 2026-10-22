#!/usr/bin/env python3
"""
Apply the close_range() fix to the InfiniR 4.14 kernel tree.

Background
----------
raystef66/kernel_xiaomi_cepheus backports close_range(2) from Linux 5.9 into
fs/open.c + fs/file.c, but its __range_close() helper is missing the
"clamp max_fd to the real fd-table size" step that upstream 5.9 has:

    static inline void __range_close(struct files_struct *cur_fds, unsigned int fd,
                                     unsigned int max_fd)
    {
            while (fd <= max_fd) {
                    file = pick_file(cur_fds, fd++);
                    ...
            }
    }

Callers such as systemd / glibc posix_spawn() use close_range(3, ~0U, ...),
i.e. max_fd = UINT_MAX.  fd is an unsigned int, so it walks up to 0xFFFFFFFF,
increments to 0, and `0 <= UINT_MAX` stays true forever -> a hard infinite
loop inside the syscall, holding the CPU with cond_resched() never reached on
the empty-fd path.  Android's bionic never calls close_range(), so only
containers (Ubuntu with glibc 2.35 / systemd 249) hang.

This script restores the upstream-5.9 clamp:

            spin_lock(&cur_fds->file_lock);
            max_fd = min(last_fd(files_fdtable(cur_fds)), max_fd);
            spin_unlock(&cur_fds->file_lock);

Usage: apply-kernel-fixes.py <kernel-source-root>
Exit code 0 on success (or already applied), non-zero on failure.
"""

import re
import sys
from pathlib import Path

MARKER = "min(last_fd(files_fdtable(cur_fds)), max_fd)"

PATTERN = re.compile(
    r"(static inline void __range_close\(struct files_struct \*cur_fds, unsigned int fd,\s*\n"
    r"[ \t]*unsigned int max_fd\)\s*\n"
    r"\{\s*\n)"
    r"([ \t]*while \(fd <= max_fd\) \{)",
    re.MULTILINE,
)

CLAMP = (
    "\t/* Make sure we're using the correct maximum value. */\n"
    "\tspin_lock(&cur_fds->file_lock);\n"
    "\tmax_fd = min(last_fd(files_fdtable(cur_fds)), max_fd);\n"
    "\tspin_unlock(&cur_fds->file_lock);\n"
    "\n"
)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: apply-kernel-fixes.py <kernel-source-root>", file=sys.stderr)
        return 2

    root = Path(sys.argv[1])
    target = root / "fs" / "file.c"
    if not target.is_file():
        print(f"error: {target} not found", file=sys.stderr)
        return 1

    src = target.read_text(encoding="utf-8", errors="surrogateescape")

    if MARKER in src:
        print(f"[skip] {target} already has the fd-table clamp")
        return 0

    match = PATTERN.search(src)
    if not match:
        print(
            "error: __range_close() anchor not found in fs/file.c.\n"
            "       Upstream source changed - re-check the backport manually.\n"
            "       Expected signature: static inline void __range_close(struct files_struct *cur_fds, ...)",
            file=sys.stderr,
        )
        return 1

    fixed = src[: match.start()] + match.group(1) + CLAMP + match.group(2) + src[match.end() :]
    # newline="\n" keeps the C source byte-identical on Windows checkouts too.
    target.write_text(fixed, encoding="utf-8", errors="surrogateescape", newline="\n")

    # Sanity check: the clamp must now be present exactly once.
    check = target.read_text(encoding="utf-8", errors="surrogateescape")
    if check.count(MARKER) != 1:
        print("error: post-patch verification failed", file=sys.stderr)
        return 1

    print(f"[ok] patched {target}")
    for line in check.splitlines():
        if MARKER in line:
            print(f"     + {line.strip()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
