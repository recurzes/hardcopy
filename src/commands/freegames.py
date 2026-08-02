"""
freegames.py — Free Games Loot Drop

Fetches currently active free game giveaways from the GamerPower API
and prints a thermal receipt grouped by platform, with a QR code per
game that links directly to its claim page.

Usage:
    python -m src.commands.freegames
    python -m src.commands.freegames --platform steam
    python -m src.commands.freegames --max 5
    python -m src.commands.freegames --no-qr
"""

from __future__ import annotations

import argparse
import textwrap
from datetime import datetime

import qrcode
import requests
from PIL import Image

from src.config import MAX_WIDTH
from src.printer import get_printer, print_centered

# ---------------------------------------------------------------------------
# GamerPower API
# ---------------------------------------------------------------------------

GAMERPOWER_API = "https://www.gamerpower.com/api/giveaways"

# Map API slugs -> human-readable platform labels
PLATFORM_LABELS: dict[str, str] = {
    "steam": "Steam",
    "epic-games-store": "Epic Games Store",
    "gog": "GOG",
    "itch.io": "itch.io",
    "ps4": "PlayStation 4",
    "ps5": "PlayStation 5",
    "xbox-one": "Xbox One",
    "xbox-series-xs": "Xbox Series X/S",
    "switch": "Nintendo Switch",
    "android": "Android",
    "ios": "iOS",
    "pc": "PC",
    "drm-free": "DRM-Free",
}

# Platform priority order for receipt (most popular first)
PLATFORM_ORDER = [
    "epic-games-store",
    "steam",
    "gog",
    "ps5",
    "ps4",
    "xbox-series-xs",
    "xbox-one",
    "switch",
    "android",
    "ios",
    "itch.io",
    "drm-free",
    "pc",
]


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def fetch_free_games(platform: str | None = None) -> list[dict]:
    """Fetch active game giveaways from GamerPower API."""
    params: dict[str, str] = {"type": "game"}
    if platform:
        params["platform"] = platform

    try:
        resp = requests.get(GAMERPOWER_API, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.ConnectionError:
        raise RuntimeError("No internet connection. Cannot reach GamerPower API.")
    except requests.exceptions.Timeout:
        raise RuntimeError("GamerPower API timed out. Try again later.")
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"GamerPower API returned an error: {e}")
    except Exception as e:
        raise RuntimeError(f"Unexpected error fetching giveaways: {e}")

    # API returns a dict with status 0 when there are no results
    if isinstance(data, dict) and data.get("status") == 0:
        return []

    if not isinstance(data, list):
        return []

    # Keep only active game giveaways
    active = [g for g in data if g.get("status", "").lower() == "active"]
    return active


def group_by_platform(games: list[dict]) -> dict[str, list[dict]]:
    """Group games by their platform slug."""
    groups: dict[str, list[dict]] = {}
    for game in games:
        platform = game.get("platforms", "pc").strip().lower()
        groups.setdefault(platform, []).append(game)
    return groups


def sorted_platform_keys(groups: dict[str, list[dict]]) -> list[str]:
    """Return platform keys in preferred display order."""
    ordered = [p for p in PLATFORM_ORDER if p in groups]
    # Append any unknown platforms not in the priority list
    remaining = [p for p in groups if p not in PLATFORM_ORDER]
    return ordered + sorted(remaining)


# ---------------------------------------------------------------------------
# QR code generation
# ---------------------------------------------------------------------------

