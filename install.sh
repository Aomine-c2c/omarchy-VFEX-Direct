#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="${HOME}/.local/bin"

mkdir -p "${BIN_DIR}"
chmod +x "${SCRIPT_DIR}/vfex.py"
ln -sf "${SCRIPT_DIR}/vfex.py" "${BIN_DIR}/vfex"

echo "Installed vfex -> ${BIN_DIR}/vfex"
echo "Make sure ${BIN_DIR} is in your PATH."
