param([string]$PythonExe = 'python')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$runtime = Join-Path $root '.venv-reels\Scripts\python.exe'
$env:TEMP = Join-Path $root '.tmp'
$env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = Join-Path $root '.cache\pip'
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $root '.cache\ms-playwright'
$env:BUN_INSTALL_CACHE_DIR = Join-Path $root '.cache\bun'
New-Item -ItemType Directory -Force -Path $env:TEMP, $env:PIP_CACHE_DIR | Out-Null
foreach ($tool in @($PythonExe,'ffmpeg','ffprobe','bun','git')) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { throw "Missing prerequisite: $tool" }
}
& $PythonExe (Join-Path $root 'scripts/restore-dependencies.py')
if ($LASTEXITCODE -ne 0) { throw 'Pinned dependency restoration failed' }
if (-not (Test-Path -LiteralPath $runtime)) {
    & $PythonExe -m venv (Join-Path $root '.venv-reels')
    if ($LASTEXITCODE -ne 0) { throw 'Could not create Python environment' }
}
& $runtime -m pip install -r (Join-Path $root 'reels\requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
foreach ($repo in @('opencut-classic','opencut-mcp')) {
        Push-Location (Join-Path $root $repo)
        try {
            & bun install --frozen-lockfile
            if ($LASTEXITCODE -ne 0) { throw "Dependencies failed: $repo" }
        } finally { Pop-Location }
}
Push-Location (Join-Path $root 'opencut-mcp')
try {
    & bunx playwright install chromium --only-shell
    if ($LASTEXITCODE -ne 0) { throw 'Chromium setup failed' }
} finally { Pop-Location }
& $runtime (Join-Path $root 'reels\bootstrap.py')
if ($LASTEXITCODE -ne 0) { throw 'Model/audio setup failed; inspect output and retry' }
Write-Output 'Wrydeco Reels dependencies and audio library ready.'
