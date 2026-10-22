# v6 编译说明 —— 在另一台机器上「基于 v5」重编

> 适用：你已经在某台机器上编过 v5（`cepheus-crDroid-Droidspaces-v5.zip`），现在换一台机器（或同一台重编）要出 v6。
> 结论先说：**v5 → v6 只改 1 个文件、+5 行代码**，其余（源码 commit、KSU pin、`.config`、AK3 骨架、ramdisk 处理）全部逐字节不变。所以这就是「v5 的构建流程 + 多打一个补丁」。

---

## 1. 变更对照表

| 维度 | v5 | v6 | 变化 |
|---|---|---|---|
| 源码基线 | `raystef66/kernel_xiaomi_cepheus` @ `6ad047b7`（分支 `16.0-ksun`） | 同 | ❌ 不变 |
| KernelSU-Next | pin `00cb93e0`（实编 `v3.0.1-legacy-88`） | 同 | ❌ 不变 |
| `.config` | `cepheus-crDroid-Droidspaces-v5-config.txt` | 同 | ❌ 不变 |
| 工具链 | 你编 v5 用的那套 | **建议照抄** | ❌ 不变 |
| AK3 骨架 | 从 v5 zip 原样抠出 | 同 | ❌ 不变 |
| 打包方式 | 只换 `Image.gz-dtb`，不碰 ramdisk / dtbo | 同 | ❌ 不变 |
| **源码改动** | **0** | **`fs/file.c` +5 行** | ✅ **唯一变量** |
| 内核版本串 | `4.14.355-openela-Droidspaces` | 同 | ❌ 不变（见坑 6） |

一次只动一个变量，就是为了「刷进去出问题时能一句话归因」。

---

## 2. 改动本体

`fs/file.c` 里 `close_range(2)` backport 的 `__range_close()` 少了上游 5.9 的 fd 表裁剪：

```diff
 static inline void __range_close(struct files_struct *cur_fds, unsigned int fd,
 				 unsigned int max_fd)
 {
+	/* Make sure we're using the correct maximum value. */
+	spin_lock(&cur_fds->file_lock);
+	max_fd = min(last_fd(files_fdtable(cur_fds)), max_fd);
+	spin_unlock(&cur_fds->file_lock);
+
 	while (fd <= max_fd) {
 		struct file *file;
```

- `max_fd` 不裁剪 → glibc / systemd 传 `close_range(3, ~0U, 0)`（`max_fd = 0xFFFFFFFF`）→ `fd` 是 `unsigned int`，涨到 `0xFFFFFFFF` 后 `++` 溢出回 `0`，`0 <= 0xFFFFFFFF` 恒真 → **系统调用里死循环**，且空 fd 表时 `cond_resched()` 不执行 → 信号投不进去，`SIGKILL` 也杀不掉。
- Android 的 bionic **从不调** `close_range`，所以宿主没事；Ubuntu 22.04 的 glibc 2.35 / systemd 249 大量用它 → **只有容器的 systemd 卡在 `initializing`**。
- 同文件里的 `__range_cloexec()`（CLOEXEC 分支）**有**这三行 → 证明是移植遗漏，不是设计。
- 对照：网友 v2.00（`aa587668`）**根本没有** `close_range` backport → 返回 `ENOSYS` → glibc 回退逐个 `close()` → 容器正常。

补丁文件已随仓库提供：`patches/0001-fs-clamp-max_fd-in-close_range-backport.patch`（已用 `git apply --check` 验证）。

---

## 3. 路线 A：直接在「编 v5 的那棵树」上重编（推荐，最省事）

