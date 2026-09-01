#!/usr/bin/env bash

# ==============================================================================
# 🛡️ Watcher - Standalone Automated Update Script
# (Works without Git installed and without requiring GitHub login/credentials)
# ==============================================================================

set -e

WATCHER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_PATH="${WATCHER_DIR}/watcher.py"

if ! command -v python3 &>/dev/null; then
    echo "❌ Python 3 é necessário para executar a atualização do Watcher."
    exit 1
fi

python3 "${SCRIPT_PATH}" update "$@"
