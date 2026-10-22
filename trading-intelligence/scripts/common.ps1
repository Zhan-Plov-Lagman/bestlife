$ErrorActionPreference = 'Stop'
$MeridianRoot = Split-Path -Parent $PSScriptRoot
$MeridianPython = Join-Path $MeridianRoot '.venv\Scripts\python.exe'
function Assert-Tools([switch]$BackendOnly) {
  if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw 'Python 3.12+ is required.' }
  python -c 'import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)'
  if ($LASTEXITCODE -ne 0) { throw 'Python 3.12+ is required.' }
  if (-not $BackendOnly) {
    if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw 'Node.js 20.9+ is required.' }
    node -e 'const [a,b]=process.versions.node.split(".").map(Number);process.exit(a>20||(a===20&&b>=9)?0:1)'
    if ($LASTEXITCODE -ne 0) { throw 'Node.js 20.9+ is required.' }
  }
}
function Check-Exit([string]$Step) { if ($LASTEXITCODE -ne 0) { throw "$Step failed (exit $LASTEXITCODE)" } }
