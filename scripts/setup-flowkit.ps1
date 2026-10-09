param([string]$PythonExe = 'python')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$pin = 'bc051f2308db050b0d987b696c843664d483b515'
$vendor = Join-Path $root 'integrations/flowkit'
if (-not (Test-Path -LiteralPath $vendor)) {
    & git clone https://github.com/crisng95/flowkit.git $vendor
    if ($LASTEXITCODE -ne 0) { throw 'Flowkit clone failed' }
    & git -C $vendor checkout --detach $pin
}
$actual = & git -C $vendor rev-parse HEAD
if ($actual -ne $pin) { throw 'Existing Flowkit checkout differs; preserve it and inspect before updating.' }
$runtime = Join-Path $root '.venv-flowkit/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $runtime)) {
    & $PythonExe -m venv (Join-Path $root '.venv-flowkit')
    if ($LASTEXITCODE -ne 0) { throw 'Could not create Flowkit environment' }
}
$env:PIP_CACHE_DIR = Join-Path $root '.cache/pip'
& $runtime -m pip install -r (Join-Path $root 'reels/flowkit-requirements.lock')
if ($LASTEXITCODE -ne 0) { throw 'Flowkit dependencies failed' }
Write-Output 'Flowkit ready. Start with scripts/start-flowkit.ps1 -ProjectId <uuid> -Job output/<job>.'
