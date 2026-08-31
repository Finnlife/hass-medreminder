"""Local QR-code generation for scan links."""

from __future__ import annotations

import segno


def qr_data_uri(value: str) -> str:
    """Return a compact SVG data URI containing a standards-compliant QR code."""
    if not value or len(value) > 2048:
        raise ValueError("QR-code value must contain between 1 and 2048 characters")
    return segno.make_qr(value, error="m").svg_data_uri(
        scale=5,
        border=4,
        dark="#075f54",
        light="#ffffff",
        encode_minimal=True,
    )
