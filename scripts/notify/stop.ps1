$ErrorActionPreference = 'Stop'
$notifyPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (Test-Path -LiteralPath $notifyPython) {
    & $notifyPython (Join-Path $PSScriptRoot 'bridge.py') --stop --url 'http://127.0.0.1:17654'
}
& docker compose -f (Join-Path $PSScriptRoot 'compose.yaml') stop
if ($LASTEXITCODE -ne 0) { throw 'Unable to stop the inbox.' }
Write-Output 'Stopped. Stored messages are preserved in the Docker volume.'
