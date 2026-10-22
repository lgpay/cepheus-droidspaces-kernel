# v6 patch notes — `close_range()` infinite loop fix

## Symptom

On v5 (`4.14.355-openela-Droidspaces`), a Droidspaces **Ubuntu 22.04** container starts
(PID allocated, NAT and port forwards come up) but `systemd` never leaves `initializing`.
Every service that forks dies as a `R` (running) task:

```
root 3911 3877 ... 0 0 R (mount)
root 3912 3877 ... 0 0 R (journald)
root 3913 3877 ... 0 0 R (mount)
root 3914 3877 ... 0 0 R (ister.sh)
```

They keep burning CPU indefinitely, `SigPnd: 0000000000000100` (SIGKILL pending) but
`kill -9` never works, and it happens on both cgroup v1 (`--force-cgroupv1`) and cgroup v2.

## Root cause

`raystef66/kernel_xiaomi_cepheus` backports `close_range(2)` from Linux 5.9 into
`fs/open.c` + `fs/file.c`. The backported helper is missing the fd-table clamp that
upstream 5.9 has:

```c
/* fs/file.c, as shipped in v5's base tree */
static inline void __range_close(struct files_struct *cur_fds, unsigned int fd,
                                 unsigned int max_fd)
{
        while (fd <= max_fd) {              /* max_fd never clamped */
                file = pick_file(cur_fds, fd++);   /* fd is unsigned int */
                if (!file)
                        continue;
                filp_close(file, cur_fds);
                cond_resched();
        }
}
```

Upstream Linux 5.9 has this at the top of the same function:

```c
        spin_lock(&cur_fds->file_lock);
        max_fd = min(last_fd(files_fdtable(cur_fds)), max_fd);
        spin_unlock(&cur_fds->file_lock);
```

Without it, `max_fd` is whatever userspace passed. glibc's `posix_spawn()` and
systemd's `close_all_fds()` call `close_range(3, ~0U, ...)`, i.e. `max_fd = 0xFFFFFFFF`.
`fd` is an `unsigned int`, so it counts up to `0xFFFFFFFF`, increments to `0`, and
`0 <= 0xFFFFFFFF` remains true — **an unconditional infinite loop inside the syscall**.
`cond_resched()` only runs on the non-NULL path, so on an empty fd table the loop never
yields and the task spins in kernel mode forever, which is why SIGKILL cannot be
delivered.

The same file's `__range_cloexec()` (`CLOSE_RANGE_CLOEXEC` path) *does* contain the
clamp, which confirms this was a porting omission rather than an intentional design.

## Evidence

Per-CPU backtrace from the device while the container was stuck:

```
sysrq: CPU0..CPU7:
Call trace:
  dump_backtrace
  showacpu
  flush_smp_call_function_queue
  generic_smp_call_function_single_interrupt
  handle_IPI
  gic_handle_irq
  el1_irq
  pick_file+0x114/0x160
  SyS_close_range+0xc/0x20
  __sys_trace_return
```

All eight CPUs were inside `SyS_close_range() -> pick_file()`.

Why only containers are affected: Android's bionic libc never calls `close_range(2)`,
so the host is fine. Ubuntu 22.04 ships glibc 2.35 / systemd 249, both of which use it
for fd hygiene around `fork`/`exec`.

Why the web kernel (InfiniR v2.00, `aa587668`) works: it has **no** `close_range`
backport at all (`fs/open.c` and `fs/file.c` there contain no `close_range` symbol), so
the syscall returns `ENOSYS` and glibc/systemd fall back to closing descriptors one by
one.

This also rules out the earlier hypotheses: it is unrelated to KernelSU-Next version,
`--force-cgroupv1`, `SCHED_WALT`, cgroup throttling, or the container configuration —
`v5` and `v2.00` use the same `.config` for all KSU options.

## Fix

`scripts/apply-kernel-fixes.py` restores the upstream clamp in `fs/file.c`. It is
idempotent and fails loudly if the anchor cannot be found (so an upstream change can
never silently skip the patch):

```diff
@@ static inline void __range_close(struct files_struct *cur_fds, unsigned int fd,
 {
+	/* Make sure we're using the correct maximum value. */
+	spin_lock(&cur_fds->file_lock);
+	max_fd = min(last_fd(files_fdtable(cur_fds)), max_fd);
+	spin_unlock(&cur_fds->file_lock);
+
 	while (fd <= max_fd) {
 		struct file *file;
```

`last_fd()` and `files_fdtable()` are defined earlier in the same file, so no other
changes are required. Behaviour after the patch matches Linux 5.9 exactly: the loop is
bounded by the real fd-table size.

## Building

`.github/workflows/build.yml` builds this kernel on GitHub Actions:

- source: `raystef66/kernel_xiaomi_cepheus` branch `16.0-ksun`, head asserted to be
  `6ad047b70d809d7dee1fc090dbe2c252ff43b7eb`
- KernelSU-Next checked out at `00cb93e0bc8bf3ca3680c7e8a3d7cf11d0b59071` (v5's pin,
  unchanged — only one variable per build)
- `.config`: `cepheus-crDroid-Droidspaces-v5-config.txt` (unchanged)
- toolchain: AOSP clang `r416183b1`
- packaging: the exact AnyKernel3 skeleton from the v5 zip, only `Image.gz-dtb` swapped

Trigger it from the Actions tab (`Build cepheus Droidspaces kernel` → Run workflow) or:

```bash
gh workflow run build.yml --repo lgpay/cepheus-droidspaces-kernel
```

## Verification after flashing

```bash
adb shell uname -r                     # 4.14.355-openela-Droidspaces
# start the ubuntu container, then:
su -c 'echo "export PATH=/usr/sbin:/usr/bin:/sbin:/bin; systemctl is-system-running" \
       | nsenter -t <container-init-pid> -m -p /bin/sh'
# expect: running  (not "initializing")
```

A quick host-side regression check for the syscall itself:

```bash
# 3-arg close_range with max_fd=~0 must return promptly, not hang
# (run inside any process with the container's glibc, e.g. inside the container)
```
