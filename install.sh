#!/bin/bash
# LinuxDesk - Instalador automático
# Testado em CachyOS com Niri

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC}  $1"; }
success() { echo -e "${GREEN}[OK]${NC}    $1"; }
warning() { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error()   { echo -e "${RED}[ERRO]${NC}  $1"; exit 1; }

echo ""
echo "╔══════════════════════════════════════╗"
echo "║         LinuxDesk Installer          ║"
echo "║   Android como segundo monitor USB   ║"
echo "╚══════════════════════════════════════╝"
echo ""

# Diretório do script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ─── Dependências ───
info "Verificando dependências..."

MISSING=()
command -v grim        &>/dev/null || MISSING+=("grim")
command -v adb         &>/dev/null || MISSING+=("android-tools")
command -v python3     &>/dev/null || MISSING+=("python3")
command -v monique     &>/dev/null || MISSING+=("monique (AUR)")

if [ ${#MISSING[@]} -gt 0 ]; then
    warning "Pacotes faltando: ${MISSING[*]}"
    info "Instalando via pacman..."
    sudo pacman -S --needed grim android-tools python 2>/dev/null || true
    info "Instalando monique via yay..."
    yay -S --needed monique 2>/dev/null || warning "Instale o monique manualmente: yay -S monique"
fi

# Python deps
info "Instalando dependências Python..."
pip install --break-system-packages pillow evdev python-uinput 2>/dev/null || true
success "Dependências OK"

# ─── vkms no boot ───
info "Configurando vkms para carregar no boot..."
echo "vkms" | sudo tee /etc/modules-load.d/vkms.conf > /dev/null
sudo modprobe vkms 2>/dev/null || true
success "vkms configurado"

# ─── sudoers ───
info "Configurando sudo para modprobe..."
echo "$USER ALL=(ALL) NOPASSWD: /sbin/modprobe vkms, /sbin/modprobe -r vkms" | \
    sudo tee /etc/sudoers.d/linuxdesk > /dev/null
success "sudoers configurado"

# ─── linuxdesk-switch no PATH ───
info "Instalando linuxdesk-switch..."
cat > ~/.local/bin/linuxdesk-switch << 'EOF'
#!/bin/bash
ACTION="${1:-on}"
LINUXDESK_DIR="$HOME/linuxdesk"

if [ "$ACTION" = "on" ]; then
    if ! lsmod | grep -q vkms; then
        sudo modprobe vkms
        sleep 1
    fi
    monique --switch-profile LinuxDesk 2>/dev/null || true
    sleep 2
    pkill -f "server.py" 2>/dev/null || true
    OUTPUT="Virtual-1" FPS=30 QUALITY=80 \
        bash "$LINUXDESK_DIR/start.sh" &> /tmp/linuxdesk.log &
    echo "LinuxDesk iniciado!"
elif [ "$ACTION" = "off" ]; then
    pkill -f "server.py" 2>/dev/null || true
    pkill -f "input_server.py" 2>/dev/null || true
    monique --switch-profile Notebook 2>/dev/null || true
    sleep 1
    sudo modprobe -r vkms 2>/dev/null || true
    echo "LinuxDesk parado!"
fi
EOF
chmod +x ~/.local/bin/linuxdesk-switch
success "linuxdesk-switch instalado"

# ─── Perfis do Monique ───
info "Criando perfis do Monique..."
mkdir -p ~/.config/monique/profiles

# Perfil Notebook (só eDP-1)
cat > ~/.config/monique/profiles/Notebook.json << 'EOF'
{
  "name": "Notebook",
  "monitors": [
    {
      "name": "eDP-1",
      "description": "internal",
      "enabled": true,
      "x": 0, "y": 0,
      "width": 1920, "height": 1080,
      "refresh_rate": 60.0,
      "scale": 1.0,
      "transform": 0
    }
  ],
  "workspace_rules": [],
  "last_applied_time": 0.0
}
EOF

warning "Perfil LinuxDesk será criado automaticamente na primeira vez que você ligar o segundo monitor e salvar pelo Monique (monique)"

# ─── Plugin do Noctalia ───
info "Instalando plugin Noctalia..."
PLUGIN_DIR="$HOME/.config/noctalia/plugins/linuxdesk"
mkdir -p "$PLUGIN_DIR/i18n"
cp -r "$SCRIPT_DIR/noctalia-plugin/"* "$PLUGIN_DIR/" 2>/dev/null || \
    warning "Plugin Noctalia não encontrado em $SCRIPT_DIR/noctalia-plugin/"

# Adicionar ao plugins.json
PLUGINS_JSON="$HOME/.config/noctalia/plugins.json"
if [ -f "$PLUGINS_JSON" ] && ! grep -q "linuxdesk" "$PLUGINS_JSON"; then
    python3 -c "
import json
with open('$PLUGINS_JSON') as f:
    data = json.load(f)
data['states']['linuxdesk'] = {'enabled': True, 'sourceUrl': 'https://github.com/noctalia-dev/noctalia-plugins'}
with open('$PLUGINS_JSON', 'w') as f:
    json.dump(data, f, indent=4)
print('Plugin adicionado ao Noctalia')
"
fi

success "Plugin Noctalia instalado"

# ─── Grupo input ───
info "Adicionando usuário ao grupo input..."
sudo usermod -aG input "$USER"
success "Usuário adicionado ao grupo input"

echo ""
echo "╔══════════════════════════════════════╗"
echo "║         Instalação Completa!         ║"
echo "╚══════════════════════════════════════╝"
echo ""
echo "Próximos passos:"
echo "  1. Conecte seu Android via USB"
echo "  2. Ative Depuração USB no Android"
echo "  3. Instale o APK: adb install android-app/linuxdesk.apk"
echo "  4. Reinicie o Noctalia para carregar o plugin"
echo "  5. Clique no ícone LinuxDesk na barra"
echo "  6. Abra o app no Android — conecta automaticamente!"
echo ""
echo "  Para usar sem Noctalia: linuxdesk-switch on"
echo ""
