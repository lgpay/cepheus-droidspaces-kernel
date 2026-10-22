### AnyKernel3 Ramdisk Mod Script
## cepheus: Droidspaces + KernelSU-Next v3.2.0-legacy kernel (4.14.355-openela-Droidspaces)
## Built from raystef66/kernel_xiaomi_cepheus (InfiniR, branch 16.0-ksun) + stock/Droidspaces config
## + KernelSU-Next v3.2.0-legacy (MANUAL_HOOK) + SUSFS v2.1.0, tree-integrated. No ramdisk modifications: kernel only.

### AnyKernel setup
# global properties
properties() { '
kernel.string=cepheus Droidspaces + KernelSU-Next v3.2.0-legacy MANUAL_HOOK kernel (4.14.355-openela-Droidspaces)
do.devicecheck=1
do.modules=0
do.systemless=0
do.cleanup=1
do.cleanuponabort=0
device.name1=cepheus
device.name2=
device.name3=
device.name4=
device.name5=
supported.versions=
supported.patchlevels=
supported.vendorpatchlevels=
'; } # end properties


### AnyKernel install
## boot files attributes
boot_attributes() {
set_perm_recursive 0 0 755 644 $RAMDISK/*;
set_perm_recursive 0 0 750 750 $RAMDISK/init* $RAMDISK/sbin;
} # end attributes

# boot shell variables
BLOCK=/dev/block/bootdevice/by-name/boot;
IS_SLOT_DEVICE=0;
RAMDISK_COMPRESSION=auto;
PATCH_VBMETA_FLAG=auto;

# import functions/variables and setup patching - see for reference (DO NOT REMOVE)
. tools/ak3-core.sh;

# boot install
dump_boot; # unpack the device's current boot.img, keep its ramdisk/dtb/cmdline

# No ramdisk modifications: this kernel only adds Droidspaces config + KernelSU.
# write_boot repacks with the Image.gz-dtb from this zip.

write_boot; # repack with new kernel and flash
## end boot install
