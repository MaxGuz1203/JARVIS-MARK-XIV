#!/usr/bin/env bash
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"
export DISPLAY="${DISPLAY:-:0}"
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export DBUS_SESSION_BUS_ADDRESS="unix:path=${XDG_RUNTIME_DIR}/bus"
export QT_QPA_PLATFORM="xcb"

cd "$HOME/jarvis" || exit 1

# Evitar duplicados si ya está corriendo
pkill -f "jarvis_wake.py" 2>/dev/null
pkill -f "jarvis_hud.py" 2>/dev/null

# Esperar un instante a que GNOME Shell y PipeWire terminen de levantar tras el encendido
sleep 2
"$HOME/jarvis/activar_aec.sh" >> /tmp/jarvis_boot.log 2>&1

# Bloquear la pantalla de inmediato al encender la laptop para esperar las 2 palmadas
sudo -n /usr/bin/loginctl lock-sessions 2>/dev/null
loginctl lock-session 2>/dev/null
gdbus call --session --dest org.gnome.ScreenSaver --object-path /org/gnome/ScreenSaver --method org.gnome.ScreenSaver.Lock >/dev/null 2>&1

# Bucle guardián: mantiene a J.A.R.V.I.S. siempre vivo
while true; do
    "$HOME/jarvis/.venv/bin/python" "$HOME/jarvis/jarvis_wake.py" >> /tmp/jarvis_boot.log 2>&1
    sleep 2
done
