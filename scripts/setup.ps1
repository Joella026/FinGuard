param(
    [switch]$Dev
)

$ErrorActionPreference = "Stop"
$candidate = Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python*\python.exe" -ErrorAction SilentlyContinue |
    Sort-Object FullName -Descending |
    Select-Object -First 1 -ExpandProperty FullName

if (-not $candidate) {
    throw "Python 3.11 or later was not found. Install Python and retry."
}

& $candidate -m ensurepip --upgrade
& $candidate -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip

$requirement = ".\backend"
if ($Dev) { $requirement = ".\backend[dev]" }
& .\.venv\Scripts\python.exe -m pip install -e $requirement

Push-Location .\frontend
npm install
npm run build
Pop-Location

if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    Write-Host "Created .env. Add OPENAI_API_KEY to enable GPT narratives."
}

Write-Host "Setup complete. Run: .\scripts\start.ps1"

