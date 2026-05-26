#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  LinuxDesk - Script de inicialização
#  Configura o túnel ADB e inicia o servidor
# ─────────────────────────────────────────────────────────────

set -e

PORT=7878
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DAEMON="$SCRIPT_DIR/daemon/server.py"

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info()    { echo -e "${GREEN}[INFO]${NC}  $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $*"; }
log_section() { echo -e "\n${BLUE}▶ $*${NC}"; }

# ─────────────────────────────────────────────
# 1. Verifica dependências
# ─────────────────────────────────────────────
log_section "Verificando dependências..."

check_cmd() {
    if command -v "$1" &>/dev/null; then
        log_info "$1 ✓"
    else
        log_error "$1 não encontrado!"
        echo "  Instale com: sudo pacman -S $2"
        exit 1
    fi
}

check_cmd adb   "android-tools"
check_cmd grim  "grim"
check_cmd python3 "python"

# Verifica PIL
if python3 -c "from PIL import Image" &>/dev/null; then
    log_info "Pillow (PIL) ✓"
else
    log_warn "Pillow não encontrado, instalando..."
    pip install --break-system-packages pillow
fi

# ─────────────────────────────────────────────
# 2. Verifica dispositivo ADB
# ─────────────────────────────────────────────
log_section "Verificando dispositivo Android..."

# Inicia servidor ADB se necessário
adb start-server 2>/dev/null

# Aguarda dispositivo
DEVICE=$(adb devices 2>/dev/null | grep -v "List of devices" | grep "device$" | head -1 | awk '{print $1}')

if [ -z "$DEVICE" ]; then
    log_error "Nenhum dispositivo Android encontrado!"
    echo ""
    echo "  Verifique se:"
    echo "  1. O cabo USB está conectado"
    echo "  2. 'Depuração USB' está ativa no Android"
    echo "  3. Você aceitou a autorização no Android"
    echo ""
    echo "  Rode 'adb devices' para verificar"
    exit 1
fi

log_info "Dispositivo encontrado: $DEVICE"

# ─────────────────────────────────────────────
# 3. Configura túnel ADB reverso
# ─────────────────────────────────────────────
log_section "Configurando túnel ADB..."

# adb reverse: faz o Android enxergar localhost:PORT como se fosse o Linux
# Ou seja: Android conecta em localhost:PORT → vai pelo USB → chega no Linux:PORT
adb -s "$DEVICE" reverse "tcp:$PORT" "tcp:$PORT"

if [ $? -eq 0 ]; then
    log_info "Túnel ADB configurado: Android:$PORT → Linux:$PORT via USB ✓"
else
    log_error "Falha ao configurar túnel ADB"
    exit 1
fi

# ─────────────────────────────────────────────
# 4. Inicia o servidor
# ─────────────────────────────────────────────
log_section "Iniciando LinuxDesk Server..."
echo ""
echo "  Porta:   $PORT"
echo "  FPS:     ${FPS:-30}"
echo "  Qualidade: ${QUALITY:-80}"
echo ""
echo "  Agora abra o app LinuxDesk no seu Android!"
echo "  (Pressione Ctrl+C para parar)"
echo ""

# Limpeza ao sair
cleanup() {
    echo ""
    log_info "Encerrando..."
    kill $INPUT_PID 2>/dev/null || true
    adb -s "$DEVICE" reverse --remove "tcp:$PORT" 2>/dev/null || true
    adb -s "$DEVICE" reverse --remove "tcp:7879" 2>/dev/null || true
    log_info "Túnel ADB removido. Bye!"
}
trap cleanup EXIT

# Configura túnel ADB para input também
adb -s "$DEVICE" reverse tcp:7879 tcp:7879 2>/dev/null && \
    log_info "Túnel ADB input configurado: Android:7879 → Linux:7879 ✓"

# Inicia servidor de input em background
python3 "$SCRIPT_DIR/daemon/input_server.py" &
INPUT_PID=$!
log_info "Servidor de input iniciado (PID: $INPUT_PID)"

# Inicia o daemon Python principal
python3 "$DAEMON" \
    --port "${PORT}" \
    --fps "${FPS:-30}" \
    --quality "${QUALITY:-80}" \
    ${OUTPUT:+--output "$OUTPUT"} \
    ${SCALE:+--scale "$SCALE"}
