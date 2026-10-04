#!/usr/bin/env python3
"""
SysMon Pro - Terminal Hardware & System Monitor
Features:
- Multi-language support (English and Spanish, toggle with 'L' or --lang).
- Dual-GPU & Multi-GPU support (PCIe Slot 1 and Slot 2 tracking).
- Fan telemetry monitoring (RPM and PWM duty cycle %).
- Complete thermal sensor dashboard.
- Interactive ASCII Motherboard Hardware Map with live physical locator.

All comments and internal documentation are written in English.
"""

import os
import sys
import time
import glob
import select
import termios
import tty
import argparse
import psutil

try:
    from rich.console import Console
    from rich.layout import Layout
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.live import Live
    from rich import box
except ImportError:
    sys.exit("Error: 'rich' library is required. Install with: pip install rich")


# ==============================================================================
# Internationalization (i18n) Dictionary
# ==============================================================================
TRANSLATIONS = {
    "en": {
        "title": "SysMon Pro - Dual GPU & System Monitor",
        "header_subtitle": "Dual GPU & Hardware Monitor",
        "press_map": "[Press 'M' for MOTHERBOARD HARDWARE MAP & FANS]",
        "press_exit": "[Q: Exit]",
        "updated": "Updated",
        "detected_board": "DETECTED MOTHERBOARD",
        "gpu_monitor_title": "󰢮 DUAL GPU MONITOR (AMD Radeon RX 9070 on PCIe 1 & PCIe 2)",
        "col_slot": "Slot",
        "col_card": "Card / Model",
        "col_gpu_use": "GPU Load",
        "col_vram_use": "VRAM Load",
        "col_edge": "Edge",
        "col_junc": "Junc",
        "col_mem": "Mem",
        "col_power": "Power",
        "col_fan": "Fan",
        "cpu_title": "󰻠 CPU (AMD Ryzen)",
        "cpu_load": "Load:",
        "cpu_temp": "Temp:",
        "cpu_clock": "Clock:",
        "cpu_threads": "Threads:",
        "mem_title": "󰍛 RAM & Swap Memory",
        "mem_ram": "RAM:",
        "mem_swap": "Swap:",
        "io_title": "󰋊 Disk & Network I/O",
        "io_disk_read": "Disk Read:",
        "io_disk_write": "Disk Write:",
        "io_root_disk": "Root Disk:",
        "io_net_down": "Net Down (Rx):",
        "io_net_up": "Net Up (Tx):",
        "thermal_fans_title": "🌡️ ALL THERMAL SENSORS & 🌀 SYSTEM FANS",
        "thermal_press_m": "— Press M to view on Motherboard",
        "col_id": "ID",
        "col_component": "Component",
        "col_sensor": "Sensor",
        "col_temp": "Temp",
        "col_status": "Status",
        "col_limits": "Limits",
        "col_fan_name": "Fan",
        "col_fan_speed": "RPM / Speed",
        "mb_cpu_fan": "CPU_FAN Header",
        "mb_sys_fan": "SYS_FAN1-4 Headers",
        "connected_mb": "Connected (Motherboard)",
        "smart_pwm": "Smart PWM",
        "fan_zero_db": "0 dB Silent (Stopped)",
        "fan_active": "Active",
        "map_title": "🗺️ MOTHERBOARD PHYSICAL SCHEMATIC — DUAL GPU & SENSORS",
        "nav_sensors": "Navigate Sensors [↑/↓ or 1-9]",
        "sensor_tech_sheet": "Technical Specs of Sensor / Fan",
        "selected_item": "SELECTED ELEMENT:",
        "location_on_board": "LOCATION ON BOARD:",
        "realtime_value": "REAL-TIME VALUE:",
        "physical_desc": "PHYSICAL DETAILS:",
        "here_active": "◄── SENSOR LOCATED HERE!",
        "footer_map": "🗺️ Motherboard Map",
        "footer_select": "Select Sensor/Fan",
        "footer_lang": "Language (EN/ES)",
        "footer_quit": "Exit",
        "cpu_desc_die": "Physical core die temperature of the Ryzen processor.",
        "cpu_desc_ctl": "Control temperature with offset used for fan curve regulation.",
        "nvme_desc": "Composite temperature of controller and NAND Flash memory modules.",
        "gpu_desc_edge": "Perimeter diode temperature of the graphics silicon in PCIe Slot #{slot}.",
        "gpu_desc_junc": "Hotspot diode (highest localized junction temperature) in PCIe Slot #{slot}.",
        "gpu_desc_mem": "Video memory modules (GDDR6 VRAM) temperature in PCIe Slot #{slot}.",
        "gpu_fan_desc": "Heatsink fans on graphics card in PCIe Slot #{slot}. Stops (0 dB Zero-RPM) when under 50°C.",
        "mb_fan_desc": "Cooling fan connected to motherboard PWM header.",
        "loc_socket_am4": "Socket AM4 (Top Center)",
        "loc_m2_slot": "M.2 Socket 3 Slot (Under CPU Socket)",
        "loc_pcie_slot": "PCIe x16 Slot #{slot} (Steel Armored - {addr})",
        "loc_mb_header": "Motherboard Fan Header (CPU_FAN / SYS_FAN)",
        "status_optimal": "OPTIMAL",
        "status_warm": "WARM",
        "status_critical": "CRITICAL"
    },
    "es": {
        "title": "SysMon Pro - Monitor de Sistema y Dual GPU",
        "header_subtitle": "Monitor de Sistema y Hardware Dual GPU",
        "press_map": "[Pulsa 'M' para MAPA VISUAL DE PLACA BASE Y VENTILADORES]",
        "press_exit": "[Q: Salir]",
        "updated": "Actualizado",
        "detected_board": "PLACA BASE DETECTADA",
        "gpu_monitor_title": "󰢮 MONITOR DUAL GPU (AMD Radeon RX 9070 en PCIe 1 y PCIe 2)",
        "col_slot": "Slot",
        "col_card": "Tarjeta / Modelo",
        "col_gpu_use": "Uso GPU",
        "col_vram_use": "Uso VRAM",
        "col_edge": "Edge",
        "col_junc": "Junc",
        "col_mem": "Mem",
        "col_power": "Potencia",
        "col_fan": "Ventilador",
        "cpu_title": "󰻠 CPU (AMD Ryzen)",
        "cpu_load": "Carga:",
        "cpu_temp": "Temp:",
        "cpu_clock": "Reloj:",
        "cpu_threads": "Hilos:",
        "mem_title": "󰍛 Memoria RAM & Swap",
        "mem_ram": "RAM:",
        "mem_swap": "Swap:",
        "io_title": "󰋊 Disco & Red I/O",
        "io_disk_read": "Lectura Disco:",
        "io_disk_write": "Escritura:",
        "io_root_disk": "Disco Raíz:",
        "io_net_down": "Red Bajada (Rx):",
        "io_net_up": "Red Subida (Tx):",
        "thermal_fans_title": "🌡️ TODAS LAS TEMPERATURAS Y 🌀 VENTILADORES DEL SISTEMA",
        "thermal_press_m": "— Pulsa M para ver en Placa Base",
        "col_id": "ID",
        "col_component": "Componente",
        "col_sensor": "Sensor",
        "col_temp": "Temp",
        "col_status": "Estado",
        "col_limits": "Límites",
        "col_fan_name": "Ventilador",
        "col_fan_speed": "RPM / Velocidad",
        "mb_cpu_fan": "Cabezal CPU_FAN",
        "mb_sys_fan": "Cabezales SYS_FAN1-4",
        "connected_mb": "Conectado (Placa)",
        "smart_pwm": "PWM Inteligente",
        "fan_zero_db": "0 dB Silencioso (Parado)",
        "fan_active": "Activo",
        "map_title": "🗺️ ESQUEMA FÍSICO DE LA PLACA BASE — DUAL GPU & SENSORES",
        "nav_sensors": "Navegar Sensores [↑/↓ o 1-9]",
        "sensor_tech_sheet": "Ficha Técnica del Sensor / Ventilador",
        "selected_item": "ELEMENTO SELECCIONADO:",
        "location_on_board": "UBICACIÓN EN PLACA:",
        "realtime_value": "VALOR EN TIEMPO REAL:",
        "physical_desc": "DESCRIPCIÓN FÍSICA:",
        "here_active": "◄── SENSOR LOCALIZADO AQUÍ!",
        "footer_map": "🗺️ Mapa Placa Base",
        "footer_select": "Seleccionar Sensor/Ventilador",
        "footer_lang": "Idioma (EN/ES)",
        "footer_quit": "Salir",
        "cpu_desc_die": "Temperatura física real de los núcleos (die) de silicio del procesador Ryzen.",
        "cpu_desc_ctl": "Temperatura de control con offset usada para gestión de ventiladores.",
        "nvme_desc": "Temperatura compuesta del controlador y módulos de memoria NAND Flash.",
        "gpu_desc_edge": "Temperatura del diodo perimetral del chip gráfico en PCIe Slot #{slot}.",
        "gpu_desc_junc": "Punto más caliente (Hotspot) del silicio gráfico en PCIe Slot #{slot}.",
        "gpu_desc_mem": "Módulos de memoria de vídeo (VRAM GDDR6) en PCIe Slot #{slot}.",
        "gpu_fan_desc": "Ventiladores del disipador de la tarjeta en PCIe Slot #{slot}. Se apagan (0 dB Zero-RPM) a menos de 50°C.",
        "mb_fan_desc": "Ventilador de refrigeración conectado a cabezal PWM de la placa base.",
        "loc_socket_am4": "Socket AM4 (Centro Superior)",
        "loc_m2_slot": "Ranura M.2 Socket 3 (Bajo el Socket AM4)",
        "loc_pcie_slot": "Ranura PCIe x16 #{slot} (Blindada - {addr})",
        "loc_mb_header": "Cabezal de Ventilador en Placa Base (CPU_FAN / SYS_FAN)",
        "status_optimal": "ÓPTIMO",
        "status_warm": "ELEVADA",
        "status_critical": "CRÍTICA"
    }
}


