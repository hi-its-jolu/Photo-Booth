# Photo Booth

A Python-based photo booth running on macOS for development and targeting Raspberry Pi for deployment. Captures a configurable number of photos with a countdown, displays a live preview, and supports printing.

## Features

- Fullscreen live camera feed (mirrored)
- Countdown timer with white flash on capture
- Per-photo preview after each shot
- Thumbnail strip showing photos taken so far
- Grid review of all photos with print / retake options
- Printer support (stub — implementation TBD)

## Project Structure

```
photo booth/
├── src/
│   ├── booth.py          # Main application & state machine
│   ├── image.py          # Camera capture & image processing
│   └── printer.py        # Print helpers (stub)
├── config/
│   └── config.py         # Tunable 
├── requirements.txt
└── setup.sh
```

## Requirements

- Python 3.10+
- macOS with Homebrew (for SDL2)
- A webcam accessible at index 0

## Setup

```bash
chmod +x setup.sh
./setup.sh
```

The script will:
1. Check for Python 3 and Homebrew
2. Create a `.venv` virtual environment
3. Install SDL2 via Homebrew (macOS only)
4. Install Python dependencies (`opencv-python`, `Pillow`, `pygame`)

## Running

```bash
source .venv/bin/activate
cd src
python booth.py
```

## Controls

| Key | Action |
|-----|--------|
| `Space` | Start a new session (idle) / skip countdown |
| `P` | Print all photos (grid screen) |
| `Delete` / `Backspace` | Retake — discard session and return to idle |
| `Escape` | Quit |

## Configuration

Edit [config/config.py](config/config.py) to adjust behaviour:

| Setting | Default | Description |
|---------|---------|-------------|
| `TOTAL_PHOTOS` | `4` | Number of photos per session |
| `COUNTDOWN_SECONDS` | `3` | Countdown duration |
| `PREVIEW_DURATION` | `1.5` | Seconds to show each photo preview |
| `FLASH_DURATION` | `0.3` | White flash duration after capture |
| `THUMB_HEIGHT` | `110` | Thumbnail strip height (px) |
| `PHOTOS_DIR` | `photos/` | Where captured photos are saved |
