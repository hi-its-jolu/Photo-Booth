# Handoff: Photo Booth — booth UI (home + preview) and event gallery

## Overview

Four approved screens across two surfaces.

**On the booth (Python / pygame, 1920×1080 fullscreen):**

- **Home / idle** — `2b`: live camera viewfinder, scrolling carousel of photos taken earlier, one call to action (green arcade button), plus a gallery QR top-right.
- **Photo preview / review** — `1d`: the 4 photos just taken, a copies stepper, print, discard, and a QR to download that session.

**On the guest's phone (web — what the QR codes open):**

- **Gallery index** — `3a`: every photo from the event, grouped by booth session.
- **Single photo** — `3b`: one photo with the download stack.

The two surfaces are separate builds. The pygame screens go in the existing app; the gallery is a new web front end (stack is your call — it only needs to list sessions and serve files).

Both booth screens are designed at **1920 × 1080 (16:9), fullscreen, no cursor**. Primary input is **GPIO arcade buttons** (see `config/config.py`), so the UI never relies on hover or pointer affordances — the on-screen controls are *pictures of the physical buttons*, laid out in the same left-to-right order as the caps on the panel.

## About the Design Files

`Photobooth Preview.dc.html` in this bundle is a **design reference created in HTML** — a prototype showing intended look and behaviour, not production code to copy. The target codebase is the existing **Python / pygame** app (`src/screens.py`, `src/main.py`, `src/composite.py`, `config/config.py`). The task is to **re-implement these designs as pygame draw routines** inside that app's existing structure (a `render_*` function per screen in `screens.py`, tunables added to `config/config.py`) — not to embed HTML.

Open the HTML file in a browser to see the designs. It is a canvas of screens, each labelled with its id badge in the top-left of its caption. Every screen in the file is **approved** — rejected explorations have been removed:

| id | Screen | Platform |
|---|---|---|
| `1d` | Photo preview / review | pygame, 1920×1080 |
| `2b` | Home / idle | pygame, 1920×1080 |
| `3a` | Event gallery — index | web, phone-first |
| `3b` | Event gallery — single photo | web, phone-first |

## Fidelity

**High-fidelity.** Colours, type sizes, weights, letter-spacing and pixel geometry below are final and should be matched. Where a value here disagrees with the HTML, this README wins.

---

## Design tokens

From the Modernist design system. Add these to `config/config.py` (or a new `config/theme.py`) as RGB tuples.

| Token | Hex | RGB | Use |
|---|---|---|---|
| `GROUND` | `#f3f2f2` | 243,242,242 | page background (light screens) |
| `INK` | `#201e1d` | 32,30,29 | text, 2px rules, borders, discard cap |
| `ACCENT` | `#ec3013` | 236,48,19 | print cap, urgent timer, live dot |
| `ACCENT_DARK` | `#b81f08` | 184,31,8 | print cap outline + 8px drop |
| `NEUTRAL_200` | `#e2e0de` | 226,224,222 | bottom rail fill |
| `NEUTRAL_400` | `#b6b3b0` | 182,179,176 | 6px drop under white caps |
| `NEUTRAL_500` | `#8a8784` | 138,135,132 | 6px drop under discard cap |
| `NEUTRAL_600` | `#6e6b68` | 110,107,104 | small label text |
| `NEUTRAL_700` | `#524f4d` | 82,79,77 | stepper cap labels |
| `GREEN` | `#3f9b4f` | 63,155,79 | start cap (home screen) |
| `GREEN_DARK` | `#256034` | 37,96,52 | drop under start cap |
| `WHITE` | `#ffffff` | | photo mats, QR, stepper caps |

**Type** — Archivo (bundle the TTF into `assets/` and load with `pygame.font.Font`, replacing `pygame.font.SysFont(None, …)`). Weights used: 600, 700, 800. **No rounded corners anywhere** except the round button caps. **Rules are 2px**, never 1px.

Note on sizes: all `px` figures below are pixel heights at 1920×1080, i.e. `pygame.font.Font(archivo, px)` — not pygame's legacy `SysFont` size argument.

**Spacing** — outer margin `56px` on all sides. Nothing but the bottom rail and the top header may enter that margin.

---

## Screen 1 — Home / idle (`2b`)

