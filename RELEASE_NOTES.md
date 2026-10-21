# Release v5 — cepheus Droidspaces kernel for crDroid 16

Tag suggestion: `v5`

Xiaomi Mi 9 (cepheus) + crDroid 16 (Android 16) Droidspaces kernel, AnyKernel3 package.
Kernel release: `4.14.355-openela-Droidspaces`

## Highlights

- Built from the real source of the InfiniR kernel shipped in crDroid 16 official builds:
  [`raystef66/kernel_xiaomi_cepheus`](https://github.com/raystef66/kernel_xiaomi_cepheus), branch `16.0-ksun`, commit `6ad047b70d809d7dee1fc090dbe2c252ff43b7eb`.
  (Note: the crDroid org repo [`android_kernel_xiaomi_sm8150`](https://github.com/crdroidandroid/android_kernel_xiaomi_sm8150), 4.14.356, is a different tree — kernels built from it do not boot on this device. Trust the version number: 355.)
- Zero source-code changes. Config = crDroid stock `/proc/config.gz` baseline + Droidspaces delta (final `.config` included in this repository).
- [KernelSU-Next](https://github.com/KernelSU-Next/KernelSU-Next) integrated (MANUAL_HOOK) with [SUSFS](https://gitlab.com/simonpunk/susfs4ksu). Version measured from the built image:
  **v3.0.1-legacy-88-g00cb93e0** + SUSFS **v2.1.0**.
  Honest note: the upstream tree's commit message claims v3.2.0-legacy, but its pinned submodule actually measures v3.0.1-legacy-88 — this release goes by the measurement.
- Droidspaces/Docker: PID/UTS/USER/IPC/NET namespaces on, `CFS_BANDWIDTH` on (`--cpus` works), `POSIX_MQUEUE` on (no runc wrapper needed for docker), `OVERLAY_FS` on, `SCHED_WALT` off, TCP default congestion control BBR.

## Tested status

- ✅ Flashed and booted on cepheus + crDroid 16.0 (20260912, v12.12) on 2026-10-20.
- ⏳ In-depth Droidspaces container / Docker validation is still pending.

## Asset

- `cepheus-crDroid-Droidspaces-v5.zip`
  SHA-256: `2616449bb62e74d3e19f1951e9535672f5644f33ec91b48d7e60cdfa72cebfaa`

## Flash / rollback

- **Back up your boot partition first.**
- Flash the zip in OrangeFox / TWRP.
- Rollback: `fastboot flash boot <stock boot.img>`.
- **cepheus + crDroid 16 only.** Do not flash on other devices or ROMs.

## License

GPLv2. Zero source changes: the complete corresponding source is the upstream repository at the commit above plus the `.config` published in this repository.

## Credits

raystef66 (InfiniR kernel), KernelSU-Next, SUSFS, crDroid, AnyKernel3 (osm0sis).
