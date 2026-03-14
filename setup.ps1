$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python não encontrado no PATH."
}

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if (-not (Test-Path ".env")) {
    @"
ABACATE_PAY_TOKEN=
API_TIMEOUT=30
RETURN_URL=http://localhost:5500/success
COMPLETION_URL=http://localhost:5500/success
JWT_SECRET=change_this_in_production
JWT_EXP_MINUTES=120
WEBHOOK_SHARED_SECRET=
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
"@ | Out-File -FilePath ".env" -Encoding UTF8
}

Write-Host "Ambiente preparado com sucesso."
