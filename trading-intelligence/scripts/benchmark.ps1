param([int]$Seconds = 10)
. "$PSScriptRoot\common.ps1"
if ($Seconds -lt 1 -or $Seconds -gt 60) { throw 'Seconds must be 1..60 per load level.' }
Push-Location $MeridianRoot
try {
  foreach ($rate in @(100,500,1000)) {
    & $MeridianPython benchmarks/run.py --events ($rate * $Seconds) --rate $rate --batch 16 --output "v11-$rate.json"
    Check-Exit "Benchmark $rate events/sec"
  }
} finally { Pop-Location }