**Purpose:** attract, show people they're on camera, and make it obvious that pressing the green button starts a session. Replaces `render_idle` in `screens.py`.

### Layout (top to bottom)

1. **Header** — `y 40`, from `x 56` to `x 1864`.
   - Left: `assets/logo_wedding.png`, height `104px`, aspect preserved. Then `34px` gap, a `14×14` square in `ACCENT` (pulsing, see below), `14px` gap, then the word **LIVE** — `19px / 700 / letter-spacing .20em / NEUTRAL_600`.
   - Right, flush right: a **gallery QR** block — two right-aligned text lines, `18px` gap, then the code:
     - **SEE EVERY PHOTO / FROM TONIGHT** (two lines) — `24px / 800 / INK / line-height 1.25`
     - **SCAN FOR THE GALLERY** — `17px / 700 / .18em / NEUTRAL_600`, `6px` below
     - QR: **112 × 112** white square, `2px INK` border, `7px` inner padding (bitmap `98 × 98`).
   - This QR points at the **whole-event gallery**, not one session — so guests who didn't print can still get their photos. Different URL from the preview screen's per-session QR; generate once at startup, it never changes.
2. **Rule** — `2px` `INK`, `x 56 → 1864`, `y 170`.
3. **Viewfinder** — centred in the band `y 212 … 772`. Box **996 × 560**, black fill, `2px INK` border. The live camera frame fills it (`object-fit: cover` equivalent: scale to cover, centre-crop) and is **mirrored horizontally** — keep the existing mirror.
   - Four white corner ticks *inside* the box, `2px` thick × `44px` long, one pair per corner (one horizontal + one vertical arm flush to each corner).
4. **Carousel label row** — baseline at `y 800`, `x 56 → 1864`, both `18px / 700 / .22em / NEUTRAL_600`:
   - left: `EARLIER TONIGHT`
   - right: `<n> PHOTOS SO FAR` — count of files in `PHOTOS_DIR` (the mock shows `312 PHOTOS SO FAR`).
5. **Carousel strip** — `x 56 → 1864`, `y 836`, height `132px`, with a `2px INK` rule on the **top and bottom** edges. Thumbnails **224 × 126** (16:9), `12px` gap, `6px` inset from the top rule, clipped to the strip. Scrolls right-to-left, looping seamlessly.
   - Existing `load_carousel_photos(126)` + `CAROUSEL_PADDING = 12`; set `CAROUSEL_STRIP_HEIGHT = 132`.
   - Speed: the mock loops a 1888px-wide set of 8 thumbnails in 40s ≈ **47 px/s**. Set `CAROUSEL_SCROLL_SPEED = 47` (currently 80 — noticeably too fast at this size).
6. **Bottom rail** — full width, `y 988 → 1080` (height `92px`), fill `NEUTRAL_200`, `2px INK` top rule, horizontal padding `56px`, contents vertically centred:
   - Left, flush left: **PRESS THE GREEN BUTTON — 4 PHOTOS, ABOUT 30 SECONDS** — `30px / 800 / INK`.
   - Right: a **58px-diameter** circle, fill `GREEN`, `2px INK` outline, `4px` solid drop shadow in `GREEN_DARK` directly below (draw a second circle offset `+4px` in y, behind). Then `16px` gap, then **START** — `22px / 800 / .16em / INK`.

### Behaviour

- **Live dot** and **start cap** both pulse: opacity 1 → 0.55 → 1 over **1.6–1.8s**, ease-in-out. In pygame, modulate alpha with `0.775 + 0.225 * sin(2π t / 1.7)`.
- Carousel advances by `SCROLL_SPEED * dt`, modulo total strip width — the current `render_idle` implementation is correct, only the constants change.
- Green button (`GPIO_BUTTON_START` = pin 17, or `SPACE`) → countdown / capture phase.
- Carousel photo list should be re-read at the start of each idle period (`_reset_carousel()` already does this) so the last session's photos appear.
- `ESC quit` hint from the old screen is **removed** from the guest-facing UI.

---

## Screen 2 — Photo preview / review (`1d`)

**Purpose:** show the 4 photos just taken, pick a number of copies, print or discard, or scan to download. Auto-returns to idle on timeout. Replaces `render_grid`.

### Layout (top to bottom)

