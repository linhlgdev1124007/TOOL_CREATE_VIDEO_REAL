param(
    [switch]$InstallPrerequisites,
    [switch]$WithFlowkit
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User') + ';' + $env:Path
}
function Require-Tool([string]$command, [string]$package) {
    if (Get-Command $command -ErrorAction SilentlyContinue) { return }
    if (-not $InstallPrerequisites) { throw "Missing $command. Run bootstrap.ps1 -InstallPrerequisites or install $package manually." }
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { throw 'Install Microsoft App Installer (winget), reopen PowerShell, then rerun.' }
    & winget install --id $package --exact --source winget --accept-package-agreements --accept-source-agreements --disable-interactivity
    if ($LASTEXITCODE -ne 0) { throw "winget failed for $package. Inspect installer output; do not bypass UAC or policy." }
    Refresh-Path
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) { throw "$package installed but $command not on PATH. Reopen PowerShell and rerun." }
}
Require-Tool 'git' 'Git.Git'
Require-Tool 'ffmpeg' 'Gyan.FFmpeg'
Require-Tool 'ffprobe' 'Gyan.FFmpeg'
Require-Tool 'bun' 'Oven-sh.Bun'

# Use the Python minor version tested with the pinned native wheels.
$pythonCandidates = @('python', (Join-Path $env:LOCALAPPDATA 'Programs/Python/Python313/python.exe'))
function Find-Python313 {
    foreach ($candidate in $pythonCandidates) {
        if (Get-Command $candidate -ErrorAction SilentlyContinue) {
            $version = & $candidate -c 'import sys; print(sys.version_info.major, sys.version_info.minor)' 2>$null
            if ($LASTEXITCODE -eq 0 -and $version -eq '3 13') { return $candidate }
        }
    }
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $candidate = & py -3.13 -c 'import sys; print(sys.executable)' 2>$null
        if ($LASTEXITCODE -eq 0 -and $candidate) { return $candidate }
    }
    return $null
}
$pythonExe = Find-Python313
if (-not $pythonExe -and $InstallPrerequisites) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { throw 'winget required to install Python 3.13' }
    & winget install --id Python.Python.3.13 --exact --source winget --accept-package-agreements --accept-source-agreements --disable-interactivity
    if ($LASTEXITCODE -ne 0) { throw 'Python installation failed' }
    Refresh-Path
    $pythonExe = Find-Python313
}
if (-not $pythonExe) { throw 'Python 3.13 not found. Install it, reopen PowerShell and rerun.' }
& (Join-Path $PSScriptRoot 'setup-wrydeco-reels.ps1') -PythonExe $pythonExe
if ($WithFlowkit) {
    & (Join-Path $PSScriptRoot 'setup-flowkit.ps1') -PythonExe $pythonExe
    Write-Output 'Human step: install Chrome if missing, sign in to Google Flow, and load integrations/flowkit/extension via chrome://extensions.'
}
& (Join-Path $root '.venv-reels/Scripts/python.exe') (Join-Path $PSScriptRoot 'doctor.py')
if ($LASTEXITCODE -ne 0) { throw 'Installation verification failed; see doctor output' }