```bash
cd <你编 v5 的内核源码目录>

# --- 前置自检（3 条，必须全过）---
git rev-parse HEAD          # 必须 = 6ad047b70d809d7dee1fc090dbe2c252ff43b7eb
readlink drivers/kernelsu   # 必须 = ../KernelSU-Next/kernel
test -f KernelSU-Next/kernel/Kconfig && echo KSU_OK

# --- 打补丁（二选一）---
git apply /path/to/patches/0001-fs-clamp-max_fd-in-close_range-backport.patch
# 或（幂等、锚点找不到会报错退出）
python3 /path/to/scripts/apply-kernel-fixes.py .

# --- 确认真的打上了 ---
grep -c 'min(last_fd(files_fdtable(cur_fds)), max_fd)' fs/file.c    # 必须输出 1

# --- 用你编 v5 的同一套命令重编（这里给参考参数，替换成你自己的）---
export ARCH=arm64 SUBARCH=arm64
export PATH=<clang>/bin:$PATH
export LLVM=1
export CROSS_COMPILE=aarch64-linux-gnu-
export CROSS_COMPILE_ARM32=arm-linux-gnueabi-
make -j"$(nproc)" O=out CC=clang AR=llvm-ar LD=ld.lld NM=llvm-nm \
     OBJCOPY=llvm-objcopy OBJDUMP=llvm-objdump STRIP=llvm-strip \
     HOSTLDLIBS_dtc=-lyaml \
     Image.gz-dtb
```

> 上面这套与上游作者的 `build.sh` 一致（clang `r416183b1` + `ld.lld`），只多了 `HOSTLDLIBS_dtc=-lyaml`（见坑 10）。
> 注意产物目标必须是 **`Image.gz-dtb`**（AK3 的 `write_boot` 找的是这个名字），不是 `Image`。

然后跳到第 5 节打包。

---

## 4. 路线 B：全新机器，从零复现

```bash
# 1) 源码（pinned branch + commit 断言）
git clone --depth=1 --single-branch -b 16.0-ksun \
  https://github.com/raystef66/kernel_xiaomi_cepheus.git kernel
cd kernel
test "$(git rev-parse HEAD)" = "6ad047b70d809d7dee1fc090dbe2c252ff43b7eb" || echo "!! 上游 head 已变，先复核再编"

# 2) KernelSU-Next（用 tar 包，别用 git checkout <sha>：该仓库 partial-clone，
#    CI 上会报 "unable to read tree"）
curl -fsSL --retry 4 -o /tmp/ksu.tar.gz \
  https://codeload.github.com/KernelSU-Next/KernelSU-Next/tar.gz/00cb93e0bc8bf3ca3680c7e8a3d7cf11d0b59071
mkdir -p KernelSU-Next
tar -xzf /tmp/ksu.tar.gz -C KernelSU-Next --strip-components=1
test -f KernelSU-Next/kernel/Kconfig && echo KSU_OK
readlink drivers/kernelsu      # 应为 ../KernelSU-Next/kernel（仓库自带软链）

# 3) 补丁
python3 /path/to/scripts/apply-kernel-fixes.py .

# 4) 配置（必须放在 KSU 目录就位之后再 olddefconfig，见坑 2）
mkdir -p out
cp /path/to/cepheus-crDroid-Droidspaces-v5-config.txt out/.config
make ARCH=arm64 SUBARCH=arm64 O=out olddefconfig

# 5) 手动核对 olddefconfig 没把关键项改掉
for k in CONFIG_KSU CONFIG_KSU_MANUAL_HOOK CONFIG_KSU_SUSFS CONFIG_POSIX_MQUEUE \
         CONFIG_CFS_BANDWIDTH CONFIG_MACH_XIAOMI_CEPHEUS CONFIG_OVERLAY_FS; do
  grep -m1 -E "^(${k}=|# ${k} is not set)" out/.config || echo "!! $k 消失了"
done
grep -m1 '^CONFIG_LOCALVERSION=' out/.config          # 必须 = "-Droidspaces"
grep -m1 '^# CONFIG_SCHED_WALT' out/.config           # 必须 is not set

# 6) 编译（参数同第 3 节）
```

工具链参考：CI 用的是 AOSP clang `r416183b1`。**如果你 v5 用的是别的 clang，就照抄 v5 那套**——换工具链等于多加一个变量。

---

## 5. 打包（两条路线通用）

