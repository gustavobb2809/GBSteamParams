#!/usr/bin/env bash
# Instala as dependencias do GBSteamParams: PySide6, gamemode, mangohud e
# gamescope, via o gerenciador de pacotes da distro (dnf/apt/pacman/zypper),
# e deixa o proprio GBSteamParams instalado em modo editavel no final.
#
# lsfg-vk (integracao com o Lossless Scaling) e opcional, nao tem pacote
# oficial na maioria das distros e por isso nao e instalado automaticamente
# aqui — o script so mostra como instalar na secao final.
set -euo pipefail

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
RESET='\033[0m'

info() { echo -e "${BOLD}==>${RESET} $*"; }
ok()   { echo -e "${GREEN}ok:${RESET} $*"; }
warn() { echo -e "${YELLOW}aviso:${RESET} $*"; }
err()  { echo -e "${RED}erro:${RESET} $*" >&2; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
    if command -v sudo >/dev/null 2>&1; then
        SUDO="sudo"
    else
        err "precisa rodar como root ou ter 'sudo' instalado."
        exit 1
    fi
fi

install_fedora() {
    info "Fedora/dnf detectado — instalando pacotes do sistema"
    $SUDO dnf install -y python3 python3-pip python3-pyside6 gamemode mangohud gamescope
}

install_debian() {
    info "Debian/Ubuntu (apt) detectado — instalando pacotes do sistema"
    $SUDO apt-get update
    $SUDO apt-get install -y python3 python3-pip \
        python3-pyside6.qtcore python3-pyside6.qtgui python3-pyside6.qtwidgets \
        gamemode mangohud gamescope
}

install_arch() {
    info "Arch (pacman) detectado — instalando pacotes do sistema"
    $SUDO pacman -Sy --needed --noconfirm python python-pyside6 gamemode mangohud gamescope
}

install_opensuse() {
    info "openSUSE (zypper) detectado — instalando pacotes do sistema"
    $SUDO zypper install -y python3 python3-PySide6 gamemode mangohud gamescope
}

install_pip_fallback() {
    warn "gerenciador de pacotes nao reconhecido automaticamente."
    warn "instale gamemode, mangohud e gamescope manualmente pelo pacote da sua distro."
    info "tentando instalar o PySide6 via pip --user..."
    python3 -m pip install --user PySide6
}

if command -v dnf >/dev/null 2>&1; then
    install_fedora
elif command -v apt-get >/dev/null 2>&1; then
    install_debian
elif command -v pacman >/dev/null 2>&1; then
    install_arch
elif command -v zypper >/dev/null 2>&1; then
    install_opensuse
else
    install_pip_fallback
fi

echo
info "Conferindo o que ficou disponivel:"
check_bin() {
    if command -v "$1" >/dev/null 2>&1; then
        ok "$1 encontrado"
    else
        warn "$1 NAO encontrado"
    fi
}
check_bin gamemoderun
check_bin mangohud
check_bin gamescope
if python3 -c "import PySide6" >/dev/null 2>&1; then
    ok "PySide6 encontrado"
else
    warn "PySide6 NAO encontrado"
fi

echo
info "lsfg-vk (frame generation do Lossless Scaling no Linux) e opcional"
info "e nao tem pacote oficial na maioria das distros."

STEAM_IS_FLATPAK=0
if command -v flatpak >/dev/null 2>&1 \
    && flatpak list --app 2>/dev/null | grep -q "com.valvesoftware.Steam"; then
    STEAM_IS_FLATPAK=1
fi

if [ "$STEAM_IS_FLATPAK" -eq 1 ]; then
    echo "  Sua Steam parece ser a versao Flatpak — nesse caso o jeito certo"
    echo "  e a extensao Flatpak do lsfg-vk (a versao nativa/AUR nao e"
    echo "  visivel de dentro do sandbox da Steam Flatpak)."
    read -r -p "  Instalar 'org.freedesktop.Platform.VulkanLayer.lsfgvk' via Flathub agora? [s/N] " resp
    case "$resp" in
        [sS]*)
            flatpak remote-add --user --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
            flatpak install --user -y flathub \
                org.freedesktop.Platform.VulkanLayer.lsfgvk//24.08 \
                org.freedesktop.Platform.VulkanLayer.lsfgvk//25.08
            echo
            echo "  Depois, libere o acesso pra Steam Flatpak com:"
            echo "    mkdir -p \"\$HOME/.config/lsfg-vk\""
            echo "    flatpak override --user --filesystem=\"\$HOME/.config/lsfg-vk:rw\" com.valvesoftware.Steam"
            echo "    flatpak override --user --env=LSFGVK_CONFIG=\"\$HOME/.config/lsfg-vk/conf.toml\" com.valvesoftware.Steam"
            ;;
        *) echo "  pulado. instrucoes completas em https://lsfg-vk.dev/docs/installation/flatpak/" ;;
    esac
elif command -v pacman >/dev/null 2>&1; then
    AUR_HELPER=""
    for h in yay paru; do
        command -v "$h" >/dev/null 2>&1 && AUR_HELPER="$h" && break
    done
    if [ -n "$AUR_HELPER" ]; then
        read -r -p "  Instalar lsfg-vk via AUR agora com '$AUR_HELPER' (nao oficial)? [s/N] " resp
        case "$resp" in
            [sS]*) "$AUR_HELPER" -S lsfg-vk ;;
            *) echo "  pulado. rode '$AUR_HELPER -S lsfg-vk' quando quiser." ;;
        esac
    else
        echo "  Arch: instale um AUR helper (yay/paru) e rode 'yay -S lsfg-vk'."
    fi
else
    echo "  Sua Steam parece ser nativa, entao a extensao Flatpak do lsfg-vk"
    echo "  nao serve pra ela (so pra jogos/launchers que rodam em Flatpak)."
    echo "  builds nativos prontos em https://builds.lsfg-vk.dev"
    echo "  instrucoes completas em https://lsfg-vk.dev/docs/installation/"
fi
echo "  Alem do lsfg-vk em si, e preciso ter o Lossless Scaling na sua"
echo "  biblioteca Steam (appid 993090) — ele fornece a Lossless.dll."

echo
info "Instalando o GBSteamParams (modo editavel)..."
python3 -m pip install --user -e "$REPO_DIR"

echo
ok "Pronto. Rode 'steam-boost-gui' ou 'steam-boost --dry-run' pra testar."