1. **Countdown, top-left** — a **112 × 112** square plate at `x 56, y 44`.
   - Fill `INK` normally, **`ACCENT` when urgent**. Numeral centred inside: **60px / 800 / `#f3f2f2`**, zero-padded to two digits (`23`, `09`).
   - To its right, `18px` gap: two lines, `19px / 700 / .20em / line-height 1.45`:
     - line 1 `SECONDS TO DECIDE` in `NEUTRAL_600`
     - line 2 `PRINT IT OR LET IT GO` in `INK`
   - **Urgent state:** at **≤ 10 s** the whole plate (fill + numeral) **flashes** — hard on/off, `0.7s` period, `50%` duty (`steps(1)`, not a fade): visible for 350ms, then drawn at 18% opacity for 350ms. Add `PREVIEW_URGENT_AT = 10` to config; total timeout stays 25s (`_GRID_TIMEOUT_SECS`).
   - The old `returning in` label and grey numeral are removed.
2. **Countdown bar** — `x 56 → 1864`, `y 166`, height `10px`. Track `NEUTRAL_300`; fill from the left, `time_left / 25` of the width, in `INK` — **`ACCENT` when urgent**. Replaces the old 80×4 bar.
3. **Rule** — `2px INK`, `x 56 → 1864`, `y 184`.
3. **Photo grid** — the block `x 56 → 1864`, `y 228 … 796`; the grid itself is **1000 × 568**, horizontally centred (so `x 516 … 1516`), 2 columns × 2 rows, **22px gap**.
   - Each cell: `2px INK` border, white fill, **10px inner padding** (a white mat), photo fills the remaining area, scale-to-cover + centre-crop, no rounding, no drop shadow.
   - Cell outer size = `(1000 - 22)/2 × (568 - 22)/2` = **489 × 273**; photo area **469 × 253**.
   - `assets/logo_wedding.png` at **340px wide**, aspect preserved, centred over the middle of the grid (over the 22px gutters).
   - Order is capture order: 1 top-left, 2 top-right, 3 bottom-left, 4 bottom-right. **Photos cannot be individually deselected** — all 4 always print.
4. **Bottom rail** — full width, `y 836 → 1080` (height `244px`), fill `NEUTRAL_200`, `2px INK` top rule, horizontal padding `56px`. Three zones, vertically centred; left group flush left, centre group centred on the screen's horizontal centre (`x 960`), right group flush right.

   **Left — copies stepper.** Two **96px** white circle caps, `2px INK` outline, `6px` drop in `NEUTRAL_400`, `14px` apart, bottom-aligned with each other:
   - cap 1 glyph: a `38 × 7` `INK` bar (minus). Label under it, `10px` below: **FEWER** — `17px / 700 / .16em / NEUTRAL_700`.
   - cap 2 glyph: the same bar plus a `7 × 38` vertical bar (plus). Label: **MORE**.
   - Then `26px` gap, a **2px `INK` vertical divider** the height of the text block, then `26px` padding, then:
     - **COPIES** — `18px / 700 / .20em / NEUTRAL_600`
     - the quantity numeral — **76px / 800 / INK**, and beside its baseline `COPY` / `COPIES` — `24px / 700 / .12em / NEUTRAL_700`.
   - Range `PRINT_QTY_MIN` 1 … `PRINT_QTY_MAX` 4. At a bound, the corresponding cap drops to **45% opacity** (glyph and outline) and its press is a no-op.
   - Buttons: `GPIO_BUTTON_QTY_N` pin 25 (fewer) / `GPIO_BUTTON_QTY_P` pin 24 (more) → `LEFT` / `RIGHT`.

   **Centre — QR.** A **140 × 140** white square with `2px INK` border and `8px` inner padding, so the QR bitmap itself is `124 × 124` — centred on `x 960`. `10px` below, centred: **SCAN TO DOWNLOAD** — `19px / 700 / .20em / INK`. Raise `_QR_SIZE` from 110 to **124**. Nothing else may occupy the centre of the rail.

   **Right — actions**, bottom-aligned, `28px` apart, in this left-to-right order (matching the physical panel):
   - **Discard**: **112px** circle, fill `INK`, `2px INK` outline, `6px` drop in `NEUTRAL_500`. Glyph: a white X — two `44 × 6` bars crossed at ±45°, centred. Label `10px` below, centred: **DISCARD** — `19px / 800 / .16em / INK`.
   - **Print**: **148px** circle, fill `ACCENT`, `2px ACCENT_DARK` outline, `8px` drop in `ACCENT_DARK`. Word **PRINT** inside — `30px / 800 / .06em / #ffffff`. Label `10px` below: **PRINT 2 COPIES** (i.e. `PRINT {n} COPY|COPIES`, uppercase) — `19px / 800 / .16em / INK`.
   - Print is deliberately the largest target on screen; discard is second; the stepper caps are smallest.

