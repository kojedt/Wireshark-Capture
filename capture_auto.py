import os
import subprocess
import time
import sys
from datetime import datetime
import configparser
from pathlib import Path
import argparse

CONFIG_FILE = "config.ini"
DEFAULT_TSHARK_PATH = r"C:\Program Files\Wireshark\tshark.exe"

# === Parse command-line arguments ===
parser = argparse.ArgumentParser(description="Wireshark auto-capture script")
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
    # Let user select
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
    
    # Write config.ini
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

# === Load config.ini ===
config = configparser.ConfigParser()
config.read(CONFIG_FILE)
interface = config.getint("CAPTURE", "interface")
duration = config.getint("CAPTURE", "duration")
retain_count = config.getint("CAPTURE", "retain_count")
base_folder = Path(config.get("CAPTURE", "base_folder"))
tshark_path = Path(config.get("CAPTURE", "tshark_path"))

# === Ensure root folder exists ===
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

    # Retention
    if retain_count > 0:
        files = sorted(day_folder.glob("capture*.pcapng"), key=os.path.getmtime)
        extra = len(files) - retain_count
        if extra > 0:
            for f in files[:extra]:
                f.unlink()
                print(f"Deleted old file: {f.name}")

    time.sleep(2)
