param([switch]$BackendOnly)
. "$PSScriptRoot\common.ps1"
Assert-Tools -BackendOnly:$BackendOnly
Push-Location $MeridianRoot
try {
  if (-not (Test-Path -LiteralPath $MeridianPython)) { python -m venv .venv; Check-Exit 'Create virtual environment' }
  python -m pip --python $MeridianPython install -r backend/requirements.lock.txt
  Check-Exit 'Install Python dependencies'
  Push-Location backend
  try { & $MeridianPython -m alembic upgrade head; Check-Exit 'Database migration' } finally { Pop-Location }
  if (-not $BackendOnly) {
    Push-Location frontend
    try { npm.cmd ci; Check-Exit 'Install frontend'; npm.cmd run build; Check-Exit 'Build frontend' } finally { Pop-Location }
  }
} finally { Pop-Location }
