#!/bin/bash
set -e

# ─────────────────────────────────────────────
# Wedding Photo Booth - Setup Script
# Run this on your Mac for local dev/testing.
# A separate Pi setup will be added later.
# ─────────────────────────────────────────────

OS="$(uname -s)"

echo ""
echo "🎉 Wedding Photo Booth Setup"
echo "────────────────────────────"
echo "Platform: $OS"
echo ""

# ── Python check ──────────────────────────────
if ! command -v python3 &>/dev/null; then
  echo "❌ Python3 not found. Install it from https://python.org"
  exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "✅ Python $PYTHON_VERSION found"

# ── Virtual environment ───────────────────────
if [ ! -d ".venv" ]; then
  echo "📦 Creating virtual environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate
echo "✅ Virtual environment activated"

# ── Pip upgrade ───────────────────────────────
pip install --upgrade pip --quiet

# ── Mac-specific SDL2 (needed by pygame) ──────
if [ "$OS" = "Darwin" ]; then
  if ! command -v brew &>/dev/null; then
    echo "❌ Homebrew not found. Install it from https://brew.sh"
    exit 1
  fi

  echo "🍺 Installing SDL2 via Homebrew..."
  brew install sdl2 sdl2_image sdl2_mixer sdl2_ttf --quiet || true
fi

# ── Python dependencies ───────────────────────
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt --quiet

echo ""
echo "✅ Setup complete!"
echo ""
echo "To start the photo booth:"
echo "  source .venv/bin/activate"
echo "  pibooth --config config/pibooth.cfg"
echo ""
