#!/usr/bin/env python3
"""
Diagnostic & Hardware Probe Script
Detects all GPUs, PCI devices, fan sensors (CPU, Chassis, GPUs),
hwmon entries, sysfs PWM controls, and temperatures.
"""

import os
import glob
import json
import subprocess
import psutil

print("=" * 70)
print("1. PROBING MOTHERBOARD & DMI")
print("=" * 70)
for field in ['board_vendor', 'board_name', 'board_version', 'product_name', 'sys_vendor', 'bios_version']:
    p = f"/sys/class/dmi/id/{field}"
    if os.path.exists(p):
        print(f"  {field:15}: {open(p).read().strip()}")

print("\n" + "=" * 70)
print("2. PROBING ALL HWMON DEVICES (Fans, Temps, Voltages, Power)")
print("=" * 70)
for hw in sorted(glob.glob("/sys/class/hwmon/hwmon*")):
    name_file = os.path.join(hw, "name")
    dev_path = os.path.realpath(os.path.join(hw, "device")) if os.path.exists(os.path.join(hw, "device")) else "N/A"
    h_name = open(name_file).read().strip() if os.path.exists(name_file) else "unknown"
    print(f"\n[+] {os.path.basename(hw)}: name='{h_name}'")
    print(f"    Device Link: {dev_path}")

    # Fans
    fans = sorted(glob.glob(os.path.join(hw, "fan*_input")))
    if fans:
        print("    FANS:")
        for f in fans:
            base = f[:-6]
            label_f = f"{base}_label"
            label = open(label_f).read().strip() if os.path.exists(label_f) else os.path.basename(base)
            try:
                rpm = int(open(f).read().strip())
                print(f"      - {label} ({os.path.basename(f)}): {rpm} RPM")
            except Exception as e:
                print(f"      - {label} ({os.path.basename(f)}): Error reading ({e})")
    else:
        print("    FANS: None reported")

    # PWM
    pwms = sorted(glob.glob(os.path.join(hw, "pwm*")))
    if pwms:
        print("    PWMs:")
        for pwm in pwms:
            if not pwm.endswith(("_enable", "_mode")):
                try:
                    val = open(pwm).read().strip()
                    pct = (int(val) / 255.0) * 100.0 if val.isdigit() else 0
                    print(f"      - {os.path.basename(pwm)}: {val} (approx {pct:.1f}%)")
                except Exception as e:
                    pass

    # Temperatures
    temps = sorted(glob.glob(os.path.join(hw, "temp*_input")))
    if temps:
        print("    TEMPERATURES:")
        for t in temps:
            base = t[:-6]
            label_f = f"{base}_label"
            label = open(label_f).read().strip() if os.path.exists(label_f) else os.path.basename(base)
            try:
                val = int(open(t).read().strip()) / 1000.0
                print(f"      - {label} ({os.path.basename(t)}): {val:.1f}°C")
            except Exception as e:
                pass

    # Power
    powers = sorted(glob.glob(os.path.join(hw, "power*_average")) + glob.glob(os.path.join(hw, "power*_input")))
    if powers:
        print("    POWER:")
        for p in powers:
            try:
                w = float(open(p).read().strip()) / 1e6
                print(f"      - {os.path.basename(p)}: {w:.1f} W")
            except Exception:
                pass

print("\n" + "=" * 70)
print("3. PROBING GPUS IN DETAIL (PCIe Bus, Model, DRM, sysfs)")
print("=" * 70)
for card in sorted(glob.glob("/sys/class/drm/card[0-9]*")):
    dev = os.path.join(card, "device")
    if not os.path.isdir(dev):
        continue
    vendor_f = os.path.join(dev, "vendor")
    device_f = os.path.join(dev, "device")
    pci_slot = os.path.basename(os.path.realpath(dev))
    print(f"\n[+] DRM Card: {os.path.basename(card)} (PCI: {pci_slot})")
    if os.path.exists(vendor_f) and os.path.exists(device_f):
        v = open(vendor_f).read().strip()
        d = open(device_f).read().strip()
        print(f"    Vendor: {v}, Device ID: {d}")

    # Product / Subsystem
    sub_prod = os.path.join(dev, "product_name")
    if os.path.exists(sub_prod):
        print(f"    Product Name: {open(sub_prod).read().strip()}")

    # Busy %
    busy_f = os.path.join(dev, "gpu_busy_percent")
    if os.path.exists(busy_f):
        print(f"    Busy %: {open(busy_f).read().strip()}%")

    # VRAM
    v_used = os.path.join(dev, "mem_info_vram_used")
    v_tot = os.path.join(dev, "mem_info_vram_total")
    if os.path.exists(v_used) and os.path.exists(v_tot):
        u = int(open(v_used).read().strip()) / (1024**3)
        t = int(open(v_tot).read().strip()) / (1024**3)
        print(f"    VRAM: {u:.2f} GB / {t:.2f} GB")

    # Clocks
    sclk = os.path.join(dev, "pp_dpm_sclk")
    if os.path.exists(sclk):
        print("    Core Clock states (pp_dpm_sclk):")
        for line in open(sclk).readlines():
            if '*' in line:
                print(f"      Current: {line.strip()}")

    # Hwmon inside device
    hwmons = glob.glob(os.path.join(dev, "hwmon", "hwmon*"))
    print(f"    hwmon nodes: {hwmons}")
    for h in hwmons:
        fans = glob.glob(os.path.join(h, "fan*_input"))
        pwms = glob.glob(os.path.join(h, "pwm*"))
        print(f"      -> {os.path.basename(h)} fans: {fans}")
        for fn in fans:
            print(f"         {os.path.basename(fn)}: {open(fn).read().strip()} RPM")
        for pw in pwms:
            if not pw.endswith(("_enable", "_mode")):
                print(f"         {os.path.basename(pw)}: {open(pw).read().strip()}")

print("\n" + "=" * 70)
print("4. CHECKING PSUTIL FANS")
print("=" * 70)
if hasattr(psutil, "sensors_fans"):
    fans = psutil.sensors_fans()
    print("psutil.sensors_fans():", fans)
else:
    print("psutil does not have sensors_fans")

print("\n" + "=" * 70)
print("5. CHECKING LSPCI OUTPUT FOR GPUS")
print("=" * 70)
out = subprocess.getoutput("lspci -nnk | grep -A 3 -E 'VGA|3D|Display'")
print(out)

