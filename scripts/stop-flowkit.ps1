param([Parameter(Mandatory=$true)][string]$Job)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$jobPath = [IO.Path]::GetFullPath((Join-Path $root $Job))
$outputRoot = [IO.Path]::GetFullPath((Join-Path $root 'output')) + [IO.Path]::DirectorySeparatorChar
if (-not $jobPath.StartsWith($outputRoot,[StringComparison]::OrdinalIgnoreCase)) { throw 'Job must be inside output/' }
$recordPath = Join-Path $jobPath 'flowkit-process.json'
$record = Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json
$owned = Get-Process -Id $record.pid -ErrorAction SilentlyContinue
if ($owned) {
    $started = $owned.StartTime.ToUniversalTime().ToString('o')
    if ($started -ne $record.started) { throw 'PID was reused; refusing to stop another process' }
    $details = Get-CimInstance Win32_Process -Filter "ProcessId=$($record.pid)"
    if ($details.CommandLine -notlike '*reels/flowkit_server.py*') { throw 'Process is not the owned Flowkit launcher' }
    & taskkill /PID $record.pid /T /F
    if ($LASTEXITCODE -ne 0) { throw 'Flowkit process tree did not stop' }
}
Write-Output 'Owned Flowkit server stopped; Chrome and its extension remain open.'
