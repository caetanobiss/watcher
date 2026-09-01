#!/usr/bin/env bash

# ==============================================================================
# 🛡️ Watcher - Web Dashboard Launcher Script
# ==============================================================================

set -e

WATCHER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_PATH="${WATCHER_DIR}/watcher.py"
PORT="${WATCHER_PORT:-3019}"

# Parse arguments if custom port is passed (e.g., ./watcher.sh 3020 or ./watcher.sh --port 3020)
while [[ $# -gt 0 ]]; do
    case "$1" in
        --port|-p)
            PORT="$2"
            shift 2
            ;;
        *)
            if [[ "$1" =~ ^[0-9]+$ ]]; then
                PORT="$1"
            fi
            shift
            ;;
    esac
done

# Color definitions
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

clear 2>/dev/null || true
echo -e "${CYAN}${BOLD}"
echo "=============================================================================="
echo " 🛡️  AURIGA WATCHER - SERVIDOR WEB DASHBOARD"
echo "=============================================================================="
echo -e "${NC}"
echo -e " 🚀 Servidor iniciado com sucesso!"
echo -e " 🌐 Acesse no seu navegador: ${GREEN}${BOLD}http://localhost:${PORT}${NC}"
echo -e " 💡 Pressione ${YELLOW}Ctrl + C${NC} no terminal para parar o servidor."
echo -e "${CYAN}=============================================================================="
echo -e "${NC}"

# Open browser automatically in background if possible
(
    sleep 1.2
    if command -v xdg-open &>/dev/null; then
        xdg-open "http://localhost:${PORT}" &>/dev/null || true
    elif command -v open &>/dev/null; then
        open "http://localhost:${PORT}" &>/dev/null || true
    fi
) &

exec python3 "${SCRIPT_PATH}" server --port "${PORT}"
