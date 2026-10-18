$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    throw "Python environment not found. Run .\scripts\setup.ps1 -Dev first."
}

if (-not (Test-Path ".\frontend\dist\index.html")) {
    Push-Location ".\frontend"
    if (-not (Test-Path ".\node_modules")) {
        npm install
    }
    npm run build
    Pop-Location
}

Write-Host "FinGuard: http://127.0.0.1:8000"
Write-Host "API docs: http://127.0.0.1:8000/docs"
& ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