def tr(key, lang="en", **kwargs):
    """Retrieve translated text string with optional formatting."""
    lang_dict = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    text = lang_dict.get(key, TRANSLATIONS["en"].get(key, key))
    if kwargs:
        text = text.format(**kwargs)
    return text


def detect_default_language():
    """Detect default language based on system environment locale."""
    for env_var in ["LC_ALL", "LC_MESSAGES", "LANG"]:
        val = os.environ.get(env_var, "").lower()
        if val.startswith("es"):
            return "es"
    return "en"


def human_bytes(bytes_val, suffix="B"):
    """Convert bytes into human-readable unit string (KB, MB, GB, etc.)."""
    for unit in ["", "K", "M", "G", "T", "P"]:
        if abs(bytes_val) < 1024.0:
            return f"{bytes_val:5.1f} {unit}{suffix}"
        bytes_val /= 1024.0
    return f"{bytes_val:5.1f} E{suffix}"


def human_speed(bps):
    """Convert transfer rate in bytes per second to formatted string."""
    return f"{human_bytes(bps)}/s"


def make_gauge(percent, length=14, high_thresh=85, med_thresh=65):
    """Generate a colored progress bar gauge with numeric percentage."""
    pct = max(0.0, min(100.0, float(percent)))
    fill_len = int(round((pct / 100.0) * length))
    empty_len = length - fill_len

    if pct >= high_thresh:
        color = "red bold"
    elif pct >= med_thresh:
        color = "yellow"
    else:
        color = "green"

    bar = "█" * fill_len + "░" * empty_len
    return Text.assemble((bar, color), (f" {pct:5.1f}%", f"{color}"))


def make_temp_bar(temp_val, min_val=25.0, max_val=105.0, length=10):
    """Generate a gradient color bar representing temperature."""
    if temp_val is None:
        return Text("-", style="dim")
    clamped = max(min_val, min(max_val, float(temp_val)))
    ratio = (clamped - min_val) / (max_val - min_val)
    fill_len = int(round(ratio * length))
    empty_len = length - fill_len

    if temp_val >= 85.0:
        color = "red bold"
    elif temp_val >= 68.0:
        color = "yellow bold"
    elif temp_val >= 50.0:
        color = "cyan"
    else:
        color = "green"

    bar = "█" * fill_len + "░" * empty_len
    return Text.assemble((bar, color), (f" {temp_val:4.1f}°C", f"{color}"))


def make_fan_bar(rpm, pwm_pct=None, max_rpm=3600, length=10, lang="en"):
    """Generate a fan status bar with speed and 0dB mode detection."""
    if rpm == 0:
        return Text(tr("fan_zero_db", lang), style="cyan dim")
    ratio = min(1.0, rpm / max_rpm) if max_rpm else 0.5
    fill_len = int(round(ratio * length))
    empty_len = length - fill_len

    color = "yellow" if rpm > 2200 else "green"
    bar = "█" * fill_len + "░" * empty_len
    pct_str = f" ({pwm_pct:.0f}%)" if pwm_pct is not None else ""
    return Text.assemble((bar, color), (f" {rpm} RPM{pct_str}", f"{color}"))


