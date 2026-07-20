# Build & Setup Notes

## 1. Find your interface number

```
"C:\Program Files\Wireshark\tshark.exe" -D
```

Example output:

```
1. \Device\NPF_{D303B069-1D64-49AB-AAAD-944C2A213C9C} (Local Area Connection* 8)
2. \Device\NPF_{46AEC726-F10F-47F0-BB26-84C179B920FC} (Local Area Connection* 7)
3. \Device\NPF_{87B82E50-673A-4AF6-BB69-2C979023BCA5} (Local Area Connection* 6)
4. \Device\NPF_{FB9FF667-F885-4175-9A98-16651E95160E} (Bluetooth Network Connection)
5. \Device\NPF_{6FF72D1D-8515-4EF8-B6BB-6B87088050B7} (Wi-Fi)
6. \Device\NPF_{20AE65D4-15D5-4F57-AE3F-BD0EA11DC278} (Local Area Connection* 10)
7. \Device\NPF_{7A234687-C019-4C8F-A372-09F1935EB0E7} (Local Area Connection* 9)
8. \Device\NPF_{E18ADC18-A5AD-46DA-A42F-D57D0C90EBCD} (Ethernet)
9. \Device\NPF_{5B4FC98C-05DE-4BD7-BEA6-436A7E185BD9} (Ethernet 4)
10. \Device\NPF_Loopback (Adapter for loopback traffic capture)
11. etwdump (Event Tracing for Windows (ETW) reader)
```

The interface number (leftmost column) is what goes into `config.ini`'s `interface` key.

## 2. Set paths and parameters

If using `capture_auto.ps1` instead of the Python script, edit these values directly at the top of the file:

```powershell
$tsharkPath = "C:\Program Files\Wireshark\tshark.exe"
$outputFolder = "C:\Users\ARSIGCOMMgr\Desktop\captures"
$interface = 8         # Change this to your interface number
$duration = 5*60       # 5 minutes (in seconds)
$retainCount = 10      # Keep only the last 10 captures
```

Note: `capture_auto.ps1` does not support `retain_days`/`retain_log_days` — that logic only exists in `capture_auto.py`.

## 3. Build the standalone executable

Requires `pyinstaller` (`pip install pyinstaller`):

```
pyinstaller --onefile --name capture_auto capture_auto.py
```

This produces `dist\capture_auto.exe`. A prebuilt copy (plus its own `config.ini`) already lives in `cap\`.

## 4. Running

- Must run as **Administrator** — Npcap/WinPcap requires elevated privileges to capture packets.
- On first run with no `config.ini`, run with `-C` to generate one interactively.
