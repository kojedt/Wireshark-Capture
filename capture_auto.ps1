# ==============================
# Wireshark Auto Capture Script
# ==============================

# === Configuration ===
$interface = 8                     # Your network interface index (use 'tshark -D' to list)
$duration = 300                    # Capture duration in seconds (5 minutes)
$retainCount = 0                   # Keep all files (no deletion)
$baseFolder = "C:\captures"        # Root folder for captures
$tsharkPath = "C:\Program Files\Wireshark\tshark.exe"  # Full path to tshark.exe

# === Create root folder if missing ===
if (!(Test-Path $baseFolder)) {
    New-Item -ItemType Directory -Path $baseFolder | Out-Null
}

while ($true) {
    # === Get current date/time ===
    $date = Get-Date -Format "yyyyMMdd"
    $time = Get-Date -Format "HHmm"

    # === Create daily folder ===
    $dayFolder = Join-Path $baseFolder $date
    if (!(Test-Path $dayFolder)) {
        New-Item -ItemType Directory -Path $dayFolder | Out-Null
        Write-Host "Created new folder for $date"
    }

    # === File name ===
    $fileName = "capture${date}_$time.pcapng"
    $filePath = Join-Path $dayFolder $fileName

    # === Start capture ===
    Write-Host "Starting capture: $fileName"
    & "$tsharkPath" -i $interface -a duration:$duration -w "$filePath"

    # === Retention (only if $retainCount > 0) ===
    if ($retainCount -gt 0) {
        $files = Get-ChildItem $dayFolder -Filter "capture*.pcapng" | Sort-Object LastWriteTime
        $extraFiles = $files.Count - $retainCount
        if ($extraFiles -gt 0) {
            $filesToDelete = $files | Select-Object -First $extraFiles
            foreach ($f in $filesToDelete) {
                Remove-Item $f.FullName -Force
                Write-Host "Deleted old file: $($f.Name)"
            }
        }
    }

    # === Wait before next capture cycle ===
    Start-Sleep -Seconds 2
}
