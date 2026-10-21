$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Create .venv and install dependencies first. See README.md.' }
Push-Location (Join-Path $projectRoot 'backend')
try {
  & $pythonPath -m alembic upgrade head
  if ($LASTEXITCODE -ne 0) { throw 'Migration failed' }
  $backend = Start-Process -FilePath $pythonPath -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000','--workers','1') -WorkingDirectory (Join-Path $projectRoot 'backend') -WindowStyle Hidden -PassThru
} finally { Pop-Location }
try {
  Push-Location (Join-Path $projectRoot 'frontend')
  npm.cmd run start
} finally {
  Pop-Location
  if ($backend -and -not $backend.HasExited) { Stop-Process -Id $backend.Id }
}
