import pygame


def check_printer_connection():
    """Return True if the default system printer is online, False otherwise."""
    import subprocess

    try:
        # Get the default printer name
        result = subprocess.run(
            ["lpstat", "-d"],
            capture_output=True, text=True, timeout=5
        )
        # "no system default destination" → no default printer set
        if "no system default" in result.stdout.lower():
            return False

        # Extract printer name from "system default destination: <name>"
        parts = result.stdout.strip().split(":")
        if len(parts) < 2:
            return False
        printer_name = parts[-1].strip()

        # Check whether that printer is idle/processing (i.e. reachable)
        status = subprocess.run(
            ["lpstat", "-p", printer_name],
            capture_output=True, text=True, timeout=5
        )
        output = status.stdout.lower()
        return "idle" in output or "processing" in output

    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False

def draw_printer_warning(surf):
    """Draw a printer icon + 'No Printer Found.' warning in the top-left corner."""
    ox, oy = 14, 14
    c = (255, 80, 80)
    # Paper feed slot (top)
    pygame.draw.rect(surf, c, (ox + 8, oy,      14, 5))
    # Printer body
    pygame.draw.rect(surf, c, (ox,     oy + 5,  30, 18))
    # Output slot cut-out
    pygame.draw.rect(surf, (20, 20, 20), (ox + 5, oy + 13, 20, 4))
    # Paper output (bottom)
    pygame.draw.rect(surf, c, (ox + 8, oy + 23, 14, 7))
    # Label text
    font = pygame.font.SysFont(None, 36)
    text = font.render("No Printer Found.", True, c)
    surf.blit(text, text.get_rect(left=ox + 38, centery=oy + 16))


def check_printer_ink():
    """Check printer ink and if low send warning to screen"""
    pass

def check_printer_paper():
    """Check printer paper and if low send warning to screen"""
    pass

def print_photos(photo_paths):
    """Send all photos to the system printer. Implementation TBD."""
    pass
