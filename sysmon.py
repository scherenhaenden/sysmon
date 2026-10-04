#!/usr/bin/env python3
"""
SysMon Pro - Monitor de Sistema y Hardware para Terminal (Inspirado en nvtop y btop).
Soporte completo para:
- Múltiples GPUs (Dual AMD Radeon RX 9070 en PCIe Slot 1 y Slot 2).
- Monitor de Ventiladores (RPM y PWM % en GPUs y chasis).
- Área completa de TODAS las temperaturas disponibles.
- Localizador Gráfico en Placa Base (Motherboard Map) con iluminación dinámica.
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
    sys.exit("Error: Se requiere la librería 'rich'. Instalar con: pip install rich")


def human_bytes(bytes_val, suffix="B"):
    """Convierte bytes a formato legible (KB, MB, GB, etc.)"""
    for unit in ["", "K", "M", "G", "T", "P"]:
        if abs(bytes_val) < 1024.0:
            return f"{bytes_val:5.1f} {unit}{suffix}"
        bytes_val /= 1024.0
    return f"{bytes_val:5.1f} E{suffix}"


def human_speed(bps):
    """Convierte bytes/segundo a velocidad legible."""
    return f"{human_bytes(bps)}/s"


def make_gauge(percent, length=14, high_thresh=85, med_thresh=65):
    """Crea una barra gráfica ASCII/Unicode coloreada con porcentaje."""
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
    """Barra gráfica para temperaturas con gradiente de color."""
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


def make_fan_bar(rpm, pwm_pct=None, max_rpm=3600, length=10):
    """Barra gráfica para ventiladores."""
    if rpm == 0:
        return Text("0 dB (Parado)", style="cyan dim")
    ratio = min(1.0, rpm / max_rpm) if max_rpm else 0.5
    fill_len = int(round(ratio * length))
    empty_len = length - fill_len

    color = "yellow" if rpm > 2200 else "green"
    bar = "█" * fill_len + "░" * empty_len
    pct_str = f" ({pwm_pct:.0f}%)" if pwm_pct is not None else ""
    return Text.assemble((bar, color), (f" {rpm} RPM{pct_str}", f"{color}"))


class HardwareSampler:
    """Recolector integral de hardware: CPU, RAM, I/O, Dual GPUs, Ventiladores y Sensores Térmicos."""

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
        """Detecta fabricante y modelo de la placa base."""
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
        """Descubre todas las tarjetas AMD y las ordena por orden físico PCIe de ranura."""
        cards = []
        for card_path in glob.glob("/sys/class/drm/card[0-9]*"):
            # Omitir puertos de salida como card0-DP-1
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
                    
                    # Comprobar modelo o sub-marca
                    prod_file = os.path.join(device_dir, "product_name")
                    if os.path.isfile(prod_file):
                        try:
                            with open(prod_file, "r") as f:
                                prod_str = f.read().strip()
                                if prod_str:
                                    name = prod_str
                        except Exception:
                            pass

                    # Encontrar nodo hwmon correspondiente
                    hwmons = glob.glob(os.path.join(device_dir, "hwmon", "hwmon*"))
                    hwmon_path = hwmons[0] if hwmons else None

                    cards.append({
                        "card": os.path.basename(card_path),
                        "pci_addr": pci_slot,
                        "path": device_dir,
                        "name": name,
                        "hwmon": hwmon_path
                    })

        # ORDENAR por dirección física de bus PCIe: 0d:00.0 (Slot 1) antes que 10:00.0 (Slot 2)
        cards.sort(key=lambda x: x["pci_addr"])
        for idx, c in enumerate(cards):
            c["slot_num"] = idx + 1
            c["slot_name"] = f"PCIe Slot #{idx+1} ({c['pci_addr']})"
        return cards

    def sample_cpu(self):
        """Muestreo de CPU."""
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
        """Muestreo de Memoria RAM y Swap."""
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
        """Muestreo de I/O de disco y transferencias de red."""
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
        """Muestreo detallado de ambas GPUs AMD (y NVIDIA si existiera)."""
        gpu_stats = []

        # 1. GPUs AMD
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

            # Carga de GPU
            busy_path = os.path.join(dev, "gpu_busy_percent")
            if os.path.isfile(busy_path):
                try:
                    with open(busy_path, "r") as f:
                        stat["busy_pct"] = float(f.read().strip())
                except Exception:
                    pass

            # Memoria VRAM
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

            # HWMon de la GPU (Potencia, Ventiladores, Temperaturas)
            hw = card["hwmon"]
            if hw and os.path.isdir(hw):
                # Potencia
                for p_file in ["power1_average", "power1_input"]:
                    p_path = os.path.join(hw, p_file)
                    if os.path.isfile(p_path):
                        try:
                            with open(p_path, "r") as f:
                                stat["power_w"] = float(f.read().strip()) / 1e6
                                break
                        except Exception:
                            pass

                # Ventilador RPM
                fan_path = os.path.join(hw, "fan1_input")
                if os.path.isfile(fan_path):
                    try:
                        with open(fan_path, "r") as f:
                            stat["fan_rpm"] = int(f.read().strip())
                    except Exception:
                        pass

                # PWM Ventilador
                pwm_path = os.path.join(hw, "pwm1")
                if os.path.isfile(pwm_path):
                    try:
                        with open(pwm_path, "r") as f:
                            val = int(f.read().strip())
                            stat["fan_pwm"] = (val / 255.0) * 100.0
                    except Exception:
                        pass

                # Temperaturas: edge, junction, mem
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

        # 2. NVIDIA GPUs si las hubiera
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

    def sample_fans(self):
        """Muestrea todos los ventiladores del sistema (GPU 1, GPU 2 y Placa Base)."""
        fan_list = []
        fan_id = 1

        # Ventiladores de las GPUs
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

            status_txt = "0 dB Modo Silencioso (Parado)" if rpm == 0 else f"Activo ({rpm} RPM)"
            fan_list.append({
                "id": fan_id,
                "name": f"Ventilador GPU {idx+1}",
                "device": f"{card['name']} (PCIe #{idx+1})",
                "rpm": rpm,
                "pwm_pct": pwm_pct,
                "status": status_txt,
                "slot_code": f"PCIE_{idx+1}_FAN",
                "location": f"Disipador GPU {idx+1} en Ranura PCIe x16 #{idx+1}",
                "description": f"Ventiladores del disipador de la tarjeta gráfica {idx+1}. Se apagan en reposo (Zero-RPM) cuando la temperatura es menor a 50°C."
            })
            fan_id += 1

        # Ventiladores adicionales en hwmon (p.ej. placas con it87, nct6775 o controladores de AIO)
        for hw_dir in glob.glob("/sys/class/hwmon/hwmon*"):
            h_name = "unknown"
            name_file = os.path.join(hw_dir, "name")
            if os.path.isfile(name_file):
                try:
                    with open(name_file, "r") as nf:
                        h_name = nf.read().strip()
                except Exception:
                    pass

            # Omitir GPUs ya procesadas
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
                        "name": f"Ventilador {lbl.upper()}",
                        "device": f"Placa Base ({h_name})",
                        "rpm": r_val,
                        "pwm_pct": None,
                        "status": f"{r_val} RPM",
                        "slot_code": "MB_FAN",
                        "location": "Cabezal de Ventilador en Placa Base (CPU_FAN / SYS_FAN)",
                        "description": "Ventilador conectado a los cabezales PWM de la placa base."
                    })
                    fan_id += 1
                except Exception:
                    pass

        return fan_list

    def sample_all_temperatures(self):
        """Recolecta todos los sensores de temperatura y los mapea físicamente."""
        sensors_list = []
        raw_temps = psutil.sensors_temperatures() if hasattr(psutil, "sensors_temperatures") else {}
        sensor_id = 1

        # 1. CPU (k10temp)
        for chip_name in ["k10temp", "zenpower", "coretemp", "cpu_thermal"]:
            if chip_name in raw_temps:
                for entry in raw_temps[chip_name]:
                    label = entry.label or "CPU Temp"
                    desc = "Temperatura física de los núcleos (die) de silicio del procesador Ryzen." if label == "Tdie" else "Temperatura de control con offset para gestión de ventiladores."
                    sensors_list.append({
                        "id": sensor_id,
                        "chip": chip_name,
                        "label": label,
                        "current": entry.current,
                        "high": entry.high or 85.0,
                        "critical": entry.critical or 95.0,
                        "category": "CPU",
                        "device_name": "Procesador AMD Ryzen (CPU)",
                        "location_name": "Socket AM4 (Centro Superior)",
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
                    "device_name": "SSD M.2 NVMe (Phison E12 PCIe x4)",
                    "location_name": "Ranura M.2 Socket 3 (Bajo el Socket AM4)",
                    "slot_code": "M2_SLOT",
                    "description": "Temperatura compuesta del controlador y chips de memoria NAND Flash.",
                })
                sensor_id += 1

        # 3. Dual GPUs AMD (ordenadas por Slot 1 y Slot 2)
        gpu_stats = self.sample_gpus()
        for g in gpu_stats:
            g_num = g["slot_num"]
            slot_code = f"PCIE_{g_num}"
            loc_str = f"Ranura PCIe x16 #{g_num} (Blindada - {g['pci_addr']})"

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
                    "description": f"Temperatura perimetral del chip gráfico en PCIe Slot #{g_num}.",
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
                    "description": f"Punto más caliente (Hotspot) del silicio gráfico en PCIe Slot #{g_num}.",
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
                    "description": f"Módulos de memoria de vídeo (VRAM GDDR6) en PCIe Slot #{g_num}.",
                })
                sensor_id += 1

        return sensors_list


def create_gpu_panel(gpu_list):
    """Renderiza ambas GPUs al estilo nvtop destacando ambas tarjetas."""
    if not gpu_list:
        return Panel(Text("No se detectaron GPUs.", style="dim italic"),
                     title="[bold red]GPU Monitoring[/bold red]", border_style="red")

    tbl = Table(expand=True, box=box.SIMPLE_HEAD, pad_edge=False)
    tbl.add_column("Slot", style="bold cyan", width=8)
    tbl.add_column("Tarjeta / Modelo", style="bold white", ratio=3)
    tbl.add_column("Uso GPU", ratio=2)
    tbl.add_column("Uso VRAM", ratio=3)
    tbl.add_column("Edge", justify="center", width=7)
    tbl.add_column("Junc", justify="center", width=7)
    tbl.add_column("Mem", justify="center", width=7)
    tbl.add_column("Potencia", justify="right", width=8)
    tbl.add_column("Ventilador", justify="right", width=16)

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

        # Ventilador
        if g['fan_rpm'] == 0:
            fan_cell = Text("0 dB (0 RPM)", style="cyan dim")
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

    return Panel(tbl, title="[bold red]󰢮 MONITOR DUAL GPU (AMD Radeon RX 9070 en PCIe 1 y PCIe 2)[/bold red]", border_style="red")


def create_thermal_and_fans_panel(all_temps, all_fans):
    """Panel unificado con TODAS las temperaturas y los ventiladores del sistema."""
    grid = Table.grid(padding=(0, 2), expand=True)
    grid.add_column(ratio=5)
    grid.add_column(ratio=3)

    # 1. Tabla de Temperaturas
    t_tbl = Table(expand=True, box=box.SIMPLE_HEAD, pad_edge=False)
    t_tbl.add_column("ID", style="bold cyan", width=4, justify="center")
    t_tbl.add_column("Componente", style="bold white", ratio=3)
    t_tbl.add_column("Sensor", style="cyan", width=14)
    t_tbl.add_column("Temp", justify="center", width=8)
    t_tbl.add_column("Estado", ratio=2)
    t_tbl.add_column("Límites", justify="center", width=11)

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

    # 2. Tabla de Ventiladores
    f_tbl = Table(expand=True, box=box.SIMPLE_HEAD, pad_edge=False)
    f_tbl.add_column("Ventilador", style="bold white", ratio=3)
    f_tbl.add_column("RPM / Velocidad", justify="right", ratio=3)

    for f in all_fans:
        f_bar = make_fan_bar(f["rpm"], f["pwm_pct"], length=8)
        f_tbl.add_row(
            f["name"],
            f_bar
        )

    # Indicador de cabezales de placa base si no reportan por sysfs
    f_tbl.add_row(Text("Cabezal CPU_FAN", style="dim"), Text("Conectado (Placa)", style="dim"))
    f_tbl.add_row(Text("Cabezal SYS_FAN1-4", style="dim"), Text("PWM Inteligente", style="dim"))

    grid.add_row(t_tbl, f_tbl)

    title_text = "[bold yellow]🌡️ TODAS LAS TEMPERATURAS Y 🌀 VENTILADORES DEL SISTEMA[/bold yellow]  [dim]— Pulsa [bold cyan]M[/bold cyan] para ver en Placa Base[/dim]"
    return Panel(grid, title=title_text, border_style="yellow")


def create_cpu_panel(cpu_info):
    """Renderiza la sección de CPU."""
    tbl = Table.grid(padding=(0, 1), expand=True)
    tbl.add_column(ratio=2)
    tbl.add_column(ratio=3)

    freq_str = f"{cpu_info['freq_ghz']:.2f} GHz" if cpu_info['freq_ghz'] > 0 else "N/A"

    info_text = Text()
    info_text.append("Carga:  ", style="cyan bold")
    info_text.append(f"{cpu_info['total_pct']:5.1f}%\n", style="white bold")
    info_text.append("Temp:   ", style="cyan bold")
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

    info_text.append("Reloj:  ", style="cyan bold")
    info_text.append(f"{freq_str}\n", style="white")
    info_text.append("Hilos:  ", style="cyan bold")
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
    return Panel(tbl, title="[bold blue]󰻠 CPU (AMD Ryzen)[/bold blue]", border_style="blue")


def create_mem_panel(mem_info):
    """Renderiza la sección de RAM y Swap."""
    tbl = Table.grid(padding=(0, 1), expand=True)
    tbl.add_column(width=6)
    tbl.add_column(ratio=1)
    tbl.add_column(width=22)

    ram_bar = make_gauge(mem_info['ram_pct'], length=16)
    ram_text = f"{human_bytes(mem_info['ram_used'])} / {human_bytes(mem_info['ram_total'])}"
    tbl.add_row(Text("RAM: ", style="bold green"), ram_bar, Text(ram_text, style="white", justify="right"))

    swap_bar = make_gauge(mem_info['swap_pct'], length=16)
    swap_text = f"{human_bytes(mem_info['swap_used'])} / {human_bytes(mem_info['swap_total'])}"
    tbl.add_row(Text("Swap:", style="bold yellow"), swap_bar, Text(swap_text, style="white", justify="right"))

    return Panel(tbl, title="[bold green]󰍛 Memoria RAM & Swap[/bold green]", border_style="green")


def create_io_panel(io_info):
    """Renderiza I/O de disco y red."""
    tbl = Table.grid(padding=(0, 2), expand=True)
    tbl.add_column(ratio=1)
    tbl.add_column(ratio=1)

    disk_t = Text()
    disk_t.append("Lectura Disco: ", style="cyan bold")
    disk_t.append(f"{human_speed(io_info['disk_read_bps'])}\n", style="bold green" if io_info['disk_read_bps'] > 0 else "white")
    disk_t.append("Escritura:     ", style="cyan bold")
    disk_t.append(f"{human_speed(io_info['disk_write_bps'])}\n", style="bold yellow" if io_info['disk_write_bps'] > 0 else "white")
    disk_t.append("Disco Raíz:    ", style="cyan bold")
    disk_t.append(f"{io_info['disk_pct']}% ({human_bytes(io_info['disk_used'])}/{human_bytes(io_info['disk_total'])})", style="white")

    net_t = Text()
    net_t.append("Red Bajada (Rx): ", style="magenta bold")
    net_t.append(f"{human_speed(io_info['net_rx_bps'])}\n", style="bold green" if io_info['net_rx_bps'] > 0 else "white")
    net_t.append("Red Subida (Tx): ", style="magenta bold")
    net_t.append(f"{human_speed(io_info['net_tx_bps'])}\n", style="bold yellow" if io_info['net_tx_bps'] > 0 else "white")

    tbl.add_row(disk_t, net_t)
    return Panel(tbl, title="[bold magenta]󰋊 Disco & Red I/O[/bold magenta]", border_style="magenta")


def generate_motherboard_ascii(board_name, active_slot, selected_item):
    """
    Diagrama gráfico ASCII de la placa base con ILUMINACIÓN DINÁMICA
    de CPU, SSD M.2, GPU 1 (Slot 1), GPU 2 (Slot 2), Ventiladores y Chipset.
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
            val_str = f"{selected_item['rpm']} RPM" if selected_item['rpm'] > 0 else "0 dB (0 RPM)"

    # Bloque CPU Socket
    if is_cpu:
        cpu_b1 = "[bold red]╔═════════════════════════════════════════════════╗[/bold red]"
        cpu_b2 = f"[bold white on red]   ★★★ SOCKET CPU AM4 / PROCESADOR RYZEN ★★★    [/bold white on red]"
        cpu_b3 = f"[bold white on red]      ▶▶ SENSOR ACTIVO: {selected_item['label']} = {val_str} ◀◀       [/bold white on red]"
        cpu_b4 = "[bold red]╚═════════════════════════════════════════════════╝[/bold red] [bold yellow]◄── SENSOR SELECCIONADO AQUÍ![/bold yellow]"
    else:
        cpu_b1 = "[blue]┌─────────────────────────────────────────────────┐[/blue]"
        cpu_b2 = "[bold cyan]             SOCKET CPU AM4 (RYZEN)               [/bold cyan]"
        cpu_b3 = "[dim]        [ Procesador & Disipador CPU ]           [/dim]"
        cpu_b4 = "[blue]└─────────────────────────────────────────────────┘[/blue]"

    # Bloque Cabezal CPU_FAN
    cpu_fan_hdr = "[bold white on yellow] [CPU_FAN & PUMP: ◄── AQUÍ] [/bold white on yellow]" if is_fan_hdr else "[dim][CPU_FAN & PUMP][/dim]"

    # Bloque Ranura M.2 NVMe SSD
    if is_nvme:
        m2_line = f"[bold white on magenta] ╔══ ★★★ RANURA M.2 NVMe SSD (Phison E12) [{val_str}] ★★★ ══╗ [/bold white on magenta] [bold yellow]◄── SENSOR AQUÍ![/bold yellow]"
    else:
        m2_line = "[green] ┌── [ Ranura M.2 Socket 3 NVMe SSD PCIe x4 ] ──┐ [/green]"

    # Bloque GPU 1 en Ranura PCIe x16 #1
    if is_gpu1:
        pcie1_line = f"[bold white on red] ╔══ ★★★ GPU 1: RADEON RX 9070 (Slot PCIe #1) [{val_str}] ★★★ ══╗ [/bold white on red] [bold yellow]◄── AQUÍ ESTÁ![/bold yellow]"
    else:
        pcie1_line = "[cyan] ┌── [ RANURA PCIe x16 #1 (GPU 1 Principal: Radeon RX 9070) ] ──┐ [/cyan]"

    # Bloque GPU 2 en Ranura PCIe x16 #2
    if is_gpu2:
        pcie2_line = f"[bold white on red] ╔══ ★★★ GPU 2: RADEON RX 9070 (Slot PCIe #2) [{val_str}] ★★★ ══╗ [/bold white on red] [bold yellow]◄── AQUÍ ESTÁ![/bold yellow]"
    else:
        pcie2_line = "[cyan] ┌── [ RANURA PCIe x16 #2 (GPU 2 Secundaria: Radeon RX 9070) ] ──┐ [/cyan]"

    # Bloque Chipset
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
        f"[bold cyan]|[/bold cyan] [bold white]PLACA DETECTADA:[/bold white] [bold yellow]{board_name.center(80)}[/bold yellow] [bold cyan]|[/bold cyan]",
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


