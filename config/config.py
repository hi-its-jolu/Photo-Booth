import os

# ── Paths ─────────────────────────────────────────────────────────────────────
PHOTOS_DIR = os.path.join(os.path.dirname(__file__), "..", "photos")

# ── Hardware ──────────────────────────────────────────────────────────────────
CAMERA_INDEX = 0           # OpenCV camera device index (0 = first/default camera)

# ── Session ───────────────────────────────────────────────────────────────────
TOTAL_PHOTOS       = 4     # number of photos per session
COUNTDOWN_SECONDS  = 3     # seconds on the countdown timer
PREVIEW_DURATION   = 1.5   # seconds to show each photo preview after capture
FLASH_DURATION     = 0.3   # seconds for the white flash effect

# ── Display ───────────────────────────────────────────────────────────────────
TARGET_FPS     = 30        # main loop frame rate

# ── Audio ─────────────────────────────────────────────────────────────────────
AUDIO_FREQ     = 44100     # sample rate (Hz)
AUDIO_SIZE     = -16       # bit depth (negative = signed)
AUDIO_CHANNELS = 2         # 1 = mono, 2 = stereo
AUDIO_BUFFER   = 512       # buffer size (smaller = lower latency)

# ── Thumbnails ────────────────────────────────────────────────────────────────
THUMB_HEIGHT        = 110  # px – height of in-session thumbnail strip
THUMB_PADDING       = 12   # px – gap between thumbnails
THUMB_MARGIN_BOTTOM = 15   # px – gap between thumbnails and screen bottom edge

# ── Grid (review screen) ──────────────────────────────────────────────────────
GRID_PAD           = 20    # px – padding around and between grid cells
GRID_ACTION_BAR_H  = 100   # px – space at bottom reserved for the action bar

# ── Preview ───────────────────────────────────────────────────────────────────
PREVIEW_SCALE = 0.75       # fraction of screen the single-photo preview fills

# ── Carousel (idle screen) ────────────────────────────────────────────────────
CAROUSEL_STRIP_HEIGHT = 180   # px – height of the scrolling photo strip
CAROUSEL_SCROLL_SPEED = 80    # px/s – how fast photos scroll left
CAROUSEL_PADDING      = 14    # px – gap between photos in the strip

# ── Printer ───────────────────────────────────────────────────────────────────
PRINTER_CHECK_INTERVAL = 10.0  # seconds between printer status polls

# ── Printing animation ────────────────────────────────────────────────────────
PRINT_COMPOSE_DUR = 0.7    # seconds – grid → polaroid crossfade
PRINT_HOLD_DUR    = 2.0    # seconds – hold polaroid before sliding away
PRINT_SLIDE_DUR   = 0.8    # seconds – polaroid accelerates off the bottom

# ── Print quantity ────────────────────────────────────────────────────────────
PRINT_QTY_DEFAULT = 1      # copies selected when a new session starts
PRINT_QTY_MIN     = 1      # minimum copies allowed
PRINT_QTY_MAX     = 4      # maximum copies allowed

# ── GPIO button mapping (BCM pin numbers) ─────────────────────────────────────
# Wiring: one leg of each button to the GPIO pin, other leg to GND.
# Set a pin to None to disable that button (e.g. during desktop development).
GPIO_BUTTON_START  = 17    # Green  – start session (idle) / skip countdown
GPIO_BUTTON_SNAP   = 27    # Yellow – same as START; useful as a second trigger
GPIO_BUTTON_PRINT  = 22    # Blue   – print polaroid (grid screen)
GPIO_BUTTON_RETAKE = 23    # Red    – retake / return to idle (grid screen)
GPIO_BUTTON_QTY_P  = 24    # Grey   - increase print qty maximum 4
GPIO_BUTTON_QTY_N  = 25    # Grey   - descrease print qty minimum 1