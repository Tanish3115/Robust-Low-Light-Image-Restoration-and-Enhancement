param([ValidateSet('backend','frontend','test')][string]$Target='backend')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    if ($Target -eq 'frontend') {
        Push-Location -LiteralPath (Join-Path $projectRoot 'frontend')
        try { npm run dev } finally { Pop-Location }
    } elseif ($Target -eq 'test') {
        & (Join-Path $projectRoot '.venv\Scripts\python.exe') -m pytest
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        Push-Location -LiteralPath (Join-Path $projectRoot 'frontend')
        try { npm test; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; npm run build } finally { Pop-Location }
    } else {
        & (Join-Path $projectRoot '.venv\Scripts\python.exe') -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
    }
} finally { Pop-Location }
