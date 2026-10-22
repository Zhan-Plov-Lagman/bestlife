param([switch]$BackendOnly)
# Compatibility entry point; owned launcher provides graceful shutdown.
& "$PSScriptRoot\dev.ps1" -BackendOnly:$BackendOnly