# ==============================================================================
# Hardware Sampler Class
# ==============================================================================
class HardwareSampler:
    """Collects system metrics across CPU, RAM, I/O, Dual GPUs, Fans, and Thermal Diodes."""

    def __init__(self):
        self.last_time = time.time()
        self.last_disk = psutil.disk_io_counters()
        self.last_net = psutil.net_io_counters()

        self.board_name = self._detect_motherboard()
        self.amd_gpus = self._discover_amd_gpus()

        self.has_nvidia = False
        try:
            import pynvml
            pynvml.nvmlInit()
            self.nvml = pynvml
            self.has_nvidia = True
            self.nvidia_device_count = pynvml.nvmlDeviceGetCount()
        except Exception:
            self.has_nvidia = False

    def _detect_motherboard(self):
        """Read motherboard vendor and product name from sysfs DMI."""
        for p in ["/sys/class/dmi/id/board_name", "/sys/class/dmi/id/product_name"]:
            if os.path.isfile(p):
                try:
                    with open(p, "r") as f:
                        val = f.read().strip()
                        if val:
                            vpath = "/sys/class/dmi/id/board_vendor"
                            vendor = ""
                            if os.path.isfile(vpath):
                                with open(vpath, "r") as vf:
                                    vendor = vf.read().strip()
                            if vendor and vendor not in val:
                                return f"{vendor} {val}"
                            return val
                except Exception:
                    pass
        return "Gigabyte AX370-Gaming 5 (ATX)"

    def _discover_amd_gpus(self):
        """Discover all AMD GPUs and sort them by physical PCIe slot address."""
        cards = []
        for card_path in glob.glob("/sys/class/drm/card[0-9]*"):
            # Skip video connector devices such as card0-DP-1
            if "-" in os.path.basename(card_path):
                continue
            device_dir = os.path.join(card_path, "device")
            if os.path.isdir(device_dir):
                vendor_file = os.path.join(device_dir, "vendor")
                is_amd = False
                if os.path.isfile(vendor_file):
                    try:
                        with open(vendor_file, "r") as f:
                            if "0x1002" in f.read().strip():
                                is_amd = True
                    except Exception:
                        pass

                busy_file = os.path.join(device_dir, "gpu_busy_percent")
                if is_amd or os.path.isfile(busy_file):
                    pci_slot = os.path.basename(os.path.realpath(device_dir))
                    name = "AMD Radeon RX 9070"

                    prod_file = os.path.join(device_dir, "product_name")
                    if os.path.isfile(prod_file):
                        try:
                            with open(prod_file, "r") as f:
                                prod_str = f.read().strip()
                                if prod_str:
                                    name = prod_str
                        except Exception:
                            pass

                    # Match hwmon sysfs node
                    hwmons = glob.glob(os.path.join(device_dir, "hwmon", "hwmon*"))
                    hwmon_path = hwmons[0] if hwmons else None

                    cards.append({
                        "card": os.path.basename(card_path),
                        "pci_addr": pci_slot,
                        "path": device_dir,
                        "name": name,
                        "hwmon": hwmon_path
                    })

        # Sort by physical PCIe bus address: 0d:00.0 (Slot 1) before 10:00.0 (Slot 2)
        cards.sort(key=lambda x: x["pci_addr"])
        for idx, c in enumerate(cards):
            c["slot_num"] = idx + 1
            c["slot_name"] = f"PCIe Slot #{idx+1} ({c['pci_addr']})"
        return cards

    def sample_cpu(self):
        """Sample CPU utilization, thread loads, frequencies, and temperature."""
        total_pct = psutil.cpu_percent(interval=None)
        per_core = psutil.cpu_percent(interval=None, percpu=True)
        freq = psutil.cpu_freq()
        cur_freq_ghz = (freq.current / 1000.0) if freq else 0.0

        temp_tdie = None
        temp_tctl = None
        cpu_temp = None
        temps = psutil.sensors_temperatures() if hasattr(psutil, "sensors_temperatures") else {}
        for chip in ["k10temp", "zenpower", "coretemp", "cpu_thermal", "acpitz"]:
            if chip in temps and temps[chip]:
                for entry in temps[chip]:
                    if entry.label == "Tdie":
                        temp_tdie = entry.current
                    elif entry.label == "Tctl":
                        temp_tctl = entry.current
                    elif entry.label in ["Package id 0", "temp1"]:
                        if cpu_temp is None:
                            cpu_temp = entry.current

        if temp_tdie is not None:
            cpu_temp = temp_tdie
        elif temp_tctl is not None:
            cpu_temp = temp_tctl

        return {
            "total_pct": total_pct,
            "per_core": per_core,
            "freq_ghz": cur_freq_ghz,
            "temp_c": cpu_temp,
            "temp_tdie": temp_tdie,
            "temp_tctl": temp_tctl,
            "count": psutil.cpu_count(logical=True)
        }

    def sample_memory(self):
        """Sample RAM and Swap memory metrics."""
        vm = psutil.virtual_memory()
        swap = psutil.swap_memory()
        return {
            "ram_used": vm.used,
            "ram_total": vm.total,
            "ram_pct": vm.percent,
            "swap_used": swap.used,
            "swap_total": swap.total,
            "swap_pct": swap.percent
        }

    def sample_io(self):
        """Sample disk transfer throughput and network bandwidth rates."""
        now = time.time()
        dt = max(now - self.last_time, 0.001)
        self.last_time = now

        cur_disk = psutil.disk_io_counters()
        read_bps = 0.0
        write_bps = 0.0
        if cur_disk and self.last_disk:
            read_bps = max(0.0, (cur_disk.read_bytes - self.last_disk.read_bytes) / dt)
            write_bps = max(0.0, (cur_disk.write_bytes - self.last_disk.write_bytes) / dt)
        self.last_disk = cur_disk

        cur_net = psutil.net_io_counters()
        net_rx_bps = 0.0
        net_tx_bps = 0.0
        if cur_net and self.last_net:
            net_rx_bps = max(0.0, (cur_net.bytes_recv - self.last_net.bytes_recv) / dt)
            net_tx_bps = max(0.0, (cur_net.bytes_sent - self.last_net.bytes_sent) / dt)
        self.last_net = cur_net

        root_part = psutil.disk_usage('/')

        return {
            "disk_read_bps": read_bps,
            "disk_write_bps": write_bps,
            "disk_used": root_part.used,
            "disk_total": root_part.total,
            "disk_pct": root_part.percent,
            "net_rx_bps": net_rx_bps,
            "net_tx_bps": net_tx_bps,
        }

    def sample_gpus(self):
        """Sample all GPUs with VRAM, load, power, fan telemetry, and thermal readings."""
        gpu_stats = []

        # 1. AMD GPUs
        for idx, card in enumerate(self.amd_gpus):
            dev = card["path"]
            stat = {
                "name": card["name"],
                "index": idx,
                "slot_num": card["slot_num"],
                "pci_addr": card["pci_addr"],
                "type": "AMD",
                "busy_pct": 0.0,
                "vram_used": 0,
                "vram_total": 0,
                "vram_pct": 0.0,
                "power_w": None,
                "fan_rpm": 0,
                "fan_pwm": 0,
                "temp_edge": None,
                "temp_junction": None,
                "temp_mem": None,
            }

            # GPU activity %
            busy_path = os.path.join(dev, "gpu_busy_percent")
            if os.path.isfile(busy_path):
                try:
                    with open(busy_path, "r") as f:
                        stat["busy_pct"] = float(f.read().strip())
                except Exception:
                    pass

            # VRAM memory
            used_path = os.path.join(dev, "mem_info_vram_used")
            tot_path = os.path.join(dev, "mem_info_vram_total")
            if os.path.isfile(used_path) and os.path.isfile(tot_path):
                try:
                    with open(used_path, "r") as f:
                        stat["vram_used"] = int(f.read().strip())
                    with open(tot_path, "r") as f:
                        stat["vram_total"] = int(f.read().strip())
                    if stat["vram_total"] > 0:
                        stat["vram_pct"] = (stat["vram_used"] / stat["vram_total"]) * 100.0
                except Exception:
                    pass

            # HWMon sensor node (Power, Fan RPM, PWM, Temperatures)
            hw = card["hwmon"]
            if hw and os.path.isdir(hw):
                # Power consumption
                for p_file in ["power1_average", "power1_input"]:
                    p_path = os.path.join(hw, p_file)
                    if os.path.isfile(p_path):
                        try:
                            with open(p_path, "r") as f:
                                stat["power_w"] = float(f.read().strip()) / 1e6
                                break
                        except Exception:
                            pass

                # Fan RPM
                fan_path = os.path.join(hw, "fan1_input")
                if os.path.isfile(fan_path):
                    try:
                        with open(fan_path, "r") as f:
                            stat["fan_rpm"] = int(f.read().strip())
                    except Exception:
                        pass

                # Fan PWM %
                pwm_path = os.path.join(hw, "pwm1")
                if os.path.isfile(pwm_path):
                    try:
                        with open(pwm_path, "r") as f:
                            val = int(f.read().strip())
                            stat["fan_pwm"] = (val / 255.0) * 100.0
                    except Exception:
                        pass

                # Thermal Diodes: edge, junction, mem
                for label_file in glob.glob(os.path.join(hw, "temp*_label")):
                    prefix = label_file[:-6]
                    val_file = f"{prefix}_input"
                    if os.path.isfile(val_file):
                        try:
                            with open(label_file, "r") as lf, open(val_file, "r") as vf:
                                lbl = lf.read().strip().lower()
                                deg = float(vf.read().strip()) / 1000.0
                                if "edge" in lbl:
                                    stat["temp_edge"] = deg
                                elif "junction" in lbl or "hotspot" in lbl:
                                    stat["temp_junction"] = deg
                                elif "mem" in lbl:
                                    stat["temp_mem"] = deg
                        except Exception:
                            pass

            gpu_stats.append(stat)

        # 2. NVIDIA GPUs via NVML
        if self.has_nvidia:
            try:
                for i in range(self.nvidia_device_count):
                    handle = self.nvml.nvmlDeviceGetHandleByIndex(i)
                    name = self.nvml.nvmlDeviceGetName(handle)
                    if isinstance(name, bytes):
                        name = name.decode("utf-8")
                    util = self.nvml.nvmlDeviceGetUtilizationRates(handle)
                    mem = self.nvml.nvmlDeviceGetMemoryInfo(handle)
                    temp = self.nvml.nvmlDeviceGetTemperature(handle, self.nvml.NVML_TEMPERATURE_GPU)
                    try:
                        power = self.nvml.nvmlDeviceGetPowerUsage(handle) / 1000.0
                    except Exception:
                        power = None
                    try:
                        fan = self.nvml.nvmlDeviceGetFanSpeed(handle)
                    except Exception:
                        fan = 0

                    vram_pct = (mem.used / mem.total * 100.0) if mem.total else 0.0
                    gpu_stats.append({
                        "name": name,
                        "index": len(gpu_stats),
                        "slot_num": len(gpu_stats) + 1,
                        "pci_addr": f"NVML-{i}",
                        "type": "NVIDIA",
                        "busy_pct": float(util.gpu),
                        "vram_used": mem.used,
                        "vram_total": mem.total,
                        "vram_pct": vram_pct,
                        "power_w": power,
                        "fan_rpm": 0,
                        "fan_pwm": fan or 0,
                        "temp_edge": float(temp),
                        "temp_junction": None,
                        "temp_mem": None,
                    })
            except Exception:
                pass

        return gpu_stats

    def sample_fans(self, lang="en"):
        """Sample all cooling fans across GPU heatsinks and motherboard headers."""
        fan_list = []
        fan_id = 1

        # GPU Fans
        for idx, card in enumerate(self.amd_gpus):
            hw = card["hwmon"]
            rpm = 0
            pwm_pct = 0.0
            if hw and os.path.isdir(hw):
                f_path = os.path.join(hw, "fan1_input")
                p_path = os.path.join(hw, "pwm1")
                if os.path.isfile(f_path):
                    try:
                        with open(f_path, "r") as f:
                            rpm = int(f.read().strip())
                    except Exception:
                        pass
                if os.path.isfile(p_path):
                    try:
                        with open(p_path, "r") as f:
                            pwm_pct = (int(f.read().strip()) / 255.0) * 100.0
                    except Exception:
                        pass

            status_txt = tr("fan_zero_db", lang) if rpm == 0 else f"{tr('fan_active', lang)} ({rpm} RPM)"
            fan_list.append({
                "id": fan_id,
                "name": f"{tr('col_fan_name', lang)} GPU {idx+1}",
                "device": f"{card['name']} (PCIe #{idx+1})",
                "rpm": rpm,
                "pwm_pct": pwm_pct,
                "status": status_txt,
                "slot_code": f"PCIE_{idx+1}_FAN",
                "location": tr("loc_pcie_slot", lang, slot=idx+1, addr=card['pci_addr']),
                "description": tr("gpu_fan_desc", lang, slot=idx+1)
            })
            fan_id += 1

        # Additional motherboard or cooling equipment fans from sysfs
        for hw_dir in glob.glob("/sys/class/hwmon/hwmon*"):
            h_name = "unknown"
            name_file = os.path.join(hw_dir, "name")
            if os.path.isfile(name_file):
                try:
                    with open(name_file, "r") as nf:
                        h_name = nf.read().strip()
                except Exception:
                    pass

            if h_name in ["amdgpu"]:
                continue

            for fan_in in sorted(glob.glob(os.path.join(hw_dir, "fan*_input"))):
                base = fan_in[:-6]
                label_f = f"{base}_label"
                lbl = open(label_f).read().strip() if os.path.exists(label_f) else os.path.basename(base)
                try:
                    r_val = int(open(fan_in).read().strip())
                    fan_list.append({
                        "id": fan_id,
                        "name": f"{tr('col_fan_name', lang)} {lbl.upper()}",
                        "device": f"Motherboard ({h_name})",
                        "rpm": r_val,
                        "pwm_pct": None,
                        "status": f"{r_val} RPM",
                        "slot_code": "MB_FAN",
                        "location": tr("loc_mb_header", lang),
                        "description": tr("mb_fan_desc", lang)
                    })
                    fan_id += 1
                except Exception:
                    pass

        return fan_list

    def sample_all_temperatures(self, lang="en"):
        """Collect all thermal sensors and map them to physical motherboard zones."""
        sensors_list = []
        raw_temps = psutil.sensors_temperatures() if hasattr(psutil, "sensors_temperatures") else {}
        sensor_id = 1

        # 1. CPU (k10temp)
        for chip_name in ["k10temp", "zenpower", "coretemp", "cpu_thermal"]:
            if chip_name in raw_temps:
                for entry in raw_temps[chip_name]:
                    label = entry.label or "CPU Temp"
                    desc = tr("cpu_desc_die", lang) if label == "Tdie" else tr("cpu_desc_ctl", lang)
                    sensors_list.append({
                        "id": sensor_id,
                        "chip": chip_name,
                        "label": label,
                        "current": entry.current,
                        "high": entry.high or 85.0,
                        "critical": entry.critical or 95.0,
                        "category": "CPU",
                        "device_name": "AMD Ryzen Processor (CPU)",
                        "location_name": tr("loc_socket_am4", lang),
                        "slot_code": "CPU_SOCKET",
                        "description": desc,
                    })
                    sensor_id += 1

        # 2. SSD M.2 NVMe
        if "nvme" in raw_temps:
            for idx, entry in enumerate(raw_temps["nvme"]):
                sensors_list.append({
                    "id": sensor_id,
                    "chip": "nvme",
                    "label": entry.label or f"NVMe-{idx+1}",
                    "current": entry.current,
                    "high": entry.high or 75.0,
                    "critical": entry.critical or 80.0,
                    "category": "NVME",
                    "device_name": "M.2 NVMe SSD (PCIe Gen3/Gen4 x4)",
                    "location_name": tr("loc_m2_slot", lang),
                    "slot_code": "M2_SLOT",
                    "description": tr("nvme_desc", lang),
                })
                sensor_id += 1

        # 3. Dual AMD GPUs sorted by physical slot
        gpu_stats = self.sample_gpus()
        for g in gpu_stats:
            g_num = g["slot_num"]
            slot_code = f"PCIE_{g_num}"
            loc_str = tr("loc_pcie_slot", lang, slot=g_num, addr=g['pci_addr'])

            # Edge
            if g["temp_edge"] is not None:
                sensors_list.append({
                    "id": sensor_id,
                    "chip": f"gpu{g_num}",
                    "label": f"GPU {g_num} Edge",
                    "current": g["temp_edge"],
                    "high": 100.0,
                    "critical": 110.0,
                    "category": f"GPU{g_num}",
                    "device_name": f"{g['name']} (GPU {g_num})",
                    "location_name": loc_str,
                    "slot_code": slot_code,
                    "description": tr("gpu_desc_edge", lang, slot=g_num),
                })
                sensor_id += 1

            # Junction
            if g["temp_junction"] is not None:
                sensors_list.append({
                    "id": sensor_id,
                    "chip": f"gpu{g_num}",
                    "label": f"GPU {g_num} Junction",
                    "current": g["temp_junction"],
                    "high": 105.0,
                    "critical": 110.0,
                    "category": f"GPU{g_num}",
                    "device_name": f"{g['name']} (GPU {g_num})",
                    "location_name": loc_str,
                    "slot_code": slot_code,
                    "description": tr("gpu_desc_junc", lang, slot=g_num),
                })
                sensor_id += 1

            # Memory
            if g["temp_mem"] is not None:
                sensors_list.append({
                    "id": sensor_id,
                    "chip": f"gpu{g_num}",
                    "label": f"GPU {g_num} Mem",
                    "current": g["temp_mem"],
                    "high": 95.0,
                    "critical": 108.0,
                    "category": f"GPU{g_num}",
                    "device_name": f"{g['name']} (GPU {g_num})",
                    "location_name": loc_str,
                    "slot_code": slot_code,
                    "description": tr("gpu_desc_mem", lang, slot=g_num),
                })
                sensor_id += 1

        return sensors_list


