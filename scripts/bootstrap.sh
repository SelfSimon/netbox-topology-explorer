#!/usr/bin/env bash
set -euo pipefail

VENV=${VENV:-.venv}

if [ ! -d "$VENV" ]; then
  python -m venv "$VENV"
fi

# shellcheck source=/dev/null
source "$VENV/bin/activate"
python -m pip install --upgrade pip
pip install -e '.[dev]'

echo "Installing pre-commit hooks..."
pre-commit install
pre-commit run --all-files

echo "Bootstrap complete."
