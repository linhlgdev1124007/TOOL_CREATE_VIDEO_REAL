param(
    [Parameter(Mandatory=$true)][string]$ProjectId,
    [Parameter(Mandatory=$true)][string]$Job
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$jobPath = [IO.Path]::GetFullPath((Join-Path $root $Job))
$outputRoot = [IO.Path]::GetFullPath((Join-Path $root 'output')) + [IO.Path]::DirectorySeparatorChar
if (-not $jobPath.StartsWith($outputRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Job must be inside output/' }
foreach ($port in @(8100,9222)) {
    if (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue) { throw "Port $port is occupied; not terminating its owner." }
}
New-Item -ItemType Directory -Force -Path $jobPath | Out-Null
$runtime = Join-Path $root '.venv-flowkit/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $runtime)) { throw 'Run setup-flowkit.ps1 first' }
$process = Start-Process -FilePath $runtime -ArgumentList @('reels/flowkit_server.py','--job',('"'+$jobPath+'"'),'--project-id',$ProjectId) -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $jobPath 'flowkit.stdout.log') -RedirectStandardError (Join-Path $jobPath 'flowkit.stderr.log')
@{pid=$process.Id; project_id=$ProjectId; job=$jobPath; started=$process.StartTime.ToUniversalTime().ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $jobPath 'flowkit-process.json')
Write-Output "Flowkit PID $($process.Id). Load integrations/flowkit/extension in Chrome and leave the signed-in Flow project open."