def create_motherboard_map_panel(all_temps, all_fans, selected_idx, board_name):
    """Crea la vista interactiva del Mapa de Sensores y Ventiladores."""
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
            "value": f"{f['rpm']} RPM" if f['rpm'] > 0 else "0 dB (Parado)",
            "slot_code": f["slot_code"],
            "location": f["location"],
            "description": f["description"]
        })

    if not combined_items:
        return Panel(Text("No hay sensores disponibles.", style="red bold"))

    selected_idx = max(0, min(len(combined_items) - 1, selected_idx))
    active_item = combined_items[selected_idx]

    # Tabla de Selección (Izquierda)
    tbl_items = Table(expand=True, box=box.SIMPLE_HEAD, pad_edge=False)
    tbl_items.add_column("Sel", width=3, justify="center")
    tbl_items.add_column("#", width=3, justify="center")
    tbl_items.add_column("Sensor / Ventilador", ratio=3)
    tbl_items.add_column("Valor Actual", justify="right", width=14)

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

    # Detalle Técnico
    detail_text = Text()
    detail_text.append("ELEMENTO SELECCIONADO: ", style="bold cyan")
    detail_text.append(f"{active_item['title']}\n", style="bold white")
    detail_text.append("UBICACIÓN EN PLACA:    ", style="bold yellow")
    detail_text.append(f"{active_item['location']}\n", style="bold white")
    detail_text.append("VALOR EN TIEMPO REAL:  ", style="bold cyan")
    detail_text.append(f"{active_item['value']}\n", style="bold green")
    detail_text.append("DESCRIPCIÓN FÍSICA:    ", style="bold cyan")
    detail_text.append(f"{active_item['description']}", style="italic white")

    # Mapa ASCII
    raw_obj = active_item["obj"]
    ascii_map = generate_motherboard_ascii(board_name, active_item["slot_code"], raw_obj)

    map_layout = Layout()
    map_layout.split_column(
        Layout(name="board_graphic", size=24),
        Layout(name="bottom_area", size=10),
    )
    map_layout["board_graphic"].update(Panel(Text.from_markup(ascii_map), title="[bold cyan]🗺️ ESQUEMA FÍSICO DE LA PLACA BASE — DUAL GPU & SENSORES[/bold cyan]", border_style="cyan"))

    map_layout["bottom_area"].split_row(
        Layout(name="selector", ratio=3),
        Layout(name="info", ratio=4),
    )
    map_layout["selector"].update(Panel(tbl_items, title="[bold yellow]Navegar Sensores [↑/↓ o 1-9][/bold yellow]", border_style="yellow"))
    map_layout["info"].update(Panel(detail_text, title="[bold green]Ficha Técnica del Sensor / Ventilador[/bold green]", border_style="green"))

    return map_layout


def build_dashboard(sampler, all_temps, all_fans):
    """Ensambla el panel principal del monitor."""
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
        (" ⚡ SYSMON DUAL-GPU ", "bold black on cyan"),
        (f"  Placa Base: {sampler.board_name}  ", "bold white"),
        (" [Pulsa 'M' para MAPA VISUAL DE PLACA BASE Y VENTILADORES]  ", "bold yellow"),
        (" [Q: Salir]", "dim")
    )
    layout["header"].update(Panel(header_text, border_style="cyan"))

    layout["gpus"].update(create_gpu_panel(gpu_list))

    layout["cpu_mem"].split_row(
        Layout(name="cpu", ratio=3),
        Layout(name="mem", ratio=2),
    )
    layout["cpu"].update(create_cpu_panel(cpu_info))
    layout["mem"].update(create_mem_panel(mem_info))

    layout["thermal_fans"].update(create_thermal_and_fans_panel(all_temps, all_fans))

    layout["io"].update(create_io_panel(io_info))

    footer = Text.assemble(
        (" [M / Tab] ", "bold cyan"),
        ("🗺️ Mapa Placa Base  ", "white"),
        (" [1-9 / ↑ / ↓] ", "bold yellow"),
        ("Seleccionar Sensor/Ventilador  ", "white"),
        (" [Q] ", "bold red"),
        ("Salir  |  ", "white"),
        (f"Dual GPU Navi 48 | Actualizado: {time.strftime('%H:%M:%S')}", "dim")
    )
    layout["footer"].update(footer)

    return layout


