param([switch]$LoginStartup)
$ErrorActionPreference = 'Stop'
$notifyDir = $PSScriptRoot
$notifyPython = Join-Path $notifyDir '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $notifyPython)) {
    & python -m venv (Join-Path $notifyDir '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Unable to create the Windows bridge virtual environment.' }
}
& $notifyPython -c "import importlib.util, sys; sys.exit(importlib.util.find_spec('windows_toasts') is None)"
if ($LASTEXITCODE -ne 0) {
    & $notifyPython -m pip --isolated install --no-user -r (Join-Path $notifyDir 'requirements-windows.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Unable to install Windows notification dependencies.' }
}
& docker compose -f (Join-Path $notifyDir 'compose.yaml') up -d --build --wait
if ($LASTEXITCODE -ne 0) { throw 'Unable to start the inbox. Check Docker Desktop and port 17654.' }
& $notifyPython (Join-Path $notifyDir 'bridge.py') --background --url 'http://127.0.0.1:17654'
if ($LASTEXITCODE -ne 0) { throw 'Unable to launch the Windows bridge.' }

$notifyReady = $false
for ($attempt = 0; $attempt -lt 20; $attempt++) {
    $notifyHealth = Invoke-RestMethod -Uri 'http://127.0.0.1:17654/health' -TimeoutSec 3
    if ($notifyHealth.bridge_connected) { $notifyReady = $true; break }
    Start-Sleep -Milliseconds 500
}
if (-not $notifyReady) { throw 'Desktop bridge did not connect. Check %LOCALAPPDATA%\AOPCNotify logs.' }

if ($LoginStartup) {
    $notifyShell = New-Object -ComObject WScript.Shell
    $notifyShortcut = $notifyShell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Startup')) 'AOPC Notify.lnk'))
    $notifyShortcut.TargetPath = $notifyPython
    $notifyShortcut.Arguments = '"' + (Join-Path $notifyDir 'bridge.py') + '" --background --url http://127.0.0.1:17654'
    $notifyShortcut.WorkingDirectory = $notifyDir
    $notifyShortcut.WindowStyle = 7
    $notifyShortcut.Save()
    Write-Output 'Windows bridge will also start at login. Keep this checkout at its current path.'
}
Write-Output 'AOPC Notify is running: http://127.0.0.1:17654'
