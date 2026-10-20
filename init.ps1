# Полная инициализация тренажёра (venv + зависимости).
# Запуск из корня репозитория:
#   powershell -ExecutionPolicy Bypass -File .\init.ps1
#   powershell -ExecutionPolicy Bypass -File .\init.ps1 -Start
#   powershell -ExecutionPolicy Bypass -File .\init.ps1 -Test

[CmdletBinding()]
param(
    [switch]$Start,
    [switch]$Test
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

function Find-Python {
    foreach ($cmd in @("py", "python")) {
        try {
            $ver = & $cmd --version 2>&1
            if ($LASTEXITCODE -eq 0 -or $ver -match "Python") {
                return $cmd
            }
        } catch {
            continue
        }
    }
    throw "Python не найден. Установите Python 3.10+ и добавьте в PATH."
}

$python = Find-Python
Write-Host "Python: $python ($( & $python --version ))" -ForegroundColor Cyan

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$venvPip = Join-Path $PSScriptRoot ".venv\Scripts\pip.exe"

if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host "Создаю виртуальное окружение .venv ..." -ForegroundColor Cyan
    & $python -m venv .venv
    if (-not (Test-Path -LiteralPath $venvPython)) {
        throw "Не удалось создать .venv"
    }
} else {
    Write-Host "Виртуальное окружение .venv уже есть." -ForegroundColor DarkGray
}

Write-Host "Устанавливаю зависимости из requirements.txt ..." -ForegroundColor Cyan
& $venvPython -m pip install --upgrade pip
& $venvPip install -r requirements.txt

if ($Test) {
    Write-Host "Устанавливаю dev-зависимости из requirements-dev.txt ..." -ForegroundColor Cyan
    & $venvPip install -r requirements-dev.txt
    Write-Host "Запускаю pytest ..." -ForegroundColor Cyan
    & $venvPython -m pytest -q
}

Write-Host ""
Write-Host "Готово." -ForegroundColor Green
Write-Host "Запуск тренажёра:"
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host "  streamlit run app.py"
Write-Host "Или сразу:  powershell -ExecutionPolicy Bypass -File .\init.ps1 -Start"

if ($Start) {
    Write-Host ""
    Write-Host "Стартую Streamlit ..." -ForegroundColor Cyan
    & $venvPython -m streamlit run app.py
}
