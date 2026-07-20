import os
import subprocess
import shutil
import time
import sys
from datetime import datetime, timedelta
import configparser
from pathlib import Path
import argparse

DEFAULT_TSHARK_PATH = r"C:\Program Files\Wireshark\tshark.exe"

# Resolve config.ini next to the script/exe, not relative to the current working directory
BASE_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config.ini"

# === Parse command-line arguments ===
parser = argparse.ArgumentParser(description="Wireshark auto-capture script")
parser.add_argument("-D", "--list-interfaces", action="store_true",
                    help="List all network interfaces using tshark and exit")
parser.add_argument("-C", "--configure", action="store_true",
                    help="Configure capture settings (create config.ini if missing)")
args = parser.parse_args()

# === Function: list interfaces ===
def list_interfaces(tshark_path=DEFAULT_TSHARK_PATH):
    if not Path(tshark_path).exists():
        print(f"tshark not found at: {tshark_path}")
        sys.exit(1)
    print(f"\nListing interfaces using: {tshark_path}\n")
    result = subprocess.run([tshark_path, "-D"], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Failed to list interfaces:\n{result.stderr}")
        sys.exit(1)
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
        "retain_days": "0",
        "retain_log_days": "0",
        "base_folder": r"C:\captures",
        "tshark_path": DEFAULT_TSHARK_PATH
    }
    with open(CONFIG_FILE, "w") as f:
        config.write(f)
    print(f"\nConfig saved to {CONFIG_FILE} with interface {interface_selected}")
    print("Recommended settings:\n"
          f"duration = 300\n"
          f"retain_count = 0\n"
          f"retain_days = 0\n"
          f"retain_log_days = 0\n"
          f"base_folder = C:\\captures\n"
          f"tshark_path = {DEFAULT_TSHARK_PATH}")

# === Function: compress and remove day-folders older than retain_days ===
def prune_old_day_folders(base_folder: Path, retain_days: int):
    if retain_days <= 0:
        return
    cutoff_date = datetime.now().date() - timedelta(days=retain_days)
    for folder in base_folder.iterdir():
        if not folder.is_dir():
            continue
        try:
            folder_date = datetime.strptime(folder.name, "%Y%m%d").date()
        except ValueError:
            continue  # not a day-folder, skip
        if folder_date >= cutoff_date:
            continue
        archive_base = base_folder / folder.name
        try:
            shutil.make_archive(str(archive_base), "zip", root_dir=str(folder))
            shutil.rmtree(folder)
            print(f"Archived and removed old capture folder: {folder.name} -> {folder.name}.zip")
        except Exception as e:
            print(f"Failed to archive/remove folder {folder.name}: {e}")

# === Function: permanently delete day-folders/archives older than retain_log_days ===
def prune_expired_archives(base_folder: Path, retain_log_days: int):
    if retain_log_days <= 0:
        return
    cutoff_date = datetime.now().date() - timedelta(days=retain_log_days)
    for item in base_folder.iterdir():
        name = item.stem if item.is_file() and item.suffix.lower() == ".zip" else item.name
        try:
            item_date = datetime.strptime(name, "%Y%m%d").date()
        except ValueError:
            continue  # not a day-folder or day-archive, skip
        if item_date >= cutoff_date:
            continue
        try:
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
            print(f"Deleted expired capture data: {item.name} (older than {retain_log_days} days)")
        except Exception as e:
            print(f"Failed to delete expired capture data {item.name}: {e}")

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
retain_days = config.getint("CAPTURE", "retain_days", fallback=0)
retain_log_days = config.getint("CAPTURE", "retain_log_days", fallback=0)
base_folder = Path(config.get("CAPTURE", "base_folder"))
tshark_path = Path(config.get("CAPTURE", "tshark_path"))

if not tshark_path.exists():
    print(f"tshark not found at: {tshark_path}. Check tshark_path in {CONFIG_FILE}.")
    sys.exit(1)

if retain_log_days > 0 and retain_days > 0 and retain_log_days <= retain_days:
    print(f"Warning: retain_log_days ({retain_log_days}) should be greater than retain_days ({retain_days}), "
          "otherwise archives will be deleted before they'd ever be created.")

# === Ensure root folder exists ===
base_folder.mkdir(parents=True, exist_ok=True)
print(f"Starting Wireshark auto-capture. Captures will be saved in: {base_folder}")

while True:
    date_str = datetime.now().strftime("%Y%m%d")
    time_str = datetime.now().strftime("%H%M%S")

    day_folder = base_folder / date_str
    day_folder.mkdir(exist_ok=True)

    file_name = f"capture{date_str}_{time_str}.pcapng"
    file_path = day_folder / file_name

    print(f"Starting capture: {file_name}")

    result = subprocess.run([
        str(tshark_path),
        "-i", str(interface),
        "-a", f"duration:{duration}",
        "-w", str(file_path)
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Capture failed (exit code {result.returncode}): {result.stderr.strip()}")
        print("Waiting 10s before retrying...")
        time.sleep(10)
        continue

    # Retention (per-day file count)
    if retain_count > 0:
        files = sorted(day_folder.glob("capture*.pcapng"), key=os.path.getmtime)
        extra = len(files) - retain_count
        if extra > 0:
            for f in files[:extra]:
                f.unlink()
                print(f"Deleted old file: {f.name}")

    # Retention (day-folder age: compress then remove folders older than retain_days)
    prune_old_day_folders(base_folder, retain_days)

    # Retention (total lifetime: permanently delete raw/zip data older than retain_log_days)
    prune_expired_archives(base_folder, retain_log_days)

    time.sleep(2)
