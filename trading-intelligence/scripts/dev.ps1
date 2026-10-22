param([switch]$BackendOnly)
. "$PSScriptRoot\common.ps1"
Assert-Tools -BackendOnly:$BackendOnly
if (-not (Test-Path -LiteralPath $MeridianPython)) { throw 'Run scripts/setup.ps1 first.' }
$runDirectory = Join-Path $MeridianRoot '.run'
New-Item -ItemType Directory -Force -Path $runDirectory | Out-Null
Push-Location (Join-Path $MeridianRoot 'backend')
try { & $MeridianPython -m alembic upgrade head; Check-Exit 'Migration' } finally { Pop-Location }
$arguments = @(('"' + (Join-Path $PSScriptRoot 'native_service.py') + '"'))
if ($BackendOnly) { $arguments += '--backend-only' }
$service = Start-Process -FilePath $MeridianPython -ArgumentList $arguments -WorkingDirectory $MeridianRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runDirectory 'backend.log') -RedirectStandardError (Join-Path $runDirectory 'backend-error.log') -PassThru
Start-Sleep -Seconds 2
if ($service.HasExited) { throw 'Backend did not start. See .run/backend-error.log (another instance may own the database).' }
Write-Output 'Meridian started on 127.0.0.1:8000. Stop with scripts/stop.ps1.'
if (-not $BackendOnly) { Write-Output 'UI: http://127.0.0.1:3000' }