### Behaviour

- Entered after the 4th photo is captured. Countdown starts at **25s**; on expiry → discard the session and return to idle (existing `_GRID_TIMEOUT_SECS` behaviour).
- Print (`GPIO_BUTTON_PRINT` pin 22 / `P`) → existing printing animation for `qty` copies, then idle.
- Discard (`GPIO_BUTTON_RETAKE` pin 23 / `DELETE`) → straight back to idle. **No confirmation dialog** in this version.
- Stepper changes redraw only the quantity numeral, the word `COPY/COPIES` and the print cap's label.
- Any button press should **not** reset the countdown, except the stepper (arguable — confirm with design; the mock assumes it does not).
- No printer / low ink is not part of this screen; keep the existing top-right status card behaviour if desired, but it must not enter the photo grid area.

### Arcade cap colours to order

| Action | Cap colour | Pin |
|---|---|---|
| Start (home) | green | 17 (+ 27 as second trigger) |
| Print | **red** | 22 |
| Discard | **black** | 23 |
| Fewer / More copies | **white** ×2 | 25 / 24 |

The on-screen circles must match these colours and sizes-by-importance, and sit in the same order as the caps on the panel.

---

## Screen 3 — Event gallery, index (`3a`)

**Purpose:** what the home screen's QR opens. A guest who didn't print (or lost the print) finds their own set and saves it. **New web front end** — no account, no login, no app; the URL is the whole key. Designed at **430 × 932** (phone). Scale up gracefully for tablet/desktop by widening the grid; the layout below is the phone spec.

### Layout (top to bottom)

1. **Header** — `padding 14px 22px 18px`, `2px INK` bottom rule.
   - **TONIGHT'S PHOTOS** — `30px / 800 / -.01em / line-height 1`.
   - `8px` below: a `9×9` `ACCENT` square, `8px` gap, **312 PHOTOS** (live count) — `13px / 700 / .14em / NEUTRAL_600`. Static, not pulsing.
   - No logo in this header (deliberately removed — it crowded the title).
2. **Utility row** — height `56px`, `22px` side padding, `2px NEUTRAL_300` bottom rule. Two equal-width buttons, `10px` apart, each `36px` tall with a `2px INK` outline and a **flush-left** label at `12px` padding, `13px / 700 / .14em`: **SELECT PHOTOS** and **FIND MY SESSION**.
   - `FIND MY SESSION` → the session-lookup affordance (by time, or by scanning the QR on their print). Behaviour not designed yet; confirm before building.
3. **Session groups** — scrolling list, `22px` side padding, newest session first. Each group:
   - **Group header** — `16px` top padding, `10px` bottom: session time (e.g. **10:42 PM**) `13px / 800 / .16em / INK` flush left; **4 PHOTOS · 1 STRIP** `12px / 700 / .14em / NEUTRAL_600` flush right.
   - **Photo grid** — 2 columns, `8px` gap, each thumbnail `100% × 106px`, scale-to-cover. Capture order, left-to-right, top-to-bottom. Tapping one opens `3b`.
   - **Session download** — `8px` below the grid, height `52px`, fill `ACCENT`, white text. Left `14px` padding: a `17px` download glyph (down arrow onto a baseline), `12px` gap, **DOWNLOAD ALL 4 + STRIP** `17px / 800`, `white-space: nowrap`. At the right end, `8px` from the edge, a `52 × 36` thumbnail of that session's printed strip — it shows what "+ STRIP" means.
   - Groups after the first are separated by a `2px NEUTRAL_300` top rule with `18px` margin above.
   - **There is no global "download all" button** — explicitly cut. Download is always per-session or per-photo.

## Screen 4 — Event gallery, single photo (`3b`)

**Purpose:** one photo, full size, with an unambiguous download stack. Dark ground so the photo carries the screen. `430 × 932`, ground `#141312`, text `#f3f2f2`.