# ==============================================================================
# UI Panel Builders
# ==============================================================================
def create_gpu_panel(gpu_list, lang="en"):
    """Render GPU monitoring table (nvtop inspired)."""
    if not gpu_list:
        return Panel(Text("No GPUs detected.", style="dim italic"),
                     title=f"[bold red]{tr('gpu_monitor_title', lang)}[/bold red]", border_style="red")

    tbl = Table(expand=True, box=box.SIMPLE_HEAD, pad_edge=False)
    tbl.add_column(tr("col_slot", lang), style="bold cyan", width=8)
    tbl.add_column(tr("col_card", lang), style="bold white", ratio=3)
    tbl.add_column(tr("col_gpu_use", lang), ratio=2)
    tbl.add_column(tr("col_vram_use", lang), ratio=3)
    tbl.add_column(tr("col_edge", lang), justify="center", width=7)
    tbl.add_column(tr("col_junc", lang), justify="center", width=7)
    tbl.add_column(tr("col_mem", lang), justify="center", width=7)
    tbl.add_column(tr("col_power", lang), justify="right", width=8)
    tbl.add_column(tr("col_fan", lang), justify="right", width=16)

    for g in gpu_list:
        slot_lbl = f"PCIe #{g['slot_num']}"
        name = f"{g['name']} [{g['pci_addr']}]"
        gpu_bar = make_gauge(g['busy_pct'], length=10)
        vram_bar = make_gauge(g['vram_pct'], length=10)
        vram_txt = f"{human_bytes(g['vram_used'])}/{human_bytes(g['vram_total'])}"
        vram_cell = Text.assemble(vram_bar, (f" {vram_txt}", "dim"))

        def fmt_t(t):
            if t is None:
                return Text("-", style="dim")
            s = f"{t:4.0f}°C"
            if t >= 85:
                return Text(s, style="bold red")
            elif t >= 70:
                return Text(s, style="yellow")
            return Text(s, style="green")

        edge_txt = fmt_t(g['temp_edge'])
        junc_txt = fmt_t(g['temp_junction'])
        mem_txt = fmt_t(g['temp_mem'])

        power_txt = Text(f"{g['power_w']:4.0f} W", style="bold white") if g['power_w'] is not None else Text("-", style="dim")

        if g['fan_rpm'] == 0:
            fan_cell = Text(tr("fan_zero_db", lang), style="cyan dim")
        else:
            fan_cell = Text(f"{g['fan_rpm']} RPM ({g['fan_pwm']:.0f}%)", style="green bold")

        tbl.add_row(
            slot_lbl,
            name,
            gpu_bar,
            vram_cell,
            edge_txt,
            junc_txt,
            mem_txt,
            power_txt,
            fan_cell
        )

    return Panel(tbl, title=f"[bold red]{tr('gpu_monitor_title', lang)}[/bold red]", border_style="red")


