"""
Utility helpers for the Jumia Kenya price scraper.
"""

import re
from typing import Optional


def parse_price(price_str: Optional[str]) -> Optional[float]:
    """
    Convert a Jumia price string to a float value in KES.

    Examples:
        "KSh 15,000"  -> 15000.0
        "KSh1,200"    -> 1200.0
        "KSh 3,999"   -> 3999.0
        "N/A"         -> None
        ""            -> None
        None          -> None
    """
    if not price_str:
        return None

    cleaned = price_str.strip()
    if cleaned.upper() in ("N/A", "-", ""):
        return None

    # Remove currency prefix (KSh, KES, etc.) and whitespace
    cleaned = re.sub(r"[Kk][Ss][Hh]?\s*", "", cleaned)

    # Remove commas used as thousand separators
    cleaned = cleaned.replace(",", "")

    # Strip any remaining non-numeric chars except decimal point
    cleaned = re.sub(r"[^\d.]", "", cleaned)

    if not cleaned:
        return None

    try:
        value = float(cleaned)
        return value if value > 0 else None
    except ValueError:
        return None


def parse_discount(discount_str: Optional[str]) -> Optional[float]:
    """
    Parse a discount badge string like "-23%" to a float (23.0).

    Returns None if not parseable or zero.
    """
    if not discount_str:
        return None

    cleaned = discount_str.strip()
    # Remove leading minus, trailing percent, whitespace
    cleaned = re.sub(r"[%\-\s]", "", cleaned)

    if not cleaned:
        return None

    try:
        value = float(cleaned)
        return value if value > 0 else None
    except ValueError:
        return None


def build_full_url(href: Optional[str], base: str = "https://www.jumia.co.ke") -> Optional[str]:
    """
    Ensure product href is an absolute URL.
    """
    if not href:
        return None
    href = href.strip()
    if href.startswith("http"):
        return href
    return base.rstrip("/") + "/" + href.lstrip("/")