```bash
rm -rf /tmp/ak3 && cp -r /path/to/ak3 /tmp/ak3          # v5 zip 里的 AK3 骨架，原样
cp out/arch/arm64/boot/Image.gz-dtb /tmp/ak3/

cd /tmp/ak3
sed -i 's|^kernel.string=.*|kernel.string=cepheus Droidspaces v6 (close_range fix) 4.14.355-openela-Droidspaces|' anykernel.sh
grep -m1 '^kernel.string=' anykernel.sh

zip -r9 /tmp/cepheus-crDroid-Droidspaces-v6.zip . -x '*.zip'
sha256sum /tmp/cepheus-crDroid-Droidspaces-v6.zip
```

`anykernel.sh` 里应保持：`do.devicecheck=1`、`device.name1=cepheus`、`do.modules=0`、`BLOCK=/dev/block/bootdevice/by-name/boot`、`IS_SLOT_DEVICE=0`、`dump_boot` → `write_boot`（**保留原 ramdisk / dtb / cmdline，只换内核，不碰 dtbo**）。

---

## 6. 刷机前产物自检

```bash
unzip -l cepheus-crDroid-Droidspaces-v6.zip | head            # 要有 Image.gz-dtb / anykernel.sh / tools/
mkdir -p /tmp/chk && unzip -o -q cepheus-crDroid-Droidspaces-v6.zip -d /tmp/chk
zcat /tmp/chk/Image.gz-dtb | strings | grep -m1 -E '4\.14\.355'      # 4.14.355-openela-Droidspaces
zcat /tmp/chk/Image.gz-dtb | strings | grep -m2 -E 'v3\.[0-9]+\.[0-9]+-legacy'  # KSU 实编版本
```

**KSU 版本以 Image 里的字符串为准，永远不要信 `anykernel.sh` 的注释**——v5 的注释写 `v3.2.0-legacy`，实编是 `v3.0.1-legacy(33136)`，就是靠这个才发现管理器版本要对齐。

---

## 7. 刷机后验证（这次的重点不是能开机，是容器能起来）

```bash
adb shell uname -r          # 4.14.355-openela-Droidspaces（和 v5 一样，看不出改没改）
```

真正要验的是容器里的 systemd：

```bash
# 启动 ubuntu 容器后，取容器 init pid
PID=$(adb shell "su -c 'ps -A -o pid,comm | grep -w systemd | head -1'" | awk '{print $1}')
adb shell "su -c 'echo \"export PATH=/usr/sbin:/usr/bin:/sbin:/bin; systemctl is-system-running\" \
            | nsenter -t $PID -m -p /bin/sh'"
# 期望: running        （v5 上是 initializing，永远卡住）
```

可选：定向回归测试（**只在 systemd 已经正常之后再做**）——在容器里编一个最小 C 程序，直接打 `close_range(3, ~0U, 0)`：

```c
#include <unistd.h>
#include <sys/syscall.h>
int main(void){ return syscall(436, 3u, ~0u, 0u) < 0; }   /* 436 = close_range on arm64 */
```

```bash
gcc -O2 -o /tmp/cr /tmp/cr.c && time /tmp/cr
# v6: 立刻返回；未打补丁的 v5: 直接挂死，而且 SIGTERM/SIGKILL 都杀不掉，只能重启手机
```

⚠️ 所以这个测试**别在未打补丁的机器上随手跑**，会把容器 CPU 打满且无法回收（v5 上就是这么卡死的）。

---

## 8. 坑清单