### Layout (top to bottom)

1. **Top bar** — height `56px`, `22px` side padding. Left: a `12px` back chevron (`3px` strokes, rotated 45°), `12px` gap, **ALL PHOTOS** `13px / 800 / .16em`. Right: **3 / 312** `13px / 700 / .14em / #a8a5a2`.
2. **Photo** — full width `430px`, height `322px`, black fill, scale-to-cover. Swipe left/right moves within the session, then across sessions.
3. **Session strip** — `x 22`, `44px` under the photo: **10:42 PM · PHOTO 3 OF 4** `13px / 800 / .16em`. `14px` below, a row of `70 × 48` thumbnails, `8px` apart: the session's 4 photos **plus the printed strip** as a 5th item. Non-current items at `50%` opacity; the current one gets a `3px ACCENT` inset outline.
4. **Download stack** — `x 22`, width `386px`, `10px` between rows, every label **flush left** at `16px` padding, all `19px / 800`:
   - **DOWNLOAD THIS PHOTO** — height `60px`, fill `ACCENT`, white text, `20px` download glyph then `12px` gap.
   - **DOWNLOAD ALL 4 + STRIP** — height `60px`, `2px #6d6a67` outline, no fill.
   - **SHARE** — height `60px`, `2px #6d6a67` outline. Native share sheet.
   - `4px` below: **FULL RESOLUTION · SAVES STRAIGHT TO YOUR CAMERA ROLL** — two lines, `13px / 700 / .12em / #a8a5a2 / line-height 1.5`.

### Gallery behaviour

- **Grouping is by session, not by day** — a session is the 4 photos from one run plus its composited strip. Group them on the server from the capture timestamps; the existing filenames already encode this (`photo_YYYYMMDD_HHMMSS_{1..4}.jpg` + `print_YYYYMMDD_HHMMSS.jpg`).
- Multi-file download should produce **individual full-resolution files in the camera roll**, not a zip, on iOS Safari and Android Chrome. This is the one genuinely tricky part of the build — validate it early on real devices; if a browser won't allow it, fall back to a sequential save with a progress state.
- Progress + confirmation states were designed and then cut from the canvas. Implement something plain ("2 of 4 photos", then "Saved to your photos") and I'll design them properly if the built version feels rough.
- New photos should appear without a manual refresh (poll or SSE) — guests keep the page open between sessions.
- Not designed yet, ask before inventing: the empty state (someone scans before any photos exist), any delete/report path, and the desktop width.

---

## State

Both screens are already covered by the existing state machine; the new/changed state is:

- `carousel_photos`, `carousel_start_time` — unchanged, new constants.
- `photo_count` — number of files in `PHOTOS_DIR`, for `N PHOTOS SO FAR`. Cheap to compute once per idle entry.
- `print_qty` (1…4), `preview_deadline` (monotonic), `qr_surf` — unchanged.
- `urgent = time_left <= PREVIEW_URGENT_AT`, and a flash phase derived from `time.monotonic()`.

## Assets

- `assets/logo_wedding.png` — existing repo asset, used on both screens (104px tall on home, 340px wide over the preview grid).
- `assets/p1–p4.jpg` — the 4 photos of one real session (Aug 29, 14:54) with `assets/print.jpg` as its composited strip; `q1–q4.jpg` + `print2.jpg` and `r1–r4.jpg` are two further real sessions, used for `3a`'s second group and `2b`'s carousel. **The home screen's viewfinder in the mock is a still frame** standing in for the live camera surface.
- Archivo (400/600/700/800) must be added to `assets/` — the mocks assume it; `SysFont(None, …)` will not match.
- Lucide is the icon set of record, but both screens need no icons: every glyph is a rectangle, a circle or crossed bars.
- QR generation is unchanged (`src/qr.py`), only the size. Two distinct codes: the home screen's **event gallery** URL (generated once at startup, `98 × 98`) and the preview screen's **per-session** download URL (`124 × 124`).

## Files

- `Photobooth Preview.dc.html` — the design canvas. Every screen in it is approved: **`1d`** (preview), **`2b`** (home), **`3a`** + **`3b`** (gallery). Rejected explorations have been deleted, so there is nothing in the file to ignore.
- `assets/` — logo, real session photos and printed strips referenced by the HTML.