def create_thermal_and_fans_panel(all_temps, all_fans, lang="en"):
    """Render unified panel containing all temperatures and system fans."""
    grid = Table.grid(padding=(0, 2), expand=True)
    grid.add_column(ratio=5)
    grid.add_column(ratio=3)

    # 1. Thermal Diodes Table
    t_tbl = Table(expand=True, box=box.SIMPLE_HEAD, pad_edge=False)
    t_tbl.add_column(tr("col_id", lang), style="bold cyan", width=4, justify="center")
    t_tbl.add_column(tr("col_component", lang), style="bold white", ratio=3)
    t_tbl.add_column(tr("col_sensor", lang), style="cyan", width=14)
    t_tbl.add_column(tr("col_temp", lang), justify="center", width=8)
    t_tbl.add_column(tr("col_status", lang), ratio=2)
    t_tbl.add_column(tr("col_limits", lang), justify="center", width=11)

    for s in all_temps:
        t_val = s["current"]
        if t_val is not None:
            if t_val >= (s["critical"] or 90.0):
                st_txt = Text(f"{t_val:4.1f}°C", style="bold red")
            elif t_val >= (s["high"] or 75.0):
                st_txt = Text(f"{t_val:4.1f}°C", style="bold yellow")
            else:
                st_txt = Text(f"{t_val:4.1f}°C", style="bold green")
        else:
            st_txt = Text("N/A", style="dim")

        bar = make_temp_bar(t_val, length=8)
        lim_str = f"{s['high']:.0f}/{s['critical']:.0f}°C" if s.get('high') and s.get('critical') else "-"

        t_tbl.add_row(
            f"[{s['id']}]",
            s["device_name"],
            s["label"],
            st_txt,
            bar,
            lim_str
        )

    # 2. Fans Table
    f_tbl = Table(expand=True, box=box.SIMPLE_HEAD, pad_edge=False)
    f_tbl.add_column(tr("col_fan_name", lang), style="bold white", ratio=3)
    f_tbl.add_column(tr("col_fan_speed", lang), justify="right", ratio=3)

    for f in all_fans:
        f_bar = make_fan_bar(f["rpm"], f["pwm_pct"], length=8, lang=lang)
        f_tbl.add_row(
            f["name"],
            f_bar
        )

    f_tbl.add_row(Text(tr("mb_cpu_fan", lang), style="dim"), Text(tr("connected_mb", lang), style="dim"))
    f_tbl.add_row(Text(tr("mb_sys_fan", lang), style="dim"), Text(tr("smart_pwm", lang), style="dim"))

    grid.add_row(t_tbl, f_tbl)

    title_text = f"[bold yellow]{tr('thermal_fans_title', lang)}[/bold yellow]  [dim]{tr('thermal_press_m', lang)}[/dim]"
    return Panel(grid, title=title_text, border_style="yellow")


