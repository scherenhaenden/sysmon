# SysMon

> **Terminal System & Hardware Monitor** with Dual-GPU Support, Fan Telemetry, and an Interactive ASCII Motherboard Visual Locator.

Inspired by tools like `btop` and `nvtop`, **SysMon** is a lightweight, responsive terminal utility built with Python and [Rich](https://github.com/Textualize/rich).

---

## ✨ Features

- **⚡ Dual-GPU & Multi-GPU Monitoring**:
  - Automatically identifies GPUs and maps them to their physical PCIe slots (e.g. Dual AMD Radeon RX 9070 on PCIe Slot #1 and Slot #2).
  - Reports GPU Load %, VRAM usage, Power consumption (Watts), Clock frequencies, and multiple thermal diodes: **Edge**, **Junction (Hotspot)**, and **VRAM Memory**.
- **🌀 Fan Telemetry**:
  - Real-time Fan RPM and PWM duty cycle % reporting for GPU coolers and motherboard fan headers.
  - Detects 0 dB / Zero-RPM silent mode when idling under 50°C.
- **🌡️ Complete Thermal Sensor Suite**:
  - Displays all system temperatures in a unified panel: CPU (`Tdie`, `Tctl`), NVMe SSD (`Composite`), GPU diodes, and Chipset.
- **🗺️ Interactive Motherboard Hardware Map (Visual Locator)**:
  - Generates an accurate ASCII representation of the motherboard (ATX / Gigabyte GA-AX370-Gaming 5).
  - Dynamically highlights the exact physical component (CPU Socket AM4, M.2 Slot, PCIe Slot 1, PCIe Slot 2, Fan headers) corresponding to the selected sensor with live thermal and physical descriptions.
- **⌨️ Non-blocking Keyboard Navigation**:
  - Switch views or navigate sensors instantaneously with 0ms input lag.

---

## 🚀 Installation

Ensure you have Python 3.8+ installed:

```bash
git clone https://github.com/scherenhaenden/sysmon.git
cd sysmon
pip install -r requirements.txt
```

### Dependencies
- `psutil`
- `rich`

---

## 🖥️ Usage

Run the monitor:
```bash
python3 sysmon.py
```

Or launch directly into the **Motherboard Sensor Map**:
```bash
python3 sysmon.py --map
```

### Keyboard Controls

| Key | Action |
| :--- | :--- |
| **`M`** or **`Tab`** | Toggle between **System Monitor** and **Motherboard Sensor Map** |
| **`↑`** / **`↓`** (or **`k`** / **`j`**) | Navigate between temperature sensors and fans |
| **`1`** – **`9`** | Directly jump to a specific sensor by number |
| **`Q`** or **`Ctrl+C`** | Exit cleanly |

---

## 🔍 Hardware Detection Tool

A standalone probe script is also included:
```bash
python3 detect_hardware.py
```
This inspects DMI motherboard strings, all `sysfs` hwmon nodes, fan inputs, PWM controls, and PCI bus topology.

---

## 📜 License

MIT License.