def make_qr_image(url: str) -> Image.Image:
    """Generate a small PIL Image of a QR code for the given URL."""
    qr = qrcode.QRCode(
        version=None,           # auto-size
        error_correction=qrcode.constants.ERROR_CORRECT_L,  # smallest code
        box_size=3,             # 3px per module -- fits 58mm roll
        border=2,               # quiet zone modules
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    return img.convert("RGB")


# ---------------------------------------------------------------------------
# Receipt printing helpers
# ---------------------------------------------------------------------------

SEPARATOR = "-" * MAX_WIDTH
THICK_SEP = "=" * MAX_WIDTH


def print_platform_header(p, label: str) -> None:
    p.text("\n")
    p.set(align="center", bold=True, font="a")
    p.text(f"[ {label.upper()} ]\n")
    p.set(align="left", bold=False, font="a")


def print_game_entry(p, game: dict, include_qr: bool) -> None:
    """Print a single game entry with optional QR code."""
    title: str = game.get("title", "Unknown Game")
    url: str = game.get("open_giveaway_url", game.get("giveaway_url", ""))
    end_date: str = game.get("end_date", "N/A").strip()

    # Friendly expiry label
    if end_date in ("", "N/A"):
        expiry_label = "Permanent"
    else:
        expiry_label = f"Ends: {end_date}"

    # Wrap the title to fit MAX_WIDTH with "> " prefix
    available = MAX_WIDTH - 2
    wrapped = textwrap.wrap(title, width=available)

    p.set(align="left", bold=True, font="a")
    if wrapped:
        p.text(f"> {wrapped[0]}\n")
        for line in wrapped[1:]:
            p.text(f"  {line}\n")
    else:
        p.text("> ???\n")

    p.set(align="left", bold=False, font="a")
    p.text(f"  {expiry_label}\n")

    if include_qr and url:
        try:
            img = make_qr_image(url)
            p.set(align="center")
            p.image(img, impl="bitImageRaster", center=True)
            p.set(align="left")
        except Exception as e:
            p.text(f"  [QR error: {e}]\n")

    p.text("\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Print currently free games as a Loot Drop receipt"
    )
    parser.add_argument(
        "--platform",
        metavar="SLUG",
        default=None,
        help=(
            "Filter to a specific platform slug "
            "(e.g. steam, epic-games-store, ps5, switch). "
            "Default: all platforms."
        ),
    )
    parser.add_argument(
        "--max",
        metavar="N",
        type=int,
        default=None,
        dest="max_games",
        help="Maximum number of games to print. Default: all.",
    )
    parser.add_argument(
        "--no-qr",
        action="store_true",
        help="Skip QR code generation (faster, text-only receipt).",
    )
    args = parser.parse_args(argv)

    # -- Fetch ---------------------------------------------------------------
    print("Fetching free games from GamerPower...")
    try:
        games = fetch_free_games(platform=args.platform)
    except RuntimeError as e:
        print(f"Error: {e}")
        return

    if not games:
        print("No active free game giveaways found right now. Check back later!")
        return

    # Apply --max cap
    if args.max_games and args.max_games > 0:
        games = games[: args.max_games]

    total = len(games)
    print(f"Found {total} free game(s). Connecting to printer...")

    # -- Printer -------------------------------------------------------------
    p = get_printer()
    if not p:
        return

    try:
        # -- Header ----------------------------------------------------------
        p.text("\n")
        print_centered(p, THICK_SEP)
        print_centered(p, "*** LOOT DROP ***")
        print_centered(p, datetime.now().strftime("%Y-%m-%d  %H:%M"))
        print_centered(p, THICK_SEP)
        p.text("\n")

        if args.no_qr:
            p.set(align="center", bold=False, font="a")
            p.text("(QR codes disabled)\n")

        # -- Games grouped by platform ---------------------------------------
        groups = group_by_platform(games)
        for platform_slug in sorted_platform_keys(groups):
            label = PLATFORM_LABELS.get(platform_slug, platform_slug.title())
            print_platform_header(p, label)
            for game in groups[platform_slug]:
                print_game_entry(p, game, include_qr=not args.no_qr)

        # -- Footer ----------------------------------------------------------
        p.set(align="left", bold=False, font="a")
        p.text(SEPARATOR + "\n")
        p.set(align="center", bold=False, font="a")
        p.text("Powered by GamerPower.com\n")
        p.set(bold=True)
        p.text(f"Total: {total} free game(s)\n")
        p.set(bold=False)
        p.text(SEPARATOR + "\n")
        p.text("\n\n")

        p.cut()
        p.close()
        print(f"Done! Printed {total} free game(s).")

    except Exception as e:
        print(f"Printer error: {e}")
        print("Tip: Check if the printer is connected and permissions are set.")


if __name__ == "__main__":
    main()