def create_cpu_panel(cpu_info, lang="en"):
    """Render CPU monitoring panel."""
    tbl = Table.grid(padding=(0, 1), expand=True)
    tbl.add_column(ratio=2)
    tbl.add_column(ratio=3)

    freq_str = f"{cpu_info['freq_ghz']:.2f} GHz" if cpu_info['freq_ghz'] > 0 else "N/A"

    info_text = Text()
    info_text.append(f"{tr('cpu_load', lang)}  ", style="cyan bold")
    info_text.append(f"{cpu_info['total_pct']:5.1f}%\n", style="white bold")
    info_text.append(f"{tr('cpu_temp', lang)}  ", style="cyan bold")
    if cpu_info['temp_c'] is not None:
        t_val = cpu_info['temp_c']
        temp_color = "red bold" if t_val >= 80 else ("yellow" if t_val >= 65 else "green")
        info_text.append(f"{t_val:4.1f}°C", style=temp_color)
        if cpu_info.get('temp_tctl') is not None and cpu_info.get('temp_tdie') is not None:
            info_text.append(f" ({cpu_info['temp_tctl']:.0f}° Tctl)\n", style="dim")
        else:
            info_text.append("\n")
    else:
        info_text.append("N/A\n", style="white")

    info_text.append(f"{tr('cpu_clock', lang)}  ", style="cyan bold")
    info_text.append(f"{freq_str}\n", style="white")
    info_text.append(f"{tr('cpu_threads', lang)}  ", style="cyan bold")
    info_text.append(f"{cpu_info['count']} threads", style="white")

    core_tbl = Table.grid(padding=(0, 1), expand=True)
    num_cols = 4 if len(cpu_info['per_core']) >= 16 else 2
    for _ in range(num_cols):
        core_tbl.add_column()

    row_cells = []
    for i, pct in enumerate(cpu_info['per_core']):
        bar = make_gauge(pct, length=6, high_thresh=85, med_thresh=60)
        cell = Text.assemble((f"#{i:<2} ", "dim"), bar)
        row_cells.append(cell)
        if len(row_cells) == num_cols:
            core_tbl.add_row(*row_cells)
            row_cells = []
    if row_cells:
        while len(row_cells) < num_cols:
            row_cells.append(Text(""))
        core_tbl.add_row(*row_cells)

    tbl.add_row(info_text, core_tbl)
    return Panel(tbl, title=f"[bold blue]{tr('cpu_title', lang)}[/bold blue]", border_style="blue")


def create_mem_panel(mem_info, lang="en"):
    """Render RAM and Swap memory panel."""
    tbl = Table.grid(padding=(0, 1), expand=True)
    tbl.add_column(width=6)
    tbl.add_column(ratio=1)
    tbl.add_column(width=22)

    ram_bar = make_gauge(mem_info['ram_pct'], length=16)
    ram_text = f"{human_bytes(mem_info['ram_used'])} / {human_bytes(mem_info['ram_total'])}"
    tbl.add_row(Text(f"{tr('mem_ram', lang)} ", style="bold green"), ram_bar, Text(ram_text, style="white", justify="right"))

    swap_bar = make_gauge(mem_info['swap_pct'], length=16)
    swap_text = f"{human_bytes(mem_info['swap_used'])} / {human_bytes(mem_info['swap_total'])}"
    tbl.add_row(Text(f"{tr('mem_swap', lang)} ", style="bold yellow"), swap_bar, Text(swap_text, style="white", justify="right"))

    return Panel(tbl, title=f"[bold green]{tr('mem_title', lang)}[/bold green]", border_style="green")


def create_io_panel(io_info, lang="en"):
    """Render Disk and Network I/O panel."""
    tbl = Table.grid(padding=(0, 2), expand=True)
    tbl.add_column(ratio=1)
    tbl.add_column(ratio=1)

    disk_t = Text()
    disk_t.append(f"{tr('io_disk_read', lang)} ", style="cyan bold")
    disk_t.append(f"{human_speed(io_info['disk_read_bps'])}\n", style="bold green" if io_info['disk_read_bps'] > 0 else "white")
    disk_t.append(f"{tr('io_disk_write', lang)} ", style="cyan bold")
    disk_t.append(f"{human_speed(io_info['disk_write_bps'])}\n", style="bold yellow" if io_info['disk_write_bps'] > 0 else "white")
    disk_t.append(f"{tr('io_root_disk', lang)} ", style="cyan bold")
    disk_t.append(f"{io_info['disk_pct']}% ({human_bytes(io_info['disk_used'])}/{human_bytes(io_info['disk_total'])})", style="white")

    net_t = Text()
    net_t.append(f"{tr('io_net_down', lang)} ", style="magenta bold")
    net_t.append(f"{human_speed(io_info['net_rx_bps'])}\n", style="bold green" if io_info['net_rx_bps'] > 0 else "white")
    net_t.append(f"{tr('io_net_up', lang)} ", style="magenta bold")
    net_t.append(f"{human_speed(io_info['net_tx_bps'])}\n", style="bold yellow" if io_info['net_tx_bps'] > 0 else "white")

    tbl.add_row(disk_t, net_t)
    return Panel(tbl, title=f"[bold magenta]{tr('io_title', lang)}[/bold magenta]", border_style="magenta")


