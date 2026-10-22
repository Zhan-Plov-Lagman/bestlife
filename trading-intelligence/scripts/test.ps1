param([switch]$BackendOnly, [switch]$E2E)
. "$PSScriptRoot\common.ps1"
Assert-Tools -BackendOnly:$BackendOnly
Push-Location (Join-Path $MeridianRoot 'backend')
try {
  & $MeridianPython -m pytest -q "--basetemp=./.test-$([guid]::NewGuid().ToString('N'))"; Check-Exit 'pytest'
  & $MeridianPython -m ruff check app tests; Check-Exit 'Ruff'
  & $MeridianPython -m mypy app; Check-Exit 'mypy'
} finally { Pop-Location }
if (-not $BackendOnly) {
  Push-Location (Join-Path $MeridianRoot 'frontend')
  try {
    npm.cmd run typecheck; Check-Exit 'TypeScript'
    npm.cmd run test; Check-Exit 'Vitest'
    npm.cmd run build; Check-Exit 'Build'
    if ($E2E) { npm.cmd run e2e; Check-Exit 'Playwright (requires dev.ps1 running)' }
  } finally { Pop-Location }
}
