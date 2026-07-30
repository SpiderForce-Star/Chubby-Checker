# Creates a Desktop shortcut for Chubby Checker (video -> access code -> main UI)
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $RepoRoot "tools\gui_launcher.py"))) {
    Write-Host "ERROR: gui_launcher.py not found under $RepoRoot"
    exit 1
}

$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "Chubby Checker.lnk"
$Target = Join-Path $RepoRoot "tools\ChubbyChecker.vbs"
$WorkDir = $RepoRoot
$IconCandidates = @(
    (Join-Path $RepoRoot "assets\branding\chubby_checker.ico"),
    (Join-Path $RepoRoot "assets\branding\ascent_logo.jpg")
)

if (-not (Test-Path $Target)) {
    Write-Host "ERROR: Launcher not found: $Target"
    exit 1
}

$Wsh = New-Object -ComObject WScript.Shell
$Sc = $Wsh.CreateShortcut($ShortcutPath)
$Sc.TargetPath = "wscript.exe"
$Sc.Arguments = "`"$Target`""
$Sc.WorkingDirectory = $WorkDir
$Sc.WindowStyle = 7
$Sc.Description = "Chubby Checker - Shipper vs Final Drawings (video, access code, main UI)"
foreach ($ico in $IconCandidates) {
    if (Test-Path $ico) {
        $Sc.IconLocation = "$ico,0"
        break
    }
}
$Sc.Save()

Write-Host "Desktop shortcut created:"
Write-Host "  $ShortcutPath"
Write-Host "Double-click 'Chubby Checker' on your Desktop to launch."
