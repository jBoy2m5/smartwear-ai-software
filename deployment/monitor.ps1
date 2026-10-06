param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('smartwrist', 'smartcap')]
    [string]$Device
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$env:PLATFORMIO_CORE_DIR = Join-Path $projectRoot '.platformio'
$env:PYTHONIOENCODING = 'utf-8'
Push-Location $projectRoot
try {
    & '.\.venv\Scripts\python.exe' -m platformio device monitor -d firmware -e $Device
} finally { Pop-Location }
