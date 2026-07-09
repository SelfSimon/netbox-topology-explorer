# Bootstrap developer environment (PowerShell)
# Creates venv, installs dev extras, and installs pre-commit hooks.

param()

$venvPath = ".venv"

if (-not (Test-Path $venvPath)) {
    python -m venv $venvPath
}

Write-Host "Activating venv and installing dev dependencies..."
& "$venvPath\Scripts\Activate.ps1"
python -m pip install --upgrade pip
pip install -e ".[dev]"

Write-Host "Installing pre-commit hooks..."
pre-commit install
pre-commit run --all-files

Write-Host "Bootstrap complete."
