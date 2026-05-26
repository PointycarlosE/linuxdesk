 LinuxDesk 📱→🖥️

> Use seu Android como segundo monitor no Linux via cabo USB — sem Wi-Fi, sem latência alta.

[![Estrelas do GitHub](https://img.shields.io/github/stars/PointycarlosE/linuxdesk?style=flat-square)](https://github.com/PointycarlosE/linuxdesk/stargazers)
![Plataforma](https://img.shields.io/badge/platform-Linux%20%7C%20Android-blue)
![Compositor](https://img.shields.io/badge/compositor-Niri%20%7C%20Wayland-green)
![Distro](https://img.shields.io/badge/distro-CachyOS-orange)
![Licença](https://img.shields.io/badge/license-MIT-lightgrey)

## Como funciona
Niri (Wayland)
→ grim (captura frames)
→ Pillow (converte para JPEG)
→ servidor TCP Python (porta 7878)
→ cabo USB
→ ADB reverse tunnel
→ app Android (recebe e exibe os frames)

A vantagem sobre soluções Wi-Fi como o Spacedesk é usar **ADB reverse tunnel** — 
o dado trafega pelo cabo USB físico, resultando em latência muito menor (~5-15ms vs ~50-100ms).

## Requisitos

### Linux
- CachyOS / Arch Linux
- Niri (compositor Wayland)
- Noctalia (opcional, para o plugin da barra)
- Monique (opcional, para perfis de monitor)

### Android
- Android 8.0+
- Depuração USB ativada
- Cabo USB

## Instalação rápida

```bash
git clone https://github.com/PointycarlosE/linuxdesk
cd linuxdesk
./install.sh
```

## Instalação manual

### 1. Dependências

```bash
sudo pacman -S grim android-tools python
yay -S monique
pip install --break-system-packages pillow evdev python-uinput
```

### 2. vkms (monitor virtual no kernel)

```bash
echo "vkms" | sudo tee /etc/modules-load.d/vkms.conf
sudo modprobe vkms
```

### 3. sudoers

```bash
echo "$USER ALL=(ALL) NOPASSWD: /sbin/modprobe vkms, /sbin/modprobe -r vkms" | \
    sudo tee /etc/sudoers.d/linuxdesk
```

### 4. linuxdesk-switch no PATH

```bash
cp scripts/linuxdesk-switch ~/.local/bin/
chmod +x ~/.local/bin/linuxdesk-switch
```

### 5. App Android

```bash
# Conecte o Android via USB com depuração ativada
adb install android-app/linuxdesk.apk
```

### 6. Plugin Noctalia (opcional)

```bash
mkdir -p ~/.config/noctalia/plugins/linuxdesk
cp -r noctalia-plugin/* ~/.config/noctalia/plugins/linuxdesk/
```

Adicione ao `~/.config/noctalia/plugins.json`:
```json
"linuxdesk": {
    "enabled": true,
    "sourceUrl": "https://github.com/noctalia-dev/noctalia-plugins"
}
```

### 7. Perfis do Monique (opcional)

Abra o Monique (`monique`), configure os dois monitores e salve dois perfis:
- **Notebook** — só o monitor interno
- **LinuxDesk** — monitor interno + Virtual-1 à direita

## Uso

### Com plugin Noctalia
Clique no ícone LinuxDesk na barra → abre o app no Android → conecta automaticamente.

### Sem Noctalia
```bash
linuxdesk-switch on   # liga
linuxdesk-switch off  # desliga
```

### Opções avançadas
```bash
FPS=24 QUALITY=70 SCALE=0.75 OUTPUT="Virtual-1" ./start.sh  # menor latência
FPS=30 QUALITY=85 OUTPUT="Virtual-1" ./start.sh              # padrão
```

## Estrutura do projeto
linuxdesk/
├── daemon/
│   ├── server.py          # servidor TCP — captura e envia frames
│   └── input_server.py    # servidor de input — touch e S Pen
├── android-app/           # app Android (Kotlin)
│   └── app/src/main/java/com/linuxdesk/
│       ├── MainActivity.kt
│       ├── StreamClient.kt
│       └── InputClient.kt
├── noctalia-plugin/       # plugin para a barra do Noctalia
│   ├── manifest.json
│   ├── Main.qml
│   └── BarWidget.qml
├── scripts/
│   └── linuxdesk-switch   # script para ligar/desligar
├── start.sh               # inicializador do servidor
├── install.sh             # instalador automático
└── README.md

## Compatibilidade

| Compositor | Status |
|---|---|
| Niri | ✅ Testado |
| Sway | ⚠️ Não testado |
| Hyprland | ⚠️ Não testado |

| Distro | Status |
|---|---|
| CachyOS | ✅ Testado |
| Arch Linux | ⚠️ Deve funcionar |
| EndeavourOS | ⚠️ Não testado |

## Roadmap

- [x] Streaming de vídeo via USB
- [x] Monitor virtual com vkms
- [x] Plugin Noctalia
- [x] Reconexão automática
- [ ] Touch input / S Pen
- [ ] Compressão H.264 via VAAPI
- [ ] Suporte a outros compositores

## Créditos

Pioneiro: **carlos** (CachyOS + Niri)  
Inspirado no Spacedesk (Windows)

## Licença

MIT
