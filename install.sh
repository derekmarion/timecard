#!/usr/bin/env bash
# install.sh — Install TimeCard on Mac/Linux.
# Installs uv if absent, installs WeasyPrint system deps, then installs the tool.
set -euo pipefail

echo "=== TimeCard Installer ==="

# 1. Install uv if not present
if ! command -v uv &>/dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# 2. Install WeasyPrint system dependencies
if [[ "$(uname)" == "Darwin" ]]; then
    echo "Installing WeasyPrint dependencies via Homebrew..."
    if ! command -v brew &>/dev/null; then
        echo "Error: Homebrew is required on macOS. Install it from https://brew.sh"
        exit 2
    fi
    brew install pango libffi
elif command -v apt-get &>/dev/null; then
    echo "Installing WeasyPrint dependencies via apt..."
    sudo apt-get update -qq
    sudo apt-get install -y -qq libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev
elif command -v dnf &>/dev/null; then
    echo "Installing WeasyPrint dependencies via dnf..."
    sudo dnf install -y pango gdk-pixbuf2 libffi-devel
else
    echo "Warning: Could not detect package manager. Ensure WeasyPrint system deps are installed."
    echo "See: https://doc.courtbouillon.org/weasyprint/stable/first_steps.html"
fi

# 3. Install timecard
echo "Installing TimeCard..."
uv tool install .

echo ""
echo "Done! Run 'timecard --help' to get started."
