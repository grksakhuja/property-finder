"""Unified parsing utilities for yen amounts, building age, and size."""

import re
from typing import Optional


def parse_yen(text: Optional[str]) -> int:
    """Parse any yen format to integer.

    Handles:
      - "8.2万円" → 82000  (SUUMO man-yen format)
      - "¥115,000" → 115000
      - "101,800円" → 101800
      - "5000円" → 5000
      - "-" / "" / None → 0
    """
    if not text or text.strip() == "-":
        return 0
    text = text.strip().replace(",", "")
    # 万円 format: X.Y万円 (万 = 10,000)
    m = re.search(r"([\d.]+)万円", text)
    if m:
        return round(float(m.group(1)) * 10000)
    # Plain yen with optional currency symbol: ¥NNN or NNN円
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else 0


def parse_building_age(text: Optional[str]) -> int:
    """Parse building age string to years.

    Handles:
      - "築20年" → 20
      - "新築" → 0  (new build)
      - "" / None → -1  (unknown)
    """
    if not text:
        return -1
    text = text.strip()
    if "新築" in text:
        return 0
    m = re.search(r"築(\d+)年", text)
    return int(m.group(1)) if m else -1


def parse_size_sqm(text: Optional[str]) -> float:
    """Parse size string to square metres.

    Handles:
      - "50.28m²" → 50.28
      - "50.28m2" → 50.28
      - "" / None → 0.0
    """
    if not text:
        return 0.0
    m = re.search(r"([\d.]+)", text)
    return float(m.group(1)) if m else 0.0
