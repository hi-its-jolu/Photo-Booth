#!/bin/bash
set -e

# ─────────────────────────────────────────────
# Wedding Photo Booth - Raspberry Pi Setup
# Run this ON THE PI, from inside the cloned repo:
#   git clone https://github.com/hi-its-jolu/Photo-Booth.git
#   cd Photo-Booth
#   chmod +x setup_pi.sh
#   ./setup_pi.sh
#
# Installs system + Python dependencies, and installs a systemd
# service so the booth launches full-screen on every boot (no
# desktop environment required - renders directly via KMS/DRM).
# ─────────────────────────────────────────────

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_USER="$(whoami)"
VENV_DIR="$REPO_DIR/venv"
SERVICE_NAME="photobooth"

echo ""
echo "🎉 Wedding Photo Booth - Raspberry Pi Setup"
echo "────────────────────────────────────────────"
echo "Repo:  $REPO_DIR"
echo "User:  $APP_USER"
echo ""

# ── System packages ───────────────────────────
echo "📦 Installing system packages (sudo required)..."
sudo apt-get update
sudo apt-get install -y \
  git python3-venv python3-pip \
  libsdl2-2.0-0 libsdl2-image-2.0-0 libsdl2-mixer-2.0-0 libsdl2-ttf-2.0-0 \
  libjpeg62-turbo libopenjp2-7 libtiff6 \
  libegl1 libgles2 \
  alsa-utils \
  cups cups-client \
  swig python3-dev build-essential liblgpio-dev \
  python3-pygame

# App user needs: lpadmin (configure printers), gpio/video/render (draw to
# the screen + read GPIO buttons without root), input (read USB/GPIO input).
sudo usermod -aG lpadmin,gpio,video,render,input "$APP_USER"

# ── Python virtual environment ────────────────
# --system-site-packages so the venv can see the apt-installed python3-pygame
# below - the PyPI pygame wheel bundles its own private SDL2 build with no
# kmsdrm support, so it can't render fullscreen without a desktop/X11. The
# Raspberry Pi Foundation's own apt package is built with kmsdrm enabled.
if [ ! -d "$VENV_DIR" ]; then
  echo "📦 Creating virtual environment..."
  python3 -m venv --system-site-packages "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

pip install --upgrade pip --quiet
echo "📦 Installing Python dependencies..."
pip install -r "$REPO_DIR/requirements.txt" --quiet

# Use the system pygame (see note above) instead of the PyPI wheel.
pip uninstall -y pygame --quiet 2>/dev/null || true

# Swap in the headless OpenCV build - the app never opens cv2's own GUI
# window (pygame owns the display), and headless skips the Qt/GTK deps
# that are a pain to install on Pi OS Lite.
pip uninstall -y opencv-python --quiet 2>/dev/null || true
pip install "opencv-python-headless>=4.8,<5.0" --quiet

# Arcade button support (config/config.py's GPIO_BUTTON_* pins). Classic
# RPi.GPIO doesn't support the GPIO chip on newer Pi OS/Pi 5 - rpi-lgpio
# is a drop-in replacement that installs itself as the `RPi.GPIO` module.
pip install rpi-lgpio --quiet

deactivate

# ── systemd service ───────────────────────────
echo "🛠  Installing systemd service..."
sudo tee "/etc/systemd/system/${SERVICE_NAME}.service" > /dev/null <<EOF
[Unit]
Description=Wedding Photo Booth
Wants=network-online.target
After=multi-user.target network-online.target

[Service]
Type=simple
User=${APP_USER}
WorkingDirectory=${REPO_DIR}/src
Environment=SDL_VIDEODRIVER=kmsdrm
Environment=SDL_AUDIODRIVER=alsa
Environment=PYTHONUNBUFFERED=1
ExecStartPre=/bin/sleep 5
ExecStart=${VENV_DIR}/bin/python3 ${REPO_DIR}/src/main.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}.service"

# ── Console auto-login ────────────────────────
# No keyboard/monitor needed after boot - the booth is meant to run
# headless, reachable only over SSH.
echo "🔓 Enabling console auto-login for ${APP_USER}..."
if command -v raspi-config &>/dev/null; then
  sudo raspi-config nonint do_boot_behaviour B2
else
  sudo mkdir -p /etc/systemd/system/getty@tty1.service.d
  sudo tee /etc/systemd/system/getty@tty1.service.d/autologin.conf > /dev/null <<EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin ${APP_USER} --noclear %I \$TERM
EOF
  sudo systemctl daemon-reload
fi

# ── Safe shutdown button ──────────────────────
# A momentary button wired between GPIO3 (physical pin 5) and any GND pin
# (e.g. pin 6, right next to it) triggers a clean shutdown at the kernel
# level - this works even if the photobooth app has frozen, unlike a
# software-only shutdown hook. Prevents SD card corruption from yanking
# the power cable to turn the booth off.
echo "🔌 Enabling GPIO3 safe-shutdown button..."
if [ -f /boot/firmware/config.txt ]; then
  CONFIG_TXT="/boot/firmware/config.txt"
else
  CONFIG_TXT="/boot/config.txt"
fi
if ! grep -q "^dtoverlay=gpio-shutdown" "$CONFIG_TXT"; then
  echo "dtoverlay=gpio-shutdown" | sudo tee -a "$CONFIG_TXT" > /dev/null
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "The photo booth will launch automatically on every boot."
echo ""
echo "Useful commands:"
echo "  sudo systemctl start ${SERVICE_NAME}     # launch now without rebooting"
echo "  sudo systemctl status ${SERVICE_NAME}    # check it's running"
echo "  journalctl -u ${SERVICE_NAME} -f         # live logs"
echo "  sudo systemctl stop ${SERVICE_NAME}      # stop it"
echo "  sudo systemctl disable ${SERVICE_NAME}   # stop launching it on boot"
echo ""
echo "⚠️  You were just added to the gpio/video/render/input groups, and both"
echo "   auto-login and the safe-shutdown button need a reboot to take effect:"
echo "     sudo reboot"
echo ""
echo "🔌 Safe shutdown: wire a momentary button between GPIO3 (physical pin 5)"
echo "   and GND (physical pin 6). A short press cleanly shuts the Pi down -"
echo "   wait for the green activity LED to stop blinking before unplugging"
echo "   power. Never just yank the power cable; it risks corrupting the SD"
echo "   card (lost Wi-Fi/network config, login settings, etc.)."
echo ""
echo "🖨  Printer: configure it once via CUPS's web UI, from another machine"
echo "   on the same network, at:"
echo "     http://$(hostname -I | awk '{print $1}'):631"
echo "   (first run: sudo cupsctl --remote-admin --remote-any WebInterface=yes)"
echo ""