# ==============================================================================
# Motherboard ASCII Graphics Generator
# ==============================================================================
def generate_motherboard_ascii(board_name, active_slot, selected_item, lang="en"):
    """
    Generate ASCII motherboard schematic with dynamic component illumination
    highlighting the CPU Socket, M.2 Slot, PCIe Slot 1, PCIe Slot 2, Fans, and Chipset.
    """
    is_cpu = (active_slot == "CPU_SOCKET")
    is_nvme = (active_slot == "M2_SLOT")
    is_gpu1 = (active_slot in ["PCIE_1", "PCIE_1_FAN"])
    is_gpu2 = (active_slot in ["PCIE_2", "PCIE_2_FAN"])
    is_chipset = (active_slot == "CHIPSET")
    is_fan_hdr = (active_slot in ["MB_FAN", "CPU_FAN"])

    val_str = ""
    if selected_item:
        if "current" in selected_item:
            val_str = f"{selected_item['current']:.1f}°C"
        elif "rpm" in selected_item:
            val_str = f"{selected_item['rpm']} RPM" if selected_item['rpm'] > 0 else tr("fan_zero_db", lang)

    here_marker = f"[bold yellow]{tr('here_active', lang)}[/bold yellow]"

    # CPU AM4 Socket block
    if is_cpu:
        cpu_b1 = "[bold red]╔═════════════════════════════════════════════════╗[/bold red]"
        cpu_b2 = f"[bold white on red]   ★★★ SOCKET CPU AM4 / PROCESADOR RYZEN ★★★    [/bold white on red]"
        cpu_b3 = f"[bold white on red]      ▶▶ SENSOR ACTIVO: {selected_item['label']} = {val_str} ◀◀       [/bold white on red]"
        cpu_b4 = f"[bold red]╚═════════════════════════════════════════════════╝[/bold red] {here_marker}"
    else:
        cpu_b1 = "[blue]┌─────────────────────────────────────────────────┐[/blue]"
        cpu_b2 = "[bold cyan]             SOCKET CPU AM4 (RYZEN)               [/bold cyan]"
        cpu_b3 = "[dim]        [ Procesador & Disipador CPU ]           [/dim]"
        cpu_b4 = "[blue]└─────────────────────────────────────────────────┘[/blue]"

    # CPU_FAN Header block
    cpu_fan_hdr = "[bold white on yellow] [CPU_FAN & PUMP: ◄── AQUÍ] [/bold white on yellow]" if is_fan_hdr else "[dim][CPU_FAN & PUMP][/dim]"

    # M.2 NVMe SSD Slot block
    if is_nvme:
        m2_line = f"[bold white on magenta] ╔══ ★★★ M.2 NVMe SSD (Phison E12) [{val_str}] ★★★ ══╗ [/bold white on magenta] {here_marker}"
    else:
        m2_line = "[green] ┌── [ Ranura M.2 Socket 3 NVMe SSD PCIe x4 ] ──┐ [/green]"

    # PCIe Slot 1 (GPU 1)
    if is_gpu1:
        pcie1_line = f"[bold white on red] ╔══ ★★★ GPU 1: RADEON RX 9070 (PCIe Slot #1) [{val_str}] ★★★ ══╗ [/bold white on red] {here_marker}"
    else:
        pcie1_line = "[cyan] ┌── [ RANURA PCIe x16 #1 (GPU 1 Principal: Radeon RX 9070) ] ──┐ [/cyan]"

    # PCIe Slot 2 (GPU 2)
    if is_gpu2:
        pcie2_line = f"[bold white on red] ╔══ ★★★ GPU 2: RADEON RX 9070 (PCIe Slot #2) [{val_str}] ★★★ ══╗ [/bold white on red] {here_marker}"
    else:
        pcie2_line = "[cyan] ┌── [ RANURA PCIe x16 #2 (GPU 2 Secundaria: Radeon RX 9070) ] ──┐ [/cyan]"

    # Chipset block
    if is_chipset:
        chipset_hdr = "[bold red]╔══ [ CHIPSET ] ══╗[/bold red]"
        chipset_txt = f"[bold white on red]★ {val_str} ★[/bold white on red]"
        chipset_ftr = "[bold red]╚═════════════════╝[/bold red]"
    else:
        chipset_hdr = "[yellow]┌── [ CHIPSET ] ──┐[/yellow]"
        chipset_txt = "[dim]  AMD X370 FCH   [/dim]"
        chipset_ftr = "[yellow]└─────────────────┘[/yellow]"

    lines = [
        f"[bold cyan]+════════════════════════════════════════════════════════════════════════════════════════════════════+[/bold cyan]",
        f"[bold cyan]|[/bold cyan] [bold white]{tr('detected_board', lang)}:[/bold white] [bold yellow]{board_name.center(76)}[/bold yellow] [bold cyan]|[/bold cyan]",
        f"[bold cyan]+════════════════════════════════════════════════════════════════════════════════════════════════════+[/bold cyan]",
        f"[bold cyan]|[/bold cyan] [bold white][PANEL TRASERO I/O][/bold white]    [bold yellow][ VRM FASES CPU ][/bold yellow]   {cpu_fan_hdr.ljust(35)}|DDR4_4|DDR4_2|DDR4_3|DDR4_1|  [bold cyan]|[/bold cyan]",
        f"[bold cyan]|[/bold cyan]  USB 3.1 / Type-C        ════════════════                                  |[RAM] |[RAM] |[RAM] |[RAM] |  [bold cyan]|[/bold cyan]",
        f"[bold cyan]|[/bold cyan]  Dual LAN Intel/Killer                                                     |      |      |      |      |  [bold cyan]|[/bold cyan]",
        f"[bold cyan]|[/bold cyan]                                                                            |      |      |      |      |  [bold cyan]|[/bold cyan]",
        f"[bold cyan]|[/bold cyan] [bold yellow][VRM LATERAL][/bold yellow]        {cpu_b1}    |      |      |      |      |  [bold cyan]|[/bold cyan]",
        f"[bold cyan]|[/bold cyan]  ═══════════        {cpu_b2}    |      |      |      |      |  [bold cyan]|[/bold cyan]",
        f"[bold cyan]|[/bold cyan]  Disipador Mosfet   {cpu_b3}    |      |      |      |      |  [bold cyan]|[/bold cyan]",
        f"[bold cyan]|[/bold cyan]                     {cpu_b4}",
        f"[bold cyan]|[/bold cyan]                                                                            +----------------------------+  [bold cyan]|[/bold cyan]",
        f"[bold cyan]|[/bold cyan]                     {m2_line.ljust(90)}",
        f"[bold cyan]|[/bold cyan]                                                                              CONECTOR 24-PIN ATX POWER     [bold cyan]|[/bold cyan]",
        f"[bold cyan]|[/bold cyan] {pcie1_line.ljust(80)}       {chipset_hdr}  [bold cyan]|[/bold cyan]",
        f"[bold cyan]|[/bold cyan]  [dim]─── Ranura PCIe x1 #1 ───────────────────────────────────────[/dim]               {chipset_txt}  [bold cyan]|[/bold cyan]",
        f"[bold cyan]|[/bold cyan]  [dim]─── Ranura PCIe x1 #2 ───────────────────────────────────────[/dim]               {chipset_ftr}  [bold cyan]|[/bold cyan]",
        f"[bold cyan]|[/bold cyan] {pcie2_line.ljust(80)}       [bold green][ 8x PUERTOS SATA 3.0 ][/bold green]    [bold cyan]|[/bold cyan]",
        f"[bold cyan]|[/bold cyan]  [dim]─── Ranura PCIe x1 #3 ───────────────────────────────────────[/dim]               [green]  ═══════════════════  [/green]    [bold cyan]|[/bold cyan]",
        f"[bold cyan]|[/bold cyan]  [dim]─── Ranura PCIe x4 #1 ───────────────────────────────────────[/dim]               [bold cyan][ CABEZALES USB 3.0 ]    [/bold cyan]|",
        f"[bold cyan]|[/bold cyan] [bold magenta][AUDIO REALTEK ALC1220][/bold magenta]                                                       [cyan]  ═══════════════════  [/cyan]    [bold cyan]|[/bold cyan]",
        f"[bold cyan]+════════════════════════════════════════════════════════════════════════════════════════════════════+[/bold cyan]",
    ]

    return "\n".join(lines)


def create_motherboard_map_panel(all_temps, all_fans, selected_idx, board_name, lang="en"):
    """Create the interactive Motherboard Hardware Map panel."""
    combined_items = []
    for t in all_temps:
        combined_items.append({
            "type": "temp",
            "obj": t,
            "title": f"🌡️ {t['device_name']} -> {t['label']}",
            "value": f"{t['current']:4.1f}°C",
            "slot_code": t["slot_code"],
            "location": t["location_name"],
            "description": t["description"]
        })
    for f in all_fans:
        combined_items.append({
            "type": "fan",
            "obj": f,
            "title": f"🌀 {f['name']} ({f['device']})",
            "value": f"{f['rpm']} RPM" if f['rpm'] > 0 else tr("fan_zero_db", lang),
            "slot_code": f["slot_code"],
            "location": f["location"],
            "description": f["description"]
        })

    if not combined_items:
        return Panel(Text("No sensors available.", style="red bold"))

    selected_idx = max(0, min(len(combined_items) - 1, selected_idx))
    active_item = combined_items[selected_idx]

    # Sensor / Fan selector table
    tbl_items = Table(expand=True, box=box.SIMPLE_HEAD, pad_edge=False)
    tbl_items.add_column("Sel", width=3, justify="center")
    tbl_items.add_column("#", width=3, justify="center")
    tbl_items.add_column(tr("col_sensor", lang), ratio=3)
    tbl_items.add_column(tr("col_temp", lang), justify="right", width=14)

    for i, it in enumerate(combined_items):
        is_cur = (i == selected_idx)
        prefix = "▶" if is_cur else " "
        cur_style = "bold white on blue" if is_cur else "white"

        tbl_items.add_row(
            Text(prefix, style="bold yellow" if is_cur else "dim"),
            f"{i+1}",
            Text(it["title"], style=cur_style),
            Text(it["value"], style="bold green" if ("°C" in it["value"] and float(it["value"][:-2]) < 65) or "RPM" in it["value"] else "yellow")
        )

    # Technical Details Card
    detail_text = Text()
    detail_text.append(f"{tr('selected_item', lang)} ", style="bold cyan")
    detail_text.append(f"{active_item['title']}\n", style="bold white")
    detail_text.append(f"{tr('location_on_board', lang)} ", style="bold yellow")
    detail_text.append(f"{active_item['location']}\n", style="bold white")
    detail_text.append(f"{tr('realtime_value', lang)} ", style="bold cyan")
    detail_text.append(f"{active_item['value']}\n", style="bold green")
    detail_text.append(f"{tr('physical_desc', lang)} ", style="bold cyan")
    detail_text.append(f"{active_item['description']}", style="italic white")

    # ASCII Map Rendering
    raw_obj = active_item["obj"]
    ascii_map = generate_motherboard_ascii(board_name, active_item["slot_code"], raw_obj, lang=lang)

    map_layout = Layout()
    map_layout.split_column(
        Layout(name="board_graphic", size=24),
        Layout(name="bottom_area", size=10),
    )
    map_layout["board_graphic"].update(Panel(Text.from_markup(ascii_map), title=f"[bold cyan]{tr('map_title', lang)}[/bold cyan]", border_style="cyan"))

    map_layout["bottom_area"].split_row(
        Layout(name="selector", ratio=3),
        Layout(name="info", ratio=4),
    )
    map_layout["selector"].update(Panel(tbl_items, title=f"[bold yellow]{tr('nav_sensors', lang)}[/bold yellow]", border_style="yellow"))
    map_layout["info"].update(Panel(detail_text, title=f"[bold green]{tr('sensor_tech_sheet', lang)}[/bold green]", border_style="green"))

    return map_layout


