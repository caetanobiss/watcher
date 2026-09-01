#!/usr/bin/env bash

# ==============================================================================
# 🛡️ Watcher - Interactive Installer & Dependency Setup Script
# ==============================================================================

set -e

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Auto-confirm flag
AUTO_YES=false
if [[ "$1" == "-y" || "$1" == "--yes" ]]; then
    AUTO_YES=true
fi

print_header() {
    clear 2>/dev/null || true
    echo -e "${CYAN}${BOLD}"
    echo "=============================================================================="
    echo " 🛡️  AURIGA WATCHER - INSTALADOR DE DEPENDÊNCIAS E CONFIGURAÇÃO"
    echo "=============================================================================="
    echo -e "${NC}"
    echo -e "Este assistente irá verificar e configurar todas as ferramentas para que o"
    echo -e "Watcher funcione com a ${BOLD}máxima velocidade e eficiência${NC} no seu sistema."
    echo ""
}

prompt_user() {
    local prompt_message="$1"
    local default_value="${2:-Y}"

    if [ "$AUTO_YES" = true ]; then
        return 0
    fi

    if [ "$default_value" = "Y" ]; then
        echo -n -e "${YELLOW}${prompt_message} [S/n]: ${NC}"
    else
        echo -n -e "${YELLOW}${prompt_message} [s/N]: ${NC}"
    fi

    read -r response
    response=$(echo "$response" | tr '[:upper:]' '[:lower:]')

    if [ "$default_value" = "Y" ]; then
        if [[ "$response" == "n" || "$response" == "nao" || "$response" == "não" ]]; then
            return 1
        else
            return 0
        fi
    else
        if [[ "$response" == "s" || "$response" == "sim" || "$response" == "y" || "$response" == "yes" ]]; then
            return 0
        else
            return 1
        fi
    fi
}

detect_package_manager() {
    if command -v apt-get &>/dev/null; then
        PKG_MGR="apt"
        INSTALL_CMD="sudo apt-get update && sudo apt-get install -y"
    elif command -v brew &>/dev/null; then
        PKG_MGR="brew"
        INSTALL_CMD="brew install"
    elif command -v dnf &>/dev/null; then
        PKG_MGR="dnf"
        INSTALL_CMD="sudo dnf install -y"
    elif command -v pacman &>/dev/null; then
        PKG_MGR="pacman"
        INSTALL_CMD="sudo pacman -S --noconfirm"
    elif command -v yum &>/dev/null; then
        PKG_MGR="yum"
        INSTALL_CMD="sudo yum install -y"
    elif command -v zypper &>/dev/null; then
        PKG_MGR="zypper"
        INSTALL_CMD="sudo zypper install -y"
    else
        PKG_MGR="unknown"
        INSTALL_CMD=""
    fi
}

install_package() {
    local pkg_name="$1"
    local apt_name="${2:-$pkg_name}"
    local brew_name="${3:-$pkg_name}"
    local arch_name="${4:-$pkg_name}"

    if [ "$PKG_MGR" = "unknown" ]; then
        echo -e "${RED}❌ Gerenciador de pacotes não identificado automaticamente.${NC}"
        echo -e "Por favor, instale ${BOLD}${pkg_name}${NC} manualmente usando o gerenciador de pacotes da sua distribuição."
        return 1
    fi

    local target_pkg="$pkg_name"
    case "$PKG_MGR" in
        apt) target_pkg="$apt_name" ;;
        brew) target_pkg="$brew_name" ;;
        pacman) target_pkg="$arch_name" ;;
    esac

    echo -e "${BLUE}📦 Instalando ${target_pkg} via ${PKG_MGR}...${NC}"
    eval "$INSTALL_CMD $target_pkg"
}

