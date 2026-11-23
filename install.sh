#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="${HOME}/.local/bin"
PLUGIN_DIR="${HOME}/.config/omarchy/plugins/io.github.aomine-c2c.vfex-direct"

mkdir -p "${BIN_DIR}" "${PLUGIN_DIR}"
chmod +x "${SCRIPT_DIR}/vfex.py" "${SCRIPT_DIR}/vfex_tui.py"
ln -sf "${SCRIPT_DIR}/vfex.py" "${BIN_DIR}/vfex"
ln -sf "${SCRIPT_DIR}/vfex_tui.py" "${BIN_DIR}/vfex-tui"

for f in Panel.qml BarWidget.qml NothingNotch.qml manifest.json vfex.py accounting.py intelligence.py newsroom.py planner.py exchange_adapters.py desktop_notify.py vfex_tui.py workspace_prefs.py ai_providers.py paper_arena.py mahoraga_weights.json; do
    if [ -e "${SCRIPT_DIR}/${f}" ]; then
        ln -sf "${SCRIPT_DIR}/${f}" "${PLUGIN_DIR}/${f}"
    fi
done

if [ -d "${SCRIPT_DIR}/components" ]; then
    ln -sfn "${SCRIPT_DIR}/components" "${PLUGIN_DIR}/components"
fi

echo "Installed vfex -> ${BIN_DIR}/vfex"
echo "Symlinked plugin files & components -> ${PLUGIN_DIR}"
echo "Make sure ${BIN_DIR} is in your PATH."

if command -v omarchy-restart-shell >/dev/null 2>&1; then
    echo "Reloading Omarchy shell..."
    omarchy-restart-shell
fi
