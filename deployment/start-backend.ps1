$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'hardware.ps1')
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    & $env:SMARTWEAR_AI_PYTHON -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
    if ($LASTEXITCODE -ne 0) { throw 'Backend failed' }
} finally { Pop-Location }
