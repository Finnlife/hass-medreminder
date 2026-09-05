"""Derive the Home Assistant brand icons from the panel logo.

Since Home Assistant 2026.3 a custom integration can ship its own brand images
in a `brand/` directory, and those take priority over the brands CDN. This is
what gives the integration an icon in HACS, on the integrations page and on its
devices, without a pull request against home-assistant/brands.

Usage: python scripts/generate-brand-icons.py
Requires Pillow.
"""

from __future__ import annotations

import pathlib

from PIL import Image

COMPONENT = (
    pathlib.Path(__file__).resolve().parents[1]
    / "custom_components"
    / "medication_reminder"
)
SOURCE = COMPONENT / "frontend" / "logo.png"
BRAND = COMPONENT / "brand"
# Home Assistant requires a square icon at exactly these sizes.
SIZES = {"icon.png": 256, "icon@2x.png": 512}


def main() -> None:
    BRAND.mkdir(exist_ok=True)
    source = Image.open(SOURCE).convert("RGBA")

    # Brand images have to be trimmed, so drop any transparent border first.
    bbox = source.getchannel("A").getbbox()
    artwork = source.crop(bbox) if bbox else source

    # Pad the shorter side instead of distorting the artwork into a square.
    side = max(artwork.size)
    if artwork.size != (side, side):
        square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        square.paste(
            artwork, ((side - artwork.width) // 2, (side - artwork.height) // 2)
        )
        artwork = square

    for name, size in SIZES.items():
        target = BRAND / name
        artwork.resize((size, size), Image.LANCZOS).save(target, optimize=True)
        print(f"wrote {target.name} at {size}x{size} ({target.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
