import os

# ── Paths ─────────────────────────────────────────────────────────────────────
PHOTOS_DIR  = os.path.join(os.path.dirname(__file__), "..", "photos")
PRINTS_DIR  = os.path.join(os.path.dirname(__file__), "..", "prints")
ASSETS_DIR  = os.path.join(os.path.dirname(__file__), "..", "assets")

# ── Hardware ──────────────────────────────────────────────────────────────────
CAMERA_INDEX = 0           # OpenCV camera device index (0 = first/default camera)

# Some UVC webcams (this one included) come up under Linux/V4L2 with very
# conservative saturation/contrast defaults, giving a washed-out image even
# though the hardware is fine. 0-255, matching the driver's own range (check
# with `v4l2-ctl -d /dev/video0 --list-ctrls`). Set to None to leave the
# driver default alone (e.g. on macOS, where these props don't apply).
# Left at None: raising these pushed this camera's auto-exposure/white
# balance into a bad state (strong blue cast on faces against a plain
# background) that a software white-balance correction couldn't fully fix.
CAMERA_SATURATION = None
CAMERA_CONTRAST   = None

# Software saturation boost instead (applied to already-captured frames, so
# it never touches the camera's own auto-exposure/white-balance and can't
# trigger the issue above). 1.0 = no change; None to disable. 1.7 tested as
# vivid but clean - much above ~2.0 starts amplifying JPEG noise into visible
# color speckling.
CAMERA_SATURATION_BOOST = None

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
PREVIEW_SCALE = .75       # fraction of screen the single-photo preview fills

# ── Carousel (idle screen) ────────────────────────────────────────────────────
CAROUSEL_STRIP_HEIGHT = 200   # px – height of the scrolling photo strip
CAROUSEL_SCROLL_SPEED = 47    # px/s – how fast photos scroll left
CAROUSEL_PADDING      = 12    # px – gap between photos in the strip

# ── Preview / review screen (grid) ────────────────────────────────────────────
PREVIEW_URGENT_AT = 10        # seconds left at which the countdown plate starts flashing

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
# POC wiring keeps all six buttons on one side of the 40-pin header.
GPIO_BUTTON_START  = 22    # Green – start session (idle) / skip countdown / snap
GPIO_BUTTON_SNAP   = 26    # Green – twin button, one per side (L/R hand access + redundancy), same action as START
GPIO_BUTTON_PRINT  = 6     # Blue  – print polaroid (grid screen)
GPIO_BUTTON_RETAKE = 5     # Red   – retake / return to idle (grid screen)
GPIO_BUTTON_QTY_P  = 17    # White - increase print qty maximum 4
GPIO_BUTTON_QTY_N  = 27    # White - descrease print qty minimum 1

# ── Design tokens (Modernist design system) ───────────────────────────────────
# From docs/design/README.md — home (2b) and preview/review (1d) screens.
GROUND       = (243, 242, 242)  # page background (light screens)
INK          = ( 32,  30,  29)  # text, 2px rules, borders, discard cap
ACCENT       = (236,  48,  19)  # print cap, urgent timer, live dot
ACCENT_DARK  = (184,  31,   8)  # print cap outline + 8px drop
NEUTRAL_200  = (226, 224, 222)  # bottom rail fill
NEUTRAL_300  = (204, 202, 199)  # countdown bar track (interpolated 200->400; exact token not in the design bundle)
NEUTRAL_400  = (182, 179, 176)  # 6px drop under white caps
NEUTRAL_500  = (138, 135, 132)  # 6px drop under discard cap
NEUTRAL_600  = (110, 107, 104)  # small label text
NEUTRAL_700  = ( 82,  79,  77)  # stepper cap labels
GREEN        = ( 63, 155,  79)  # start cap (home screen)
GREEN_DARK   = ( 37,  96,  52)  # drop under start cap
WHITE        = (255, 255, 255)  # photo mats, QR, stepper caps