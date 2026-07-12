#!/usr/bin/env python3
"""
macOS Hardware Sniffer for OpCore Simplify
Generates hardware report JSON compatible with OpCore Simplify schema.
Usage: python3 hardware_sniffer_mac.py -e -o <output_directory>
"""

import argparse
import json
import os
import plistlib
import re
import struct
import subprocess
import sys


def run(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout
    except:
        return ""


def sysctl_val(key):
    return run(["sysctl", "-n", key]).strip()


def sysctl_int(key):
    v = sysctl_val(key)
    try:
        return int(v)
    except:
        return 0


def profiler_items(datatype):
    out = run(["system_profiler", datatype, "-xml"], timeout=60)
    if not out:
        return []
    try:
        plist = plistlib.loads(out.encode("utf-8"))
        return plist[0].get("_items", []) if plist else []
    except:
        return []


def data_to_u32(data):
    if isinstance(data, bytes) and len(data) >= 4:
        return struct.unpack("<I", data[:4])[0]
    return 0


def hex_strip(val):
    """Strip 0x prefix and return uppercase hex."""
    return val.replace("0x", "").strip() if val else ""


def fmt_dev_id(vid_hex, did_hex):
    """Format vendor/device hex strings to XXXX-XXXX."""
    vid = hex_strip(vid_hex)[:4].upper().zfill(4)
    did = hex_strip(did_hex)[:4].upper().zfill(4)
    return f"{vid}-{did}" if vid or did else "0000-0000"


def slot_to_pci_path(slot_name):
    """Convert macOS slot name (e.g., Internal@0,2,0) to PciRoot format."""
    if not slot_name:
        return ""
    s = slot_name.replace("Internal@", "").replace(" ", "")
    parts = re.split(r"[@/]", s)
    pci_parts = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        nums = part.split(",")
        if len(nums) >= 2:
            dev = int(nums[-2], 16)
            fn = int(nums[-1], 16)
            pci_parts.append(f"Pci(0x{dev:X},0x{fn:X})")
    if pci_parts:
        pci_parts.insert(0, "PciRoot(0x0)")
        return "/".join(pci_parts)
    return ""


def hex_str(val):
    return hex_strip(val).zfill(4).upper() if hex_strip(val) else ""


def pci_device_entry(item):
    """Build standard device entry from SPPCIDataType item."""
    did = item.get("sppci_device-id", "") or ""
    vid = item.get("sppci_vendor-id", "") or ""
    sub_id = item.get("sppci_subsystem-id", "") or ""
    slot = item.get("sppci_slot_name", "") or ""
    device_id = fmt_dev_id(vid, did)
    entry = {
        "Bus Type": "PCI",
        "Device ID": device_id
    }
    if hex_str(sub_id):
        entry["Subsystem ID"] = f"0x{hex_str(sub_id)}"
    if slot:
        entry["PCI Path"] = slot_to_pci_path(slot)
    return entry


def _classify_pci(item):
    """Classify PCI device by its sppci_device_type string."""
    dtype = (item.get("sppci_device_type", "") or "").lower()
    name = (item.get("_name", "") or "").lower()
    if not dtype:
        return None
    if "vga" in dtype or "display" in dtype:
        if "hdmi" not in name:
            return "gpu"
    if "ethernet" in dtype or "network" in dtype:
        return "network"
    if "usb" in dtype:
        return "usb"
    if "audio" in dtype and ("hdmi" in name or "display" in name):
        return "gpu_audio"
    if "audio" in dtype:
        return "audio"
    if "nvme" in dtype or "mass storage" in dtype or "sata" in dtype:
        return "storage"
    if "smbus" in dtype or "communication" in dtype:
        return None
    return "system"


def _parse_gpu_item(item):
    """Build GPU dict from SPDisplaysDataType item, cross-ref with PCI data."""
    name = item.get("sppci_model", "") or item.get("_name", "") or "Unknown"
    vendor_str = item.get("spdisplays_vendor", "") or ""
    device_id_str = item.get("spdisplays_device-id", "") or ""

    manufacturer = "Intel"
    if "amd" in vendor_str.lower() or "radeon" in name.lower():
        manufacturer = "AMD"
    elif "nvidia" in vendor_str.lower() or "nvidia" in name.lower() or "geforce" in name.lower():
        manufacturer = "NVIDIA"
    elif "apple" in name.lower():
        manufacturer = "Apple"

    dev_type = "Discrete GPU"
    if manufacturer == "Intel" or "intel" in name.lower():
        dev_type = "Integrated GPU"

    gpu_key = name.replace("/", "-") or "Unknown GPU"

    gpu = {
        "Manufacturer": manufacturer,
        "Codename": _detect_gpu_codename(name, manufacturer),
        "Device ID": fmt_dev_id("", device_id_str),
        "Device Type": dev_type
    }
    return gpu_key, gpu


def _detect_gpu_codename(name, manufacturer):
    n = name.lower()
    if manufacturer == "Intel" or "intel" in n:
        if "uhd" in n:
            for c in ["630", "610", "620"]:
                if c in n:
                    return "Coffee Lake GT2"
            if "7" in n:
                return "Ice Lake GT2"
            return "Unknown UHD"
        if "iris" in n:
            if "xe" in n:
                return "Alchemist"
            return "Ice Lake GT2"
        if "hd" in n:
            for c in ["530", "540", "550"]:
                if c in n:
                    return "Skylake GT2"
            for c in ["620", "630"]:
                if c in n:
                    return "Kaby Lake GT2"
            return "Intel HD Graphics"
        return "Intel Graphics"
    elif manufacturer == "AMD" or "radeon" in n:
        if "rx" in n:
            if "6800" in n or "6900" in n:
                return "Navi 21"
            if "5700" in n or "5600" in n:
                return "Navi 10"
            if "5500" in n or "5300" in n:
                return "Navi 14"
            if "580" in n or "570" in n or "590" in n:
                return "Polaris 20"
            if "560" in n or "470" in n or "480" in n:
                return "Polaris"
            if "460" in n:
                return "Baffin"
            if "7900" in n or "7800" in n:
                return "RDNA 3"
            return "AMD Radeon"
        if "vega" in n:
            return "Vega"
        if "pro" in n and ("560" in n or "570" in n or "575" in n or "580" in n):
            return "Polaris 20"
        return "AMD"
    elif manufacturer == "NVIDIA" or "nvidia" in n or "geforce" in n:
        if "gtx 10" in n or "gtx 1080" in n:
            return "Pascal"
        if "gtx 9" in n or "gtx 980" in n or "gtx 970" in n:
            return "Maxwell"
        if "rtx" in n:
            return "Turing" if "20" in n else "Ampere"
        if "gtx 7" in n:
            return "Kepler"
        return "NVIDIA"
    return "Unknown"


def _detect_cpu_codename(brand):
    b = brand.lower()
    if "intel" in b:
        if "xeon" in b:
            return "Xeon"
        m = re.search(r"\b(?:i[3579]|core\s*ultra)\s*-?\s*(\d{4,5})\b", brand)
        if m:
            num = int(m.group(1))
            gen = num // 10000 if num >= 10000 else num // 1000
            if "core ultra" in b and gen >= 14:
                return "Meteor Lake"
            elif gen >= 14:
                return "Raptor Lake Refresh"
            elif gen == 13:
                return "Raptor Lake"
            elif gen == 12:
                return "Alder Lake"
            elif gen == 11:
                return "Tiger Lake" if any(x in b for x in ["1155", "1140", "1135", "1125", "1115"]) else "Rocket Lake"
            elif gen == 10:
                return "Ice Lake" if any(x in brand for x in ["1035", "1065", "1068"]) else "Comet Lake"
            elif gen == 9:
                return "Coffee Lake"
            elif gen == 8:
                return "Coffee Lake"
            elif gen == 7:
                return "Kaby Lake"
            elif gen == 6:
                return "Skylake"
            elif gen == 5:
                return "Broadwell"
            elif gen == 4:
                return "Haswell"
            elif gen == 3:
                return "Ivy Bridge"
            elif gen == 2:
                return "Sandy Bridge"
        return "Intel"
    elif "amd" in b:
        if "ryzen" in b or "rayzen" in b:
            if "7000" in b or "8700" in b:
                return "Raphael"
            if "5000" in b:
                return "Vermeer"
            if "3000" in b:
                return "Matisse"
            if "2000" in b:
                return "Pinnacle Ridge"
            if "1000" in b:
                return "Summit Ridge"
        return "AMD Ryzen"
    return "Unknown"


def _normalize_connector(conn_str):
    """Normalize macOS connector type strings to schema values."""
    if not conn_str:
        return "Uninitialized"
    s = conn_str.lower()
    if "dp" in s or "displayport" in s:
        return "DP"
    if "hdmi" in s:
        return "HDMI"
    if "dvi" in s:
        return "DVI"
    if "vga" in s:
        return "VGA"
    if "internal" in s or "lvds" in s or "edp" in s:
        return "Internal" if "lvds" not in s else "LVDS"
    return "Uninitialized"


def _normalize_resolution(res_str):
    """Extract WxH from macOS resolution string."""
    if not res_str:
        return ""
    m = re.match(r"(\d+)\s*x\s*(\d+)", res_str)
    if m:
        return f"{m.group(1)}x{m.group(2)}"
    return res_str


def collect_all():
    """Collect all hardware info and return the report dict."""

    # -- PCI data first (used for cross-referencing) --
    pci_items = profiler_items("SPPCIDataType")
    pci_by_name = {}
    pci_by_type = {}
    for item in pci_items:
        name = item.get("_name", "")
        pci_by_name[name] = item
        ctype = _classify_pci(item)
        if ctype:
            pci_by_type.setdefault(ctype, []).append(item)

    # -- Motherboard --
    hw_items = profiler_items("SPHardwareDataType")
    hw = hw_items[0] if hw_items else {}
    model = hw.get("machine_model", "") or hw.get("machine_name", "") or "Unknown"
    is_laptop = any(x in model.lower() for x in ["macbook", "macbookpro", "macbookair"])
    platform = "Laptop" if is_laptop else "Desktop"
    chipset = "Unknown"
    if "macpro" in model.lower():
        chipset = "Intel C422"
    elif "macmini" in model.lower():
        chipset = "Intel H310"
    elif "imac" in model.lower():
        # Try to detect from CPU generation
        pass  # Keep Unknown for now
    motherboard = {"Name": model, "Chipset": chipset, "Platform": platform}

    # -- BIOS --
    rom = hw.get("boot_rom_version", "") or hw.get("Boot ROM Version", "") or ""
    sip_out = run(["csrutil", "status"], timeout=5)
    secure_boot = "Enabled" if "enabled" in sip_out.lower() else "Disabled"
    bios = {
        "Version": rom,
        "Firmware Type": "UEFI",
        "Secure Boot": secure_boot
    }

    # -- CPU --
    brand = sysctl_val("machdep.cpu.brand_string")
    manufacturer = "Intel" if "Intel" in brand else ("AMD" if "AMD" in brand else "Unknown")
    features = sysctl_val("machdep.cpu.features")
    cpu = {
        "Manufacturer": manufacturer,
        "Processor Name": brand,
        "Codename": _detect_cpu_codename(brand),
        "Core Count": str(sysctl_int("hw.physicalcpu")),
        "CPU Count": str(sysctl_int("hw.logicalcpu")),
        "SIMD Features": features
    }

    # -- GPU --
    gpu_items = profiler_items("SPDisplaysDataType")
    gpus = {}
    for item in gpu_items:
        gpu_key, gpu_data = _parse_gpu_item(item)
        # Cross-reference with PCI data for device ID and path
        name = item.get("sppci_model", "") or item.get("_name", "")
        pci_match = pci_by_name.get(name)
        if pci_match:
            pci_eid = pci_match.get("sppci_device-id", "") or ""
            pci_vid = pci_match.get("sppci_vendor-id", "") or ""
            if pci_eid and pci_vid:
                gpu_data["Device ID"] = fmt_dev_id(pci_vid, pci_eid)
            sub_id = pci_match.get("sppci_subsystem-id", "") or ""
            if sub_id:
                gpu_data["Subsystem ID"] = f"0x{hex_str(sub_id)}"
            slot = pci_match.get("sppci_slot_name", "") or ""
            if slot:
                gpu_data["PCI Path"] = slot_to_pci_path(slot)
        gpus[gpu_key] = gpu_data

    # -- Monitor --
    monitors = {}
    for item in gpu_items:
        displays = item.get("spdisplays_ndrvs", []) or []
        for disp in displays:
            dname = disp.get("_name", "") or disp.get("spdisplays_display-product-name", "") or "Unknown Monitor"
            res = (disp.get("_spdisplays_resolution", "") or
                   disp.get("spdisplays_resolution", "") or "")
            conn = disp.get("spdisplays_connection_type", "") or ""
            gpu_ref = item.get("sppci_model", "") or ""
            mon_key = dname.replace("/", "-") or "Monitor"
            entry = {
                "Connector Type": _normalize_connector(conn),
                "Resolution": _normalize_resolution(res)
            }
            if gpu_ref:
                entry["Connected GPU"] = gpu_ref
            monitors[mon_key] = entry

    # -- Network --
    networks = {}
    for item in pci_by_type.get("network", []):
        name = item.get("_name", "") or "Unknown Network"
        entry = pci_device_entry(item)
        entry.pop("ACPI Path", None)
        key = name.replace("/", "-") or f"Net_{len(networks)}"
        networks[key] = entry

    # -- Sound --
    sounds = {}
    for item in pci_by_type.get("audio", []):
        name = item.get("_name", "") or "Unknown Audio"
        did = item.get("sppci_device-id", "") or ""
        vid = item.get("sppci_vendor-id", "") or ""
        sub_id = item.get("sppci_subsystem-id", "") or ""
        key = name.replace("/", "-") or f"Audio_{len(sounds)}"
        entry = {
            "Bus Type": "PCI",
            "Device ID": fmt_dev_id(vid, did)
        }
        if hex_str(sub_id):
            entry["Subsystem ID"] = f"0x{hex_str(sub_id)}"
        entry["Audio Endpoints"] = []
        sounds[key] = entry

    # -- USB Controllers --
    usb_controllers = {}
    for item in pci_by_type.get("usb", []):
        name = item.get("_name", "") or "Unknown USB"
        entry = pci_device_entry(item)
        entry.pop("ACPI Path", None)
        key = name.replace("/", "-") or f"USB_{len(usb_controllers)}"
        usb_controllers[key] = entry
    if not usb_controllers:
        usb_items = profiler_items("SPUSBDataType")
        for item in usb_items:
            name = item.get("_name", "") or "Unknown USB"
            did = (item.get("pci_device", "") or "")
            vid = (item.get("pci_vendor", "") or "")
            key = name.replace("/", "-") or f"USB_{len(usb_controllers)}"
            entry = {
                "Bus Type": "USB",
                "Device ID": fmt_dev_id(vid, did)
            }
            usb_controllers[key] = entry

    # -- Input --
    inputs = {}
    usb_items = profiler_items("SPUSBDataType")
    for item in usb_items:
        name = item.get("_name", "") or ""
        n = name.lower()
        if not any(x in n for x in ["keyboard", "mouse", "touchpad", "trackpad",
                                     "trackpoint", "touchscreen", "tablet",
                                     "digitizer", "pen", "stylus", "wacom"]):
            continue
        key = name.replace("/", "-") or f"Inp_{len(inputs)}"
        d_type = "Keyboard" if "keyboard" in n else ("Mouse" if "mouse" in n else "Input")
        entry = {"Bus Type": "USB"}
        if name:
            entry["Device"] = name
        if d_type:
            entry["Device Type"] = d_type
        inputs[key] = entry
    if not inputs:
        inputs["USB Input"] = {
            "Bus Type": "USB",
            "Device": "Unknown",
            "Device Type": "Input"
        }

    # -- Storage Controllers --
    storages = {}
    for item in pci_by_type.get("storage", []):
        name = item.get("_name", "") or "Unknown Storage"
        entry = pci_device_entry(item)
        entry.pop("ACPI Path", None)
        key = name.replace("/", "-") or f"Stor_{len(storages)}"
        entry["Disk Drives"] = []
        storages[key] = entry
    if not storages:
        # Try NVMe data
        nvme_items = profiler_items("SPNVMeDataType")
        for item in nvme_items:
            name = item.get("_name", "") or "Unknown NVMe"
            key = name.replace("/", "-") or f"NVMe_{len(storages)}"
            drives = []
            for d in item.get("spnvme_disks", []) or []:
                if isinstance(d, dict):
                    drives.append(d.get("_name", "") or "")
                else:
                    drives.append(str(d))
            entry = {
                "Bus Type": "PCI",
                "Device ID": "0000-0000"
            }
            if drives:
                entry["Disk Drives"] = drives
            storages[key] = entry

    # -- Bluetooth --
    bluetooth = {}
    bt_items = profiler_items("SPBluetoothDataType")
    for item in bt_items:
        name = item.get("_name", "") or item.get("spbluetooth_controller_name", "") or "Bluetooth"
        key = name.replace("/", "-") or "Bluetooth"
        vid = item.get("spbluetooth_vendor_id", "") or ""
        pid = item.get("spbluetooth_product_id", "") or ""
        dev_id = fmt_dev_id(vid, pid)
        entry = {"Bus Type": "USB"}
        if dev_id:
            entry["Device ID"] = dev_id
        else:
            entry["Device ID"] = "0000-0000"
        bluetooth[key] = entry

    # -- Biometric --
    biometric = {}

    # -- SD Controller --
    sd = {}
    for item in pci_items:
        dtype = (item.get("sppci_device_type", "") or "").lower()
        if "sd" in dtype or "mmc" in dtype or "flash" in dtype:
            name = item.get("_name", "") or "SD Controller"
            entry = pci_device_entry(item)
            key = name.replace("/", "-") or "SD Controller"
            sd[key] = entry

    # -- System Devices --
    sys_devices = {}
    for item in pci_by_type.get("system", []):
        name = item.get("_name", "") or "Unknown"
        entry = pci_device_entry(item)
        entry["Device"] = name
        key = name.replace("/", "-") or f"Dev_{len(sys_devices)}"
        sys_devices[key] = entry

    return {
        "Motherboard": motherboard,
        "BIOS": bios,
        "CPU": cpu,
        "GPU": gpus,
        "Monitor": monitors,
        "Network": networks,
        "Sound": sounds,
        "USB Controllers": usb_controllers,
        "Input": inputs,
        "Storage Controllers": storages,
        "Biometric": biometric,
        "Bluetooth": bluetooth,
        "SD Controller": sd,
        "System Devices": sys_devices
    }


def main():
    parser = argparse.ArgumentParser(description="macOS Hardware Sniffer")
    parser.add_argument("-e", action="store_true", help="Export hardware report")
    parser.add_argument("-o", "--output", metavar="DIR", help="Output directory")
    args = parser.parse_args()
    if not args.e or not args.output:
        print("Usage: hardware_sniffer_mac.py -e -o <output_directory>")
        sys.exit(1)

    out_dir = args.output
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    report = collect_all()

    report_path = os.path.join(out_dir, "Report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=4)
    sys.exit(0)


if __name__ == "__main__":
    main()