def read_key(timeout=0.0):
    """Lee pulsaciones del teclado de manera no bloqueante."""
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


def main():
    parser = argparse.ArgumentParser(description="SysMon Pro - Dual GPU & Motherboard Sensor Map")
    parser.add_argument("-m", "--map", action="store_true", help="Iniciar directamente en el Mapa de Sensores de la Placa Base")
    args = parser.parse_args()

    console = Console()
    sampler = HardwareSampler()

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
        all_temps = sampler.sample_all_temperatures()
        all_fans = sampler.sample_fans()
        total_items = len(all_temps) + len(all_fans)

        first_view = create_motherboard_map_panel(all_temps, all_fans, selected_idx, sampler.board_name) if view_mode == "map" else build_dashboard(sampler, all_temps, all_fans)

        with Live(first_view, console=console, refresh_per_second=4, screen=True) as live:
            last_sample_time = time.time()

            while True:
                now = time.time()
                need_refresh = False

                key = read_key(timeout=0.1)
                if key:
                    if key in ['q', 'Q']:
                        break
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
                    all_temps = sampler.sample_all_temperatures()
                    all_fans = sampler.sample_fans()
                    total_items = len(all_temps) + len(all_fans)

                    if view_mode == "map":
                        live.update(create_motherboard_map_panel(all_temps, all_fans, selected_idx, sampler.board_name))
                    else:
                        live.update(build_dashboard(sampler, all_temps, all_fans))

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