def build_dashboard(sampler, all_temps, all_fans, lang="en"):
    """Assemble all sub-panels into the primary dashboard layout."""
    cpu_info = sampler.sample_cpu()
    mem_info = sampler.sample_memory()
    io_info = sampler.sample_io()
    gpu_list = sampler.sample_gpus()

    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="gpus", size=4 + max(len(gpu_list) * 2, 4)),
        Layout(name="cpu_mem", size=9),
        Layout(name="thermal_fans", size=11),
        Layout(name="io", size=5),
        Layout(name="footer", size=1),
    )

    header_text = Text.assemble(
        (" ⚡ SYSMON PRO ", "bold black on cyan"),
        (f"  {sampler.board_name}  ", "bold white"),
        (f" {tr('press_map', lang)}  ", "bold yellow"),
        (f" {tr('press_exit', lang)}", "dim")
    )
    layout["header"].update(Panel(header_text, border_style="cyan"))

    layout["gpus"].update(create_gpu_panel(gpu_list, lang=lang))

    layout["cpu_mem"].split_row(
        Layout(name="cpu", ratio=3),
        Layout(name="mem", ratio=2),
    )
    layout["cpu"].update(create_cpu_panel(cpu_info, lang=lang))
    layout["mem"].update(create_mem_panel(mem_info, lang=lang))

    layout["thermal_fans"].update(create_thermal_and_fans_panel(all_temps, all_fans, lang=lang))

    layout["io"].update(create_io_panel(io_info, lang=lang))

    footer = Text.assemble(
        (" [M / Tab] ", "bold cyan"),
        (f"{tr('footer_map', lang)}  ", "white"),
        (" [1-9 / ↑ / ↓] ", "bold yellow"),
        (f"{tr('footer_select', lang)}  ", "white"),
        (" [L] ", "bold magenta"),
        (f"{tr('footer_lang', lang)}: [{lang.upper()}]  ", "white"),
        (" [Q] ", "bold red"),
        (f"{tr('footer_quit', lang)}  |  ", "white"),
        (f"{tr('updated', lang)}: {time.strftime('%H:%M:%S')}", "dim")
    )
    layout["footer"].update(footer)

    return layout


def read_key(timeout=0.0):
    """Read a non-blocking keystroke from standard input."""
    if not sys.stdin.isatty():
        return None
    r, _, _ = select.select([sys.stdin], [], [], timeout)
    if not r:
        return None
    ch = sys.stdin.read(1)
    if ch == '\x1b':
        r2, _, _ = select.select([sys.stdin], [], [], 0.05)
        if r2:
            ch2 = sys.stdin.read(1)
            if ch2 == '[':
                ch3 = sys.stdin.read(1)
                if ch3 == 'A':
                    return 'UP'
                elif ch3 == 'B':
                    return 'DOWN'
                elif ch3 == 'C':
                    return 'RIGHT'
                elif ch3 == 'D':
                    return 'LEFT'
                return f'ESC[{ch3}'
            return f'ESC{ch2}'
        return 'ESC'
    return ch


# ==============================================================================
# Main Entry Point
# ==============================================================================
def main():
    parser = argparse.ArgumentParser(description="SysMon Pro - Dual GPU & Motherboard Hardware Monitor")
    parser.add_argument("-m", "--map", action="store_true", help="Launch directly into Motherboard Hardware Map mode")
    parser.add_argument("-l", "--lang", choices=["en", "es"], default=None, help="Set interface language ('en' for English, 'es' for Spanish)")
    args = parser.parse_args()

    # Determine initial language (CLI flag > system locale > English)
    current_lang = args.lang if args.lang else detect_default_language()

    console = Console()
    sampler = HardwareSampler()

    # Initial CPU sample to prime utilization deltas
    psutil.cpu_percent(interval=None)
    psutil.cpu_percent(interval=None, percpu=True)
    time.sleep(0.1)

    view_mode = "map" if args.map else "dashboard"
    selected_idx = 0

    old_term_settings = None
    is_tty = sys.stdin.isatty()
    if is_tty:
        try:
            old_term_settings = termios.tcgetattr(sys.stdin.fileno())
            tty.setcbreak(sys.stdin.fileno())
        except Exception:
            old_term_settings = None

    try:
        all_temps = sampler.sample_all_temperatures(lang=current_lang)
        all_fans = sampler.sample_fans(lang=current_lang)
        total_items = len(all_temps) + len(all_fans)

        first_view = create_motherboard_map_panel(all_temps, all_fans, selected_idx, sampler.board_name, lang=current_lang) if view_mode == "map" else build_dashboard(sampler, all_temps, all_fans, lang=current_lang)

        with Live(first_view, console=console, refresh_per_second=4, screen=True) as live:
            last_sample_time = time.time()

            while True:
                now = time.time()
                need_refresh = False

                key = read_key(timeout=0.1)
                if key:
                    if key in ['q', 'Q']:
                        break
                    elif key in ['l', 'L']:
                        # Toggle language between English and Spanish
                        current_lang = "es" if current_lang == "en" else "en"
                        need_refresh = True
                    elif key in ['m', 'M', '\t']:
                        view_mode = "dashboard" if view_mode == "map" else "map"
                        need_refresh = True
                    elif key in ['ESC']:
                        if view_mode == "map":
                            view_mode = "dashboard"
                            need_refresh = True
                        else:
                            break
                    elif key in ['UP', 'k', 'LEFT']:
                        selected_idx = max(0, selected_idx - 1)
                        need_refresh = True
                    elif key in ['DOWN', 'j', 'RIGHT']:
                        selected_idx = min(max(0, total_items - 1), selected_idx + 1)
                        need_refresh = True
                    elif key.isdigit() and int(key) > 0:
                        target = int(key) - 1
                        if target < total_items:
                            selected_idx = target
                            need_refresh = True

                if now - last_sample_time >= 1.0 or need_refresh:
                    last_sample_time = now
                    all_temps = sampler.sample_all_temperatures(lang=current_lang)
                    all_fans = sampler.sample_fans(lang=current_lang)
                    total_items = len(all_temps) + len(all_fans)

                    if view_mode == "map":
                        live.update(create_motherboard_map_panel(all_temps, all_fans, selected_idx, sampler.board_name, lang=current_lang))
                    else:
                        live.update(build_dashboard(sampler, all_temps, all_fans, lang=current_lang))

    except KeyboardInterrupt:
        pass
    finally:
        if is_tty and old_term_settings:
            try:
                termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_term_settings)
            except Exception:
                pass


if __name__ == "__main__":
    main()
