. "$PSScriptRoot\common.ps1"
& $MeridianPython (Join-Path $PSScriptRoot 'native_service.py') --stop
Check-Exit 'Graceful shutdown'
