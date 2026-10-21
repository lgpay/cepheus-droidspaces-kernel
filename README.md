# cepheus Droidspaces Kernel (crDroid 16)

A Droidspaces-ready kernel for the Xiaomi Mi 9 (**cepheus**) running **crDroid 16 (Android 16)**, packaged as an [AnyKernel3](https://github.com/osm0sis/AnyKernel3) zip. Kernel release string: `4.14.355-openela-Droidspaces`. It is built from the exact source of the InfiniR kernel shipped in crDroid 16 official builds ([`raystef66/kernel_xiaomi_cepheus`](https://github.com/raystef66/kernel_xiaomi_cepheus), branch `16.0-ksun`, commit `6ad047b7`), using the stock kernel configuration plus a Droidspaces delta — namespaces, `CONFIG_CFS_BANDWIDTH` (`--cpus`), `CONFIG_POSIX_MQUEUE`, overlayfs — with **zero source-code changes**. [KernelSU-Next](https://github.com/KernelSU-Next/KernelSU-Next) with [SUSFS](https://gitlab.com/simonpunk/susfs4ksu) is integrated in manual-hook mode; the version actually compiled in, measured from the built image, is **v3.0.1-legacy-88-g00cb93e0** (see the honesty note below). **Tested: flashed and booted on cepheus + crDroid 16.0 (20260912, v12.12) on 2026-10-20.** In-depth Droidspaces container / Docker validation is still pending. For cepheus + crDroid 16 only — back up your boot partition before flashing.

---

# 小米 9（cepheus）Droidspaces 内核 — crDroid 16

适用于小米 9（cepheus）+ crDroid 16（Android 16）的 Droidspaces 内核，AnyKernel3 刷机包。内核版本串：`4.14.355-openela-Droidspaces`。

## 源码血统（重要，认版本号不认组织名）

- 基线源码：[`raystef66/kernel_xiaomi_cepheus`](https://github.com/raystef66/kernel_xiaomi_cepheus)，分支 `16.0-ksun`，commit `6ad047b70d809d7dee1fc090dbe2c252ff43b7eb`。这是 crDroid 16 官方包内置的 InfiniR 内核（`v2.02_A16_KSUN`）的真实源码。
- ⚠️ **特别提醒**：[crDroid](https://github.com/crdroidandroid) 组织仓库的 [`android_kernel_xiaomi_sm8150`](https://github.com/crdroidandroid/android_kernel_xiaomi_sm8150)（4.14.356）**不是**这棵树。从组织树编译的内核在本机无法开机（已实测）。判断血统认版本号 **355**，不认组织名。

## 构建与配置

- **本包零源码改动**：源码与上述上游 commit 完全一致。
- 配置 = crDroid stock 内核的 `/proc/config.gz` 基线 + Droidspaces 增量；最终 `.config` 随本仓库一同发布（`cepheus-crDroid-Droidspaces-v5-config.txt`）。

## [KernelSU-Next](https://github.com/KernelSU-Next/KernelSU-Next) 与 [SUSFS](https://gitlab.com/simonpunk/susfs4ksu)

- 集成方式：MANUAL_HOOK（手动 hook）。
- **实测版本（从编译出的 Image 提取字符串）**：[KernelSU-Next](https://github.com/KernelSU-Next/KernelSU-Next) **v3.0.1-legacy-88-g00cb93e0** + [SUSFS](https://gitlab.com/simonpunk/susfs4ksu) **v2.1.0**。
- 诚实注明：上游树的提交信息自称集成了 v3.2.0-legacy，但其 gitlink pin 的子模块内容经实测为 v3.0.1-legacy-88——标签与内容不符。本包一律以从 Image 实测的版本为准。

## Droidspaces / Docker 支持项

- PID / UTS / USER / IPC / NET 五个 namespace 全部开启
- `CONFIG_CFS_BANDWIDTH` 开启 → Droidspaces 的 `--cpus` 限制可用
- `CONFIG_POSIX_MQUEUE` 开启 → docker 无需 runc wrapper 剥除 `/dev/mqueue`
- `CONFIG_OVERLAY_FS` 开启
- `CONFIG_SCHED_WALT` 关闭（与 stock 一致，同时是 CFS_BANDWIDTH 可用的前提）
- TCP 默认拥塞控制为 BBR

## 实测状态

- ✅ 2026-10-20 在 cepheus + crDroid 16.0（20260912，v12.12）上刷入并成功开机。
- ⏳ Droidspaces 容器与 docker 的深度验收尚待回报。本包不宣称未经验证的使用体验，刷机结果请以自身测试为准。

## 刷机与回滚

- **刷机前务必先备份 boot 分区**（重要的事说三遍也不为过）。
- 刷机：在 OrangeFox / TWRP recovery 中刷入 `cepheus-crDroid-Droidspaces-v5.zip`。
- 回滚：`fastboot flash boot <原厂 boot.img>`，刷回备份的 boot 即可。
- **仅限 cepheus + crDroid 16**。其他设备、其他 ROM 请勿刷入。

## 源码与许可（GPLv2）

- 本内核遵循 GPLv2。因零源码改动，完整对应源码 = 上述上游仓库的该 commit + 本仓库发布的 `.config`，可自行复现构建。

## 致谢

- **[raystef66](https://github.com/raystef66)** — InfiniR 内核作者与维护者
- **[KernelSU-Next](https://github.com/KernelSU-Next/KernelSU-Next)** — 内核级 root 方案
- **[SUSFS](https://gitlab.com/simonpunk/susfs4ksu)** — 隐藏与补丁框架
- **[crDroid](https://github.com/crdroidandroid)** — ROM 与设备维护
- **[AnyKernel3](https://github.com/osm0sis/AnyKernel3)**（[osm0sis](https://github.com/osm0sis)）— 刷机包格式
