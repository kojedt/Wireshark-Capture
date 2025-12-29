import os
import subprocess
import time
import sys
from datetime import datetime
import configparser
from pathlib import Path
import argparse
from pymodbus.client import ModbusTcpClient  # 👈 Add Modbus support

CONFIG_FILE = "config.ini"
DEFAULT_TSHARK_PATH = r"C:\Program Files\Wireshark\tshark.exe"

# Modbus settings (change as needed)
MODBUS_IP = "192.168.1.100"   # 👈 your Modbus server IP
MODBUS_PORT = 502
MODBUS_COIL = 1

# === Parse command-line arguments ===
parser = argparse.ArgumentParser(description="Wireshark auto-capture script with Modbus health check")
parser.add_argument("-D", "--list-interfaces", action="store_true",
                    help="List all network interfaces using tshark and exit")
parser.add_argument("-C", "--configure", action="store_true",
                    help="Configure capture settings (create config.ini if missing)")
args = parser.parse_args()

# === Function: list interfaces ===
def list_interfaces(tshark_path=DEFAULT_TSHARK_PATH):
    print(f"\nListing interfaces using: {tshark_path}\n")
    result = subprocess.run([tshark_path, "-D"], capture_output=True, text=True)
    print(result.stdout)
    return result.stdout.strip().splitlines()

# === Function: configure and write config.ini ===
def configure():
    interfaces = list_interfaces()
    while True:
        try:
            choice = int(input("\nSelect interface number: "))
            if 1 <= choice <= len(interfaces):
                interface_selected = choice
                break
            else:
                print("Invalid selection. Try again.")
        except ValueError:
            print("Enter a number corresponding to the interface.")
    
    config = configparser.ConfigParser()
    config["CAPTURE"] = {
        "interface": str(interface_selected),
        "duration": "300",
        "retain_count": "0",
        "base_folder": r"C:\captures",
        "tshark_path": DEFAULT_TSHARK_PATH
    }
    with open(CONFIG_FILE, "w") as f:
        config.write(f)
    print(f"\nConfig saved to {CONFIG_FILE} with interface {interface_selected}")
    print("Recommended settings:\n"
          f"duration = 300\n"
          f"retain_count = 0\n"
          f"base_folder = C:\\captures\n"
          f"tshark_path = {DEFAULT_TSHARK_PATH}")

# === Function: Modbus TCP check ===
def check_modbus(ip=MODBUS_IP, port=MODBUS_PORT, coil=MODBUS_COIL):
    try:
        client = ModbusTcpClient(ip, port=port, timeout=2)
        client.connect()
        rr = client.read_coils(coil - 1, 1)  # coils start at 0
        client.close()
        if rr.isError():
            print(f"❌ Modbus error reading coil {coil}")
            return False
        else:
            print(f"✅ Modbus OK - Coil {coil} = {rr.bits[0]}")
            return True
    except Exception as e:
        print(f"❌ Modbus check failed: {e}")
        return False

# === Mode: Configure (-C) ===
if args.configure:
    configure()
    sys.exit(0)

# === Mode: List interfaces (-D) ===
if args.list_interfaces:
    list_interfaces()
    sys.exit(0)

# === Default: Run capture ===
if not os.path.exists(CONFIG_FILE):
    print(f"{CONFIG_FILE} not found. Run 'python capture_auto.py -C' to create configuration.")
    sys.exit(1)

config = configparser.ConfigParser()
config.read(CONFIG_FILE)
interface = config.getint("CAPTURE", "interface")
duration = config.getint("CAPTURE", "duration")
retain_count = config.getint("CAPTURE", "retain_count")
base_folder = Path(config.get("CAPTURE", "base_folder"))
tshark_path = Path(config.get("CAPTURE", "tshark_path"))

base_folder.mkdir(parents=True, exist_ok=True)
print(f"Starting Wireshark auto-capture. Captures will be saved in: {base_folder}")

while True:
    date_str = datetime.now().strftime("%Y%m%d")
    time_str = datetime.now().strftime("%H%M")

    day_folder = base_folder / date_str
    day_folder.mkdir(exist_ok=True)

    file_name = f"capture{date_str}_{time_str}.pcapng"
    file_path = day_folder / file_name

    print(f"Starting capture: {file_name}")

    subprocess.run([
        str(tshark_path),
        "-i", str(interface),
        "-a", f"duration:{duration}",
        "-w", str(file_path)
    ])

    # 🧩 Modbus health check
    check_modbus()

    # Retention
    if retain_count > 0:
        files = sorted(day_folder.glob("capture*.pcapng"), key=os.path.getmtime)
        extra = len(files) - retain_count
        if extra > 0:
            for f in files[:extra]:
                f.unlink()
                print(f"Deleted old file: {f.name}")

    time.sleep(2)
