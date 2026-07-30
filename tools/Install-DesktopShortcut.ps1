# Creates a Desktop shortcut: "Ascent Chubby"
# Launch path: video -> access code (Twist1960) -> main UI (silent, no console)
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $RepoRoot "tools\gui_launcher.py"))) {
    Write-Host "ERROR: gui_launcher.py not found under $RepoRoot"
    exit 1
}

$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutName = "Ascent Chubby.lnk"
$ShortcutPath = Join-Path $Desktop $ShortcutName
$Target = Join-Path $RepoRoot "tools\ChubbyChecker.vbs"
$WorkDir = $RepoRoot

# Prefer multi-size Ascent Chubby .ico; fall back to logo image if needed
$IconCandidates = @(
    (Join-Path $RepoRoot "assets\branding\ascent_chubby.ico"),
    (Join-Path $RepoRoot "assets\branding\chubby_checker.ico"),
    (Join-Path $RepoRoot "assets\branding\ascent_shipper_checker.ico"),
    (Join-Path $RepoRoot "assets\branding\ascent_logo.jpg")
)

if (-not (Test-Path $Target)) {
    Write-Host "ERROR: Silent launcher not found: $Target"
    exit 1
}

# Remove previous shortcut name if present (rename from Chubby Checker)
$LegacyShortcut = Join-Path $Desktop "Chubby Checker.lnk"
if (Test-Path $LegacyShortcut) {
    Remove-Item -LiteralPath $LegacyShortcut -Force
    Write-Host "Removed legacy shortcut: $LegacyShortcut"
}

$Wsh = New-Object -ComObject WScript.Shell
$Sc = $Wsh.CreateShortcut($ShortcutPath)
# wscript.exe + .vbs = no Command Prompt window
$Sc.TargetPath = "wscript.exe"
$Sc.Arguments = "//B `"$Target`""
$Sc.WorkingDirectory = $WorkDir
$Sc.WindowStyle = 7
$Sc.Description = "Ascent Chubby (Chubby Checker) - Shipper vs Final Drawings. Video, access code, main UI."

$iconUsed = $null
foreach ($ico in $IconCandidates) {
    if (Test-Path $ico) {
        $Sc.IconLocation = "$ico,0"
        $iconUsed = $ico
        break
    }
}
$Sc.Save()

Write-Host "Desktop shortcut created:"
Write-Host "  $ShortcutPath"
if ($iconUsed) {
    Write-Host "  Icon: $iconUsed"
} else {
    Write-Host "  Icon: (system default - place assets/branding/ascent_chubby.ico)"
}
Write-Host "Double-click 'Ascent Chubby' on your Desktop to launch (no Command Prompt)."
