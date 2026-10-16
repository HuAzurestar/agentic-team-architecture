param(
    [ValidateSet('Start', 'Stop')]
    [string]$Action = 'Start',
    [switch]$NoOpen
)
$ErrorActionPreference = 'Stop'
$memoryPort = if ($env:AGENTMEMORY_SEARCH_PORT) { [int]$env:AGENTMEMORY_SEARCH_PORT } else { 3120 }
if ($memoryPort -lt 1 -or $memoryPort -gt 65535) { throw 'Invalid AGENTMEMORY_SEARCH_PORT.' }
$memoryUrl = "http://127.0.0.1:$memoryPort"
$memoryRuntime = Join-Path $PSScriptRoot '.runtime'
$memoryPidFile = Join-Path $memoryRuntime "server-$memoryPort.pid"
$memoryServerFile = Join-Path $PSScriptRoot 'server.mjs'

function Test-MemorySearch {
    try {
        $memoryHealth = Invoke-RestMethod -Uri "$memoryUrl/api/health" -TimeoutSec 2
        return $memoryHealth.app -eq 'agentmemory-search-local' -and $memoryHealth.status -eq 'ok'
    } catch { return $false }
}

if ($Action -eq 'Stop') {
    if (!(Test-Path -LiteralPath $memoryPidFile)) {
        Write-Host 'No background server started by this launcher.'
        exit 0
    }
    $memoryProcessId = [int](Get-Content -LiteralPath $memoryPidFile -Raw).Trim()
    $memoryProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $memoryProcessId"
    if (!$memoryProcess) { Write-Host 'Search server is already stopped.'; exit 0 }
    if ($memoryProcess.Name -ne 'node.exe' -or $memoryProcess.CommandLine -notmatch [regex]::Escape($memoryServerFile)) {
        throw 'PID belongs to a different process; refusing to stop it.'
    }
    Stop-Process -Id $memoryProcessId
    Write-Host 'Agent Memory search stopped.'
    exit 0
}

if (!(Test-MemorySearch)) {
    $memoryNode = (Get-Command node -ErrorAction Stop).Source
    New-Item -ItemType Directory -Path $memoryRuntime -Force | Out-Null
    $memoryChild = Start-Process -FilePath $memoryNode -ArgumentList ('"' + $memoryServerFile + '"') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $memoryRuntime "server-$memoryPort.log") -RedirectStandardError (Join-Path $memoryRuntime "server-$memoryPort.error.log")
    Set-Content -LiteralPath $memoryPidFile -Value $memoryChild.Id -Encoding ascii
    $memoryReady = $false
    for ($memoryAttempt = 0; $memoryAttempt -lt 15; $memoryAttempt++) {
        if (Test-MemorySearch) { $memoryReady = $true; break }
        if ($memoryChild.HasExited) { break }
        Start-Sleep -Milliseconds 200
    }
    if (!$memoryReady) { throw "Search server could not start. Check $memoryRuntime\server-$memoryPort.error.log" }
}
Write-Host "Agent Memory search: $memoryUrl"
Write-Host 'Running in the background. Use stop.cmd to stop it.'
if (!$NoOpen) { Start-Process $memoryUrl }
