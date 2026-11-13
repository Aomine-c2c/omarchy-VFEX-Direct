#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="${HOME}/.local/bin"
PLUGIN_DIR="${HOME}/.config/omarchy/plugins/io.github.aomine-c2c.vfex-direct"

mkdir -p "${BIN_DIR}" "${PLUGIN_DIR}"
chmod +x "${SCRIPT_DIR}/vfex.py"
ln -sf "${SCRIPT_DIR}/vfex.py" "${BIN_DIR}/vfex"

for f in Panel.qml BarWidget.qml manifest.json vfex.py; do
    ln -sf "${SCRIPT_DIR}/${f}" "${PLUGIN_DIR}/${f}"
done

echo "Installed vfex -> ${BIN_DIR}/vfex"
echo "Symlinked plugin files -> ${PLUGIN_DIR}"
echo "Make sure ${BIN_DIR} is in your PATH."
