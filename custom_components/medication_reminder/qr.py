"""Local QR-code generation for scan links."""

from __future__ import annotations

import segno

from .scan_codes import SCAN_CODE_PATTERN


def qr_data_uri(value: str) -> str:
    """Return a compact SVG data URI containing a standards-compliant QR code."""
    if not SCAN_CODE_PATTERN.fullmatch(value):
        raise ValueError("QR-code value must be a Medication Reminder scan code")
    return segno.make_qr(value, error="q").svg_data_uri(
        scale=6,
        border=4,
        dark="#000000",
        light="#ffffff",
        encode_minimal=True,
    )