main() {
    print_header
    detect_package_manager

    # 1. Verification of Python 3
    echo -e "${BOLD}1. Verificando Python 3...${NC}"
    if command -v python3 &>/dev/null; then
        PY_VERSION=$(python3 --version 2>&1)
        echo -e "${GREEN}  ✓ Python 3 já está instalado (${PY_VERSION}).${NC}"
    else
        echo -e "${RED}  ❌ Python 3 não foi encontrado!${NC}"
        echo -e "${CYAN}  Motivo da instalação:${NC} O Watcher é construído em Python 3.10+ (API HTTP server, parser de entidades Ruby/GraphQL e motor de análise de risco)."
        if prompt_user "  Deseja instalar o Python 3 agora?"; then
            install_package "python3" "python3" "python" "python"
        else
            echo -e "${YELLOW}  ⚠️  Atenção: O Watcher não poderá ser executado sem o Python 3.${NC}"
        fi
    fi
    echo ""

    # 2. Verification of Git
    echo -e "${BOLD}2. Verificando Git...${NC}"
    if command -v git &>/dev/null; then
        GIT_VERSION=$(git --version 2>&1)
        echo -e "${GREEN}  ✓ Git já está instalado (${GIT_VERSION}).${NC}"
    else
        echo -e "${RED}  ❌ Git não foi encontrado!${NC}"
        echo -e "${CYAN}  Motivo da instalação:${NC} O Watcher usa o Git para extrair alterações de diff (Working Tree, Staging Area, Branches e Commits)."
        if prompt_user "  Deseja instalar o Git agora?"; then
            install_package "git" "git" "git" "git"
        else
            echo -e "${YELLOW}  ⚠️  Atenção: O Watcher necessita do Git para detectar alterações no repositório.${NC}"
        fi
    fi
    echo ""

    # 3. Verification of Ripgrep (rg)
    echo -e "${BOLD}3. Verificando Ripgrep (rg)...${NC}"
    if command -v rg &>/dev/null; then
        RG_VERSION=$(rg --version | head -n 1)
        echo -e "${GREEN}  ✓ Ripgrep (rg) já está instalado (${RG_VERSION}).${NC}"
    else
        echo -e "${YELLOW}  ⚠️  Ripgrep (rg) NÃO foi encontrado no sistema.${NC}"
        echo -e "${CYAN}  Motivo da instalação:${NC}"
        echo -e "  O ${BOLD}ripgrep${NC} é uma ferramenta de busca regex ultra-rápida. Com o Ripgrep instalado, o Watcher"
        echo -e "  consegue varrer todas as dezenas de módulos do monorepo em ${BOLD}menos de 1 segundo${NC}."
        echo -e "  (Nota: O Watcher possui fallback nativo em Python, mas o Ripgrep garante máxima velocidade)."
        echo ""
        if prompt_user "  Deseja instalar o Ripgrep (rg) agora para máxima performance?"; then
            install_package "ripgrep" "ripgrep" "ripgrep" "ripgrep"
        else
            echo -e "${YELLOW}  ℹ️  Ripgrep não instalado. O Watcher usará a busca nativa em Python.${NC}"
        fi
    fi
    echo ""

    # 4. Global Command Setup (CLI alias / bin link)
    echo -e "${BOLD}4. Configurando comando global 'watcher'...${NC}"
    WATCHER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    SCRIPT_PATH="${WATCHER_DIR}/watcher.py"

    if command -v watcher &>/dev/null; then
        echo -e "${GREEN}  ✓ O comando 'watcher' já está disponível no terminal.${NC}"
    else
        echo -e "${CYAN}  Motivo da instalação:${NC}"
        echo -e "  Criar o comando global ${BOLD}'watcher'${NC} permite que você rode a ferramenta diretamente de qualquer pasta"
        echo -e "  no seu terminal (ex: digitando 'watcher server' ou 'watcher analyze --engine stock')."
        echo ""
        if prompt_user "  Deseja criar o atalho/comando 'watcher' no seu terminal?"; then
            BIN_DIR="${HOME}/.local/bin"
            mkdir -p "$BIN_DIR"

            cat <<EOF > "${BIN_DIR}/watcher"
#!/usr/bin/env bash
python3 "${SCRIPT_PATH}" "\$@"
EOF
            chmod +x "${BIN_DIR}/watcher"
            echo -e "${GREEN}  ✓ Executável criado em: ${BIN_DIR}/watcher${NC}"

            # Check if BIN_DIR is in PATH
            if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
                echo -e "${YELLOW}  ⚠️  Adicionando ${BIN_DIR} ao seu PATH no arquivo de configuração do shell...${NC}"
                SHELL_PROFILE=""
                if [[ "$SHELL" == *"zsh"* ]]; then
                    SHELL_PROFILE="${HOME}/.zshrc"
                elif [[ "$SHELL" == *"bash"* ]]; then
                    SHELL_PROFILE="${HOME}/.bashrc"
                else
                    SHELL_PROFILE="${HOME}/.profile"
                fi

                if [ -n "$SHELL_PROFILE" ] && [ -f "$SHELL_PROFILE" ]; then
                    if ! grep -q '\.local/bin' "$SHELL_PROFILE"; then
                        echo '' >> "$SHELL_PROFILE"
                        echo '# Watcher CLI Path' >> "$SHELL_PROFILE"
                        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$SHELL_PROFILE"
                        echo -e "${GREEN}  ✓ Linha adicionada em ${SHELL_PROFILE}.${NC}"
                        echo -e "${BLUE}  💡 Dica: Execute 'source ${SHELL_PROFILE}' para recarregar o PATH nesta sessão de terminal.${NC}"
                    fi
                fi
            fi
        else
            echo -e "${YELLOW}  ℹ️  Atalho não criado. Você pode rodar usando 'python3 watcher.py'.${NC}"
        fi
    fi
    echo ""

    # Finished
    echo -e "${GREEN}${BOLD}=============================================================================="
    echo " 🎉 INSTALAÇÃO E CONFIGURAÇÃO CONCLUÍDAS COM SUCESSO!"
    echo "=============================================================================="
    echo -e "${NC}"
    echo -e "Para iniciar o Dashboard Web com 1 clique, rode:"
    echo -e "  ${CYAN}./watcher.sh${NC}   (ou ${CYAN}watcher server${NC})"
    echo ""
    echo -e "Para rodar uma análise de impacto via CLI:"
    echo -e "  ${CYAN}watcher analyze --engine stock${NC}"
    echo ""
}

main "$@"
