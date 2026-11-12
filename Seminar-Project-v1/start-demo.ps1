param([int]$Port = 8000)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$demoPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $demoPython)) {
    throw 'Create .venv and install requirements.txt first. See DAY1.md.'
}
& $demoPython -m scripts.local_demo start
if ($LASTEXITCODE -ne 0) { throw 'Could not start demo database.' }
Write-Host "Demo: http://127.0.0.1:$Port/"
Write-Host "API docs: http://127.0.0.1:$Port/docs"
$demoHealth = $null
try {
    $demoHealth = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 2
} catch { }
$demoPresentation = $null
try {
    $demoPresentation = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/demo/info" -TimeoutSec 2
} catch { }
if ($demoPresentation.presentation_version -eq '1.1' -and $demoHealth.ok) {
    Write-Host 'The presentation demo is already running.'
    return
}
if ($demoHealth.ok) {
    throw 'An older demo API is running on this port. Stop that API and run this script again.'
}
& $demoPython -m uvicorn demo_dashboard:app --host 127.0.0.1 --port $Port
