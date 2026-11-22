#!/usr/bin/env bash
set -e

echo "============================================================"
echo "  J.A.R.V.I.S. MARK XIV — INSTALADOR AUTOMÁTICO (UBUNTU)"
echo "============================================================"

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "[1/6] Instalando dependencias del sistema (apt)..."
sudo apt-get update
sudo apt-get install -y \
  python3 python3-venv python3-pip \
  portaudio19-dev ffmpeg wmctrl xdotool playerctl \
  gnome-screenshot xclip brightnessctl x11-utils \
  libxcb-cursor0 libgl1 libglib2.0-0 libnotify-bin

echo "[2/6] Creando entorno virtual Python (.venv) e instalando paquetes..."
python3 -m venv "$PROJECT_DIR/.venv"
"$PROJECT_DIR/.venv/bin/pip" install --upgrade pip
"$PROJECT_DIR/.venv/bin/pip" install -r "$PROJECT_DIR/requirements.txt"

echo "[3/6] Verificando archivo de variables de entorno (.env)..."
if [ ! -f "$PROJECT_DIR/.env" ]; then
  cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
  echo "  -> Se creó .env desde .env.example. Edítalo con tu GEMINI_API_KEY."
fi

chmod +x "$PROJECT_DIR"/*.py "$PROJECT_DIR/start_jarvis.sh" 2>/dev/null || true

echo "[4/6] Configurando autostart de GNOME y alias 'jv'..."
mkdir -p "$HOME/.config/autostart"
cat << DESKTOP > "$HOME/.config/autostart/jarvis-wake.desktop"
[Desktop Entry]
Type=Application
Name=J.A.R.V.I.S. Mark XIV Boot Protocol
Comment=Bloquea la pantalla al encender y espera las 2 palmadas
Exec=$PROJECT_DIR/start_jarvis.sh
Path=$PROJECT_DIR
Terminal=false
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=1
DESKTOP
chmod +x "$HOME/.config/autostart/jarvis-wake.desktop"

if ! grep -q "alias jv=" "$HOME/.bashrc"; then
  echo "alias jv='$PROJECT_DIR/.venv/bin/python $PROJECT_DIR/jarvis_wake.py --listen-once'" >> "$HOME/.bashrc"
fi

echo "[5/6] Configurando permisos sudoers (lock/unlock/shutdown) y apagado rápido ACPI..."
sudo bash -c "cat << SUDO > /etc/sudoers.d/jarvis-unlock
$USER ALL=(ALL) NOPASSWD: /usr/bin/loginctl, /bin/loginctl, /usr/sbin/poweroff, /sbin/poweroff, /usr/bin/systemctl, /bin/systemctl
SUDO"
sudo chmod 0440 /etc/sudoers.d/jarvis-unlock

sudo mkdir -p /etc/systemd/system.conf.d
sudo bash -c "cat << SYS > /etc/systemd/system.conf.d/jarvis-fast-shutdown.conf
[Manager]
DefaultTimeoutStopSec=10s
DefaultTimeoutAbortSec=10s
SYS"
sudo systemctl daemon-reload

echo "[6/6] Validando sintaxis de todos los módulos Python..."
"$PROJECT_DIR/.venv/bin/python" -m py_compile "$PROJECT_DIR"/jarvis_*.py

echo ""
echo "[OK] Instalación de J.A.R.V.I.S. Mark XIV completada con éxito."
echo "Siguiente paso: edita '$PROJECT_DIR/.env' con tu GEMINI_API_KEY y ejecuta 'source ~/.bashrc'."
