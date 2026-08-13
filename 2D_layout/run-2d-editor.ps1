$ErrorActionPreference = 'Stop'
$appRoot = Join-Path $PSScriptRoot '2dlayoutMaker-main'
$python = Join-Path $appRoot '.venv\Scripts\python.exe'
$app = Join-Path $appRoot 'app.pyw'

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Python environment not found. Follow $appRoot\README.md first-time setup."
}
if (-not (Test-Path -LiteralPath $app -PathType Leaf)) {
    throw "Application entry point not found: $app"
}

Push-Location $appRoot
try {
    & $python $app
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
