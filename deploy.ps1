$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

if (-not (Test-Path ".env")) {
    .\setup.ps1
}

python -m unittest discover -p "test*.py"

if ($LASTEXITCODE -ne 0) {
    throw "Falha na suíte de testes."
}

if (-not (Get-Command vercel -ErrorAction SilentlyContinue)) {
    Write-Host "Vercel CLI não encontrada. Instalando..."
    npm i -g vercel
}

vercel --prod
