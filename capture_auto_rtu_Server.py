import os
import subprocess
import time
import sys
from datetime import datetime
import configparser
from pathlib import Path
import argparse
import threading

from pymodbus.server import StartTcpServer
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext

CONFIG_FILE = "config.ini"
DEFAULT_TSHARK_PATH = r"C:\Program Files\Wireshark\tshark.exe"

# === Modbus server configuration ===
MODBUS_IP = "0.0.0.0"     # Listen on all network interfaces
MODBUS_PORT = 502

# Holding register addresses
HR_LIFE_COUNTER = 1
HR_INTERFACE = 2
HR_DURATION = 3        # minutes, 1-255
HR_RETAIN_COUNT = 4

# === Parse command-line arguments ===
parser = argparse.ArgumentParser(description="Wireshark auto-capture script with Modbus TCP server")
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
        "duration": "5",     # default 5 minutes
        "retain_count": "0",
        "base_folder": r"C:\captures",
        "tshark_path": DEFAULT_TSHARK_PATH
    }
    with open(CONFIG_FILE, "w") as f:
        config.write(f)
    print(f"\nConfig saved to {CONFIG_FILE} with interface {interface_selected}")
    print("Recommended settings:\n"
          f"duration = 5 (minutes)\n"
          f"retain_count = 0\n"
          f"base_folder = C:\\captures\n"
          f"tshark_path = {DEFAULT_TSHARK_PATH}")

# === Modbus datastore ===
store = ModbusSlaveContext(
    di=ModbusSequentialDataBlock(0, [False] * 10),
    co=ModbusSequentialDataBlock(0, [False] * 10),
    hr=ModbusSequentialDataBlock(0, [0] * 10),  # holding registers
    ir=ModbusSequentialDataBlock(0, [0] * 10),
)
context = ModbusServerContext(slaves=store, single=True)

# === Start Modbus server in background thread ===
def run_modbus_server():
    print(f"🟢 Starting Modbus TCP Server on {MODBUS_IP}:{MODBUS_PORT}")
    StartTcpServer(context, address=(MODBUS_IP, MODBUS_PORT))

modbus_thread = threading.Thread(target=run_modbus_server, daemon=True)
modbus_thread.start()

# === Mode: Configure (-C) ===
if args.configure:
    configure()
    sys.exit(0)

# === Mode: List interfaces (-D) ===
if args.list_interfaces:
    list_interfaces()
    sys.exit(0)

# === Load config.ini ===
if not os.path.exists(CONFIG_FILE):
    print(f"{CONFIG_FILE} not found. Run 'python capture_auto.py -C' first.")
    sys.exit(1)

config = configparser.ConfigParser()
config.read(CONFIG_FILE)
base_folder = Path(config.get("CAPTURE", "base_folder"))
tshark_path = Path(config.get("CAPTURE", "tshark_path"))

# Load initial settings from config.ini
interface = config.getint("CAPTURE", "interface")
duration = config.getint("CAPTURE", "duration")  # minutes
retain_count = config.getint("CAPTURE", "retain_count")

# Clamp duration to 1–255 minutes
duration = max(1, min(255, duration))

# Initialize Modbus holding registers
context[0x01].setValues(3, HR_INTERFACE-1, [interface, duration, retain_count])
context[0x01].setValues(3, HR_LIFE_COUNTER-1, [0])  # life counter

base_folder.mkdir(parents=True, exist_ok=True)
print(f"Starting Wireshark auto-capture. Captures will be saved in: {base_folder}")

# === Function: update running settings from Modbus HR ===
def update_settings_from_modbus():
    global interface, duration, retain_count
    # Read HR2–HR4
    hr_values = context[0x01].getValues(3, HR_INTERFACE-1, count=3)
    new_interface, new_duration, new_retain = hr_values

    # Clamp duration 1–255
    new_duration = max(1, min(255, new_duration))
    changed = False

    if new_interface != interface:
        interface = new_interface
        changed = True
    if new_duration != duration:
        duration = new_duration
        changed = True
    if new_retain != retain_count:
        retain_count = new_retain
        changed = True

    if changed:
        # Save back to config.ini
        config["CAPTURE"]["interface"] = str(interface)
        config["CAPTURE"]["duration"] = str(duration)
        config["CAPTURE"]["retain_count"] = str(retain_count)
        with open(CONFIG_FILE, "w") as f:
            config.write(f)
        print(f"💾 Settings updated from Modbus: interface={interface}, duration={duration} min, retain_count={retain_count}")

# === Life counter updater thread ===
def life_counter_loop():
    while True:
        val = context[0x01].getValues(3, HR_LIFE_COUNTER-1, count=1)[0]
        val = (val + 1) % 256  # loop 0-255
        context[0x01].setValues(3, HR_LIFE_COUNTER-1, [val])
        time.sleep(1)

threading.Thread(target=life_counter_loop, daemon=True).start()

# === Main capture loop ===
while True:
    date_str = datetime.now().strftime("%Y%m%d")
    time_str = datetime.now().strftime("%H%M")
    day_folder = base_folder / date_str
    day_folder.mkdir(exist_ok=True)
    file_name = f"capture{date_str}_{time_str}.pcapng"
    file_path = day_folder / file_name

    print(f"Starting capture: {file_name} (Interface {interface}, Duration {duration} min, Retain {retain_count})")

    # Convert duration from minutes to seconds for tshark
    duration_seconds = duration * 60

    # Start tshark capture
    subprocess.run([
        str(tshark_path),
        "-i", str(interface),
        "-a", f"duration:{duration_seconds}",
        "-w", str(file_path)
    ])

    # Update settings from Modbus if changed
    update_settings_from_modbus()

    # Retention logic
    if retain_count > 0:
        files = sorted(day_folder.glob("capture*.pcapng"), key=os.path.getmtime)
        extra = len(files) - retain_count
        if extra > 0:
            for f in files[:extra]:
                f.unlink()
                print(f"Deleted old file: {f.name}")

    time.sleep(2)