1. **`drivers/kernelsu` 是符号链接**（→ `../KernelSU-Next/kernel`）。用 Git for Windows 克隆、或把源码打包成 zip 传输时，软链会退化成普通文本文件 → 编译直接报错。**在 Linux 上编，或确认 `git config core.symlinks true`**。
2. **顺序不能反**：`drivers/Kconfig` 里 `source "drivers/kernelsu/Kconfig"`，KSU 目录不存在时这个 source 会被跳过 → `CONFIG_KSU` 直接**从 Kconfig 里消失**，`olddefconfig` 会静默把 `CONFIG_KSU=y` 丢掉 → 编出来一个没 root 的内核，而且不报错。**先放 KSU 再 olddefconfig，然后 grep 验证 `CONFIG_KSU=y`**。
3. **KSU 管理器 versionCode 必须 ≤ 内核 KSU 的 versionCode**。v6 内核仍是 33136 → 管理器用 `KernelSU_Next_v3.2.0_33129`；装 3.4.0(33294) 会报 "Kernel update required" 且 su 不可用。
4. **源码头必须对上**：`4.14.355` 这棵（raystef66）。`crdroidandroid/android_kernel_xiaomi_sm8150`（4.14.356）是**另一棵树**，从那儿编出来的在本机开不了机（已实测）。认版本号 355，不认组织名。
5. **`LOCALVERSION="-Droidspaces"` 别改**，否则版本串变、AK3 横幅和现有识别逻辑都跟着对不上。
6. **版本串相同 = 分不出 v5 / v6**。想区分只能看 `anykernel.sh` 的 `kernel.string`（recovey 刷机时显示），或者改 `LOCALVERSION`——但那会破坏「只动一个变量」，不建议。
7. **`olddefconfig` 会静默补/删选项**。它跑完必须 diff 一遍最终 `out/.config` 和 `cepheus-crDroid-Droidspaces-v5-config.txt`，确认关键项没被翻转（尤其 `KSU`、`SCHED_WALT`、`CFS_BANDWIDTH`）。
8. **任何格式的 CRLF 都可能刷机失败**。C 源码里 CRLF 无所谓，但 `anykernel.sh` / `update-binary` 被转成 CRLF 时 TWRP 会报 `\r` 语法错。仓库已用 `.gitattributes` 把 workflow / python / patch 钉成 LF。
9. **卡死过的机器必须先重启**。v5 那批 `R` 状态死循环进程 `SIGKILL` 无效，只能重启清；容器 `run_at_boot=0`，不会自启。
10. **`scripts/dtc` 缺 libyaml 会挂**（这次 CI 第一次编译就死在这）。症状很长但很好认：
    ```
    ld.lld: error: undefined symbol: yaml_emitter_initialize
    >>> referenced by yamltree.c
    >>>               scripts/dtc/yamltree.o:(yaml_tree)
    make[3]: *** [scripts/Makefile.host:111: scripts/dtc/dtc] Error 1
    ```
    两件事一起做：`apt install libyaml-dev pkg-config`，并在 make 命令行显式加 **`HOSTLDLIBS_dtc=-lyaml`**（保证 `-lyaml` 出现在对象文件之后）。注意这是**宿主工具**链问题，跟内核配置无关，换 `.config` 不会好。
11. **别随手加 `LLVM_IAS=1`**。上游作者自己的 `build.sh` 也没设，4.14 这棵老树的汇编用集成汇编器容易出问题——照抄他能跑的那套。

---

## 9. 仓库文件与云端编译

| 文件 | 作用 |
|---|---|
| `BUILD-v6.md` | 本文件：v5→v6 的编译差异、两条路线、自检、坑清单 |
| `patches/0001-fs-clamp-max_fd-in-close_range-backport.patch` | 标准 git patch，`git apply` 直接用 |
| `scripts/apply-kernel-fixes.py` | 幂等补丁器，锚点找不到**报错退出**（防上游改动后静默跳过） |
| `cepheus-crDroid-Droidspaces-v5-config.txt` | v5 的 `.config`，v6 原样复用 |
| `ak3/` | 从 v5 zip 原样提取的 AnyKernel3 骨架（含 `anykernel.sh`、`tools/`、`META-INF/`） |
| `.github/workflows/build.yml` | GitHub Actions 云端编译，源码 commit / KSU pin / config 全部锁定 |
| `PATCH_NOTES.md` | 完整证据链（症状、sysrq 栈、根因、验证） |

云端触发：

```bash
gh workflow run build.yml --repo lgpay/cepheus-droidspaces-kernel \
  -f artifact_name=cepheus-crDroid-Droidspaces-v6.zip
gh run list --repo lgpay/cepheus-droidspaces-kernel --limit 3
```

产物会同时上传成 artifact 并挂到同名 release 上。
