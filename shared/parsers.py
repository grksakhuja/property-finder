"""Unified parsing utilities for yen amounts, building age, and size."""

import datetime
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


def parse_year_to_age(text: Optional[str]) -> int:
    """Extract a 4-digit year from text and return building age in years.

    Handles:
      - "2010年 9月" → age based on current year
      - "Built in 2010" → age based on current year
      - "2015" → age based on current year
      - "" / None → -1 (unknown)
    """
    if not text:
        return -1
    m = re.search(r"(\d{4})", text)
    if m:
        return max(0, datetime.datetime.now().year - int(m.group(1)))
    return -1


def parse_walk_minutes(text: Optional[str]) -> Optional[int]:
    """Extract walk time in minutes from access strings.

    Handles:
      - "JR京浜東北線 川口駅 徒歩8分" → 8
      - "5 min walk" or "5-min walk" → 5
      - "8 min. walk" → 8
      - "徒歩16～19分" → 16 (takes first/min)
      - Multiple access lines separated by " / " → returns shortest
      - "" / None / no walk info → None
    """
    if not text:
        return None
    matches = []
    # JP: 徒歩8分, 歩5分
    for m in re.finditer(r'(?:徒歩|歩)(\d+)', text):
        matches.append(int(m.group(1)))
    # EN: "6 min walk", "6-min walk", "6 min. walk"
    for m in re.finditer(r'(\d+)\s*(?:-\s*)?min\.?\s*walk', text, re.IGNORECASE):
        matches.append(int(m.group(1)))
    return min(matches) if matches else None


def parse_digits_as_yen(text: Optional[str]) -> int:
    """Strip non-digits and return integer yen.

    Handles:
      - "￥50,000" → 50000
      - "¥80,000" → 80000
      - "Monthly Costs ¥150,490" → 150490
      - "-" / "None" / "N/A" / "free" / "" → 0
    """
    if not text or text.strip().lower() in ("none", "n/a", "-", "free", ""):
        return 0
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else 0
