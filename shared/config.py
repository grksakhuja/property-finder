"""Unified area configuration — single source of truth for all scrapers."""

import json
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional, List


@dataclass(frozen=True)
class Area:
    """A geographic area searched across one or more property sources."""
    name: str           # e.g. "Kawaguchi (川口市)"
    prefecture: str     # e.g. "saitama"
    lat: float = 0.0    # centre latitude (for POI builder)
    lng: float = 0.0    # centre longitude (for POI builder)

    # UR-specific codes (None if area not on UR)
    ur_block: Optional[str] = None   # e.g. "kanto"
    ur_tdfk: Optional[str] = None    # e.g. "11"
    ur_skcs: Optional[str] = None    # e.g. "203"

    # SUUMO-specific code (None if area not on SUUMO)
    suumo_code: Optional[str] = None  # e.g. "sc_kawaguchi"

    # Real Estate Japan codes (None if area not on REJ)
    rej_prefecture: Optional[str] = None  # e.g. "JP-11"
    rej_city: Optional[str] = None        # e.g. "11203"

    # Best Estate codes (None if area not on Best Estate)
    best_estate_prefecture: Optional[str] = None  # e.g. "saitama"

    # GaijinPot codes (None if area not on GaijinPot)
    gaijinpot_prefecture_id: Optional[str] = None  # e.g. "13" (Tokyo), "14" (Kanagawa)

    # Wagaya Japan codes (None if area not on Wagaya)
    wagaya_prefecture: Optional[str] = None  # e.g. "tokyo", "saitama"

    # Canary codes (None if area not on Canary)
    canary_prefecture: Optional[str] = None  # e.g. "tokyo", "kanagawa"

    # Village House codes (None if area not on Village House)
    villagehouse_region: Optional[str] = None      # e.g. "kanto"
    villagehouse_prefecture: Optional[str] = None   # e.g. "kanagawa"
    villagehouse_city: Optional[str] = None          # e.g. "kawasaki"

    @property
    def en_name(self) -> str:
        """English name: 'Kawaguchi (川口市)' → 'Kawaguchi'"""
        return self.name.split("(")[0].strip()

    @property
    def jp_name(self) -> str:
        """Japanese name: 'Kawaguchi (川口市)' → '川口市'"""
        m = re.search(r"\((.+?)\)", self.name)
        return m.group(1) if m else ""


@lru_cache(maxsize=1)
def get_target_room_types() -> List[str]:
    """Return target room type names from scoring_config.json."""
    config_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "scoring_config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    return list(config.get("roomType", {}).keys())


def get_areas_for_source(source: str) -> List[Area]:
    """Return areas that have codes for a given source."""
    if source == "ur":
        return [a for a in AREAS if a.ur_skcs is not None]
    elif source == "suumo":
        return [a for a in AREAS if a.suumo_code is not None]
    elif source == "rej":
        return [a for a in AREAS if a.rej_city is not None]
    elif source == "best_estate":
        return [a for a in AREAS if a.best_estate_prefecture is not None]
    elif source == "gaijinpot":
        return [a for a in AREAS if a.gaijinpot_prefecture_id is not None]
    elif source == "wagaya":
        return [a for a in AREAS if a.wagaya_prefecture is not None]
    elif source == "canary":
        return [a for a in AREAS if a.canary_prefecture is not None]
    elif source == "villagehouse":
        return [a for a in AREAS if a.villagehouse_city is not None]
    else:
        raise ValueError(f"Unknown source: {source}")


# ---------------------------------------------------------------------------
# Unified areas list
# Merges ur_rental_search.py (30 areas), suumo_search.py (32 areas),
# realestate_jp_search.py (18 areas), and build_pois.py AREA_CENTRES.
# ---------------------------------------------------------------------------

AREAS = [
    # === SAITAMA ===
    Area("Kawaguchi (川口市)",        "saitama", 35.808, 139.724,
         ur_block="kanto", ur_tdfk="11", ur_skcs="203",
         suumo_code="sc_kawaguchi",
         rej_prefecture="JP-11", rej_city="11203",
         best_estate_prefecture="saitama",
         gaijinpot_prefecture_id="11", wagaya_prefecture="saitama", canary_prefecture="saitama"),
    Area("Wako (和光市)",            "saitama", 35.787, 139.606,
         ur_block="kanto", ur_tdfk="11", ur_skcs="229",
         suumo_code="sc_wako",
         gaijinpot_prefecture_id="11", wagaya_prefecture="saitama", canary_prefecture="saitama"),
    Area("Urawa (浦和区)",           "saitama", 35.858, 139.657,
         ur_block="kanto", ur_tdfk="11", ur_skcs="107",
         suumo_code="sc_saitamashiurawa",
         rej_prefecture="JP-11", rej_city="11107",
         gaijinpot_prefecture_id="11", wagaya_prefecture="saitama", canary_prefecture="saitama"),
    Area("Omiya (大宮区)",           "saitama", 35.906, 139.631,
         ur_block="kanto", ur_tdfk="11", ur_skcs="103",
         suumo_code="sc_saitamashiomiya",
         rej_prefecture="JP-11", rej_city="11103",
         gaijinpot_prefecture_id="11", wagaya_prefecture="saitama", canary_prefecture="saitama"),
    Area("Kawagoe (川越市)",         "saitama", 35.925, 139.486,
         ur_block="kanto", ur_tdfk="11", ur_skcs="201",
         suumo_code="sc_kawagoe",
         rej_prefecture="JP-11", rej_city="11201",
         gaijinpot_prefecture_id="11", wagaya_prefecture="saitama", canary_prefecture="saitama"),
    Area("Toda (戸田市)",            "saitama", 35.817, 139.678,
         ur_block="kanto", ur_tdfk="11", ur_skcs="224",
         suumo_code="sc_toda",
         gaijinpot_prefecture_id="11", wagaya_prefecture="saitama", canary_prefecture="saitama"),
    Area("Warabi (蕨市)",            "saitama", 35.826, 139.680,
         ur_block="kanto", ur_tdfk="11", ur_skcs="223",
         suumo_code="sc_warabi",
         gaijinpot_prefecture_id="11", wagaya_prefecture="saitama", canary_prefecture="saitama"),
    Area("Saitama Minami-ku (南区)", "saitama", 35.845, 139.645,
         ur_block="kanto", ur_tdfk="11", ur_skcs="108",
         suumo_code="sc_saitamashiminami",
         rej_prefecture="JP-11", rej_city="11108",
         gaijinpot_prefecture_id="11", wagaya_prefecture="saitama", canary_prefecture="saitama"),
    Area("Saitama Chuo-ku (中央区)", "saitama", 35.874, 139.625,
         ur_block="kanto", ur_tdfk="11", ur_skcs="105",
         suumo_code="sc_saitamashichuo",
         gaijinpot_prefecture_id="11", wagaya_prefecture="saitama", canary_prefecture="saitama"),
    Area("Asaka (朝霞市)",           "saitama", 35.797, 139.593,
         ur_block="kanto", ur_tdfk="11", ur_skcs="227",
         suumo_code="sc_asaka",
         gaijinpot_prefecture_id="11", wagaya_prefecture="saitama", canary_prefecture="saitama"),
    Area("Niiza (新座市)",           "saitama", 35.793, 139.565,
         ur_block="kanto", ur_tdfk="11", ur_skcs="230",
         suumo_code="sc_niiza",
         gaijinpot_prefecture_id="11", wagaya_prefecture="saitama", canary_prefecture="saitama"),

    # === CHIBA ===
    Area("Ichikawa (市川市)",        "chiba", 35.732, 139.931,
         ur_block="kanto", ur_tdfk="12", ur_skcs="203",
         suumo_code="sc_ichikawa",
         rej_prefecture="JP-12", rej_city="12203",
         best_estate_prefecture="chiba",
         gaijinpot_prefecture_id="12", wagaya_prefecture="chiba", canary_prefecture="chiba"),
    Area("Funabashi (船橋市)",       "chiba", 35.695, 139.983,
         ur_block="kanto", ur_tdfk="12", ur_skcs="204",
         suumo_code="sc_funabashi",
         rej_prefecture="JP-12", rej_city="12204",
         gaijinpot_prefecture_id="12", wagaya_prefecture="chiba", canary_prefecture="chiba"),
    Area("Urayasu (浦安市)",         "chiba", 35.654, 139.902,
         ur_block="kanto", ur_tdfk="12", ur_skcs="227",
         suumo_code="sc_urayasu",
         rej_prefecture="JP-12", rej_city="12227",
         gaijinpot_prefecture_id="12", wagaya_prefecture="chiba", canary_prefecture="chiba"),
    Area("Matsudo (松戸市)",         "chiba", 35.788, 139.901,
         ur_block="kanto", ur_tdfk="12", ur_skcs="207",
         suumo_code="sc_matsudo",
         rej_prefecture="JP-12", rej_city="12207",
         gaijinpot_prefecture_id="12", wagaya_prefecture="chiba", canary_prefecture="chiba"),

    # === KANAGAWA — Kawasaki ===
    Area("Kawasaki-ku (川崎区)",     "kanagawa", 35.531, 139.703,
         ur_block="kanto", ur_tdfk="14", ur_skcs="131",
         suumo_code="sc_kawasakishikawasaki",
         best_estate_prefecture="kanagawa",
         gaijinpot_prefecture_id="14", wagaya_prefecture="kanagawa", canary_prefecture="kanagawa",
         villagehouse_region="kanto", villagehouse_prefecture="kanagawa", villagehouse_city="kawasaki"),
    Area("Saiwai-ku (幸区)",         "kanagawa", 35.541, 139.684,
         ur_block="kanto", ur_tdfk="14", ur_skcs="132",
         suumo_code="sc_kawasakishisaiwai",
         gaijinpot_prefecture_id="14", wagaya_prefecture="kanagawa", canary_prefecture="kanagawa",
         villagehouse_region="kanto", villagehouse_prefecture="kanagawa", villagehouse_city="kawasaki"),
    Area("Nakahara-ku (中原区)",     "kanagawa", 35.576, 139.660,
         ur_block="kanto", ur_tdfk="14", ur_skcs="133",
         suumo_code="sc_kawasakishinakahara",
         gaijinpot_prefecture_id="14", wagaya_prefecture="kanagawa", canary_prefecture="kanagawa",
         villagehouse_region="kanto", villagehouse_prefecture="kanagawa", villagehouse_city="kawasaki"),
    Area("Takatsu-ku (高津区)",      "kanagawa", 35.588, 139.615,
         ur_block="kanto", ur_tdfk="14", ur_skcs="134",
         suumo_code="sc_kawasakishitakatsu",
         gaijinpot_prefecture_id="14", wagaya_prefecture="kanagawa", canary_prefecture="kanagawa",
         villagehouse_region="kanto", villagehouse_prefecture="kanagawa", villagehouse_city="kawasaki"),

    # === KANAGAWA — Yokohama ===
    Area("Yokohama Nishi-ku (西区)", "kanagawa", 35.466, 139.622,
         ur_block="kanto", ur_tdfk="14", ur_skcs="103",
         suumo_code="sc_yokohamashinishi",
         gaijinpot_prefecture_id="14", wagaya_prefecture="kanagawa", canary_prefecture="kanagawa",
         villagehouse_region="kanto", villagehouse_prefecture="kanagawa", villagehouse_city="yokohama"),
    Area("Yokohama Naka-ku (中区)",  "kanagawa", 35.444, 139.638,
         ur_block="kanto", ur_tdfk="14", ur_skcs="104",
         suumo_code="sc_yokohamashinaka",
         gaijinpot_prefecture_id="14", wagaya_prefecture="kanagawa", canary_prefecture="kanagawa",
         villagehouse_region="kanto", villagehouse_prefecture="kanagawa", villagehouse_city="yokohama"),
    Area("Yokohama Kanagawa-ku (神奈川区)", "kanagawa", 35.479, 139.637,
         ur_block="kanto", ur_tdfk="14", ur_skcs="102",
         suumo_code="sc_yokohamashikanagawa",
         gaijinpot_prefecture_id="14", wagaya_prefecture="kanagawa", canary_prefecture="kanagawa",
         villagehouse_region="kanto", villagehouse_prefecture="kanagawa", villagehouse_city="yokohama"),
    Area("Yokohama Kohoku-ku (港北区)", "kanagawa", 35.520, 139.593,
         ur_block="kanto", ur_tdfk="14", ur_skcs="109",
         suumo_code="sc_yokohamashikohoku",
         gaijinpot_prefecture_id="14", wagaya_prefecture="kanagawa", canary_prefecture="kanagawa",
         villagehouse_region="kanto", villagehouse_prefecture="kanagawa", villagehouse_city="yokohama"),
    Area("Yokohama Tsuzuki-ku (都筑区)", "kanagawa", 35.546, 139.571,
         ur_block="kanto", ur_tdfk="14", ur_skcs="118",
         gaijinpot_prefecture_id="14", wagaya_prefecture="kanagawa", canary_prefecture="kanagawa",
         villagehouse_region="kanto", villagehouse_prefecture="kanagawa", villagehouse_city="yokohama"),
    Area("Yokohama Aoba-ku (青葉区)", "kanagawa", 35.564, 139.541,
         ur_block="kanto", ur_tdfk="14", ur_skcs="117",
         suumo_code="sc_yokohamashiaoba",
         gaijinpot_prefecture_id="14", wagaya_prefecture="kanagawa", canary_prefecture="kanagawa",
         villagehouse_region="kanto", villagehouse_prefecture="kanagawa", villagehouse_city="yokohama"),
    Area("Yokohama Minami-ku (南区)", "kanagawa", 35.428, 139.596,
         ur_block="kanto", ur_tdfk="14", ur_skcs="105",
         suumo_code="sc_yokohamashiminami",
         gaijinpot_prefecture_id="14", wagaya_prefecture="kanagawa", canary_prefecture="kanagawa",
         villagehouse_region="kanto", villagehouse_prefecture="kanagawa", villagehouse_city="yokohama"),
    Area("Yokohama Hodogaya-ku (保土ケ谷区)", "kanagawa", 35.443, 139.596,
         ur_block="kanto", ur_tdfk="14", ur_skcs="106",
         suumo_code="sc_yokohamashihodogaya",
         gaijinpot_prefecture_id="14", wagaya_prefecture="kanagawa", canary_prefecture="kanagawa",
         villagehouse_region="kanto", villagehouse_prefecture="kanagawa", villagehouse_city="yokohama"),
    Area("Yokohama Isogo-ku (磯子区)", "kanagawa", 35.400, 139.621,
         ur_block="kanto", ur_tdfk="14", ur_skcs="107",
         gaijinpot_prefecture_id="14", wagaya_prefecture="kanagawa", canary_prefecture="kanagawa",
         villagehouse_region="kanto", villagehouse_prefecture="kanagawa", villagehouse_city="yokohama"),

    # SUUMO-only Yokohama areas
    Area("Yokohama Tsurumi-ku (鶴見区)", "kanagawa", 35.508, 139.682,
         suumo_code="sc_yokohamashitsurumi",
         gaijinpot_prefecture_id="14", wagaya_prefecture="kanagawa", canary_prefecture="kanagawa",
         villagehouse_region="kanto", villagehouse_prefecture="kanagawa", villagehouse_city="yokohama"),
    Area("Yokohama Konan-ku (港南区)", "kanagawa", 35.381, 139.598,
         suumo_code="sc_yokohamashikonan",
         gaijinpot_prefecture_id="14", wagaya_prefecture="kanagawa", canary_prefecture="kanagawa",
         villagehouse_region="kanto", villagehouse_prefecture="kanagawa", villagehouse_city="yokohama"),

    # REJ has Kawasaki and Yokohama as single city entries
    # These are mapped separately as REJ uses broader city codes
    Area("Kawasaki (川崎市)",        "kanagawa", 35.531, 139.703,
         rej_prefecture="JP-14", rej_city="14130",
         gaijinpot_prefecture_id="14", wagaya_prefecture="kanagawa", canary_prefecture="kanagawa",
         villagehouse_region="kanto", villagehouse_prefecture="kanagawa", villagehouse_city="kawasaki"),
    Area("Yokohama (横浜市)",        "kanagawa", 35.466, 139.622,
         rej_prefecture="JP-14", rej_city="14100",
         gaijinpot_prefecture_id="14", wagaya_prefecture="kanagawa", canary_prefecture="kanagawa",
         villagehouse_region="kanto", villagehouse_prefecture="kanagawa", villagehouse_city="yokohama"),

    # === KANAGAWA — Shonan ===
    Area("Kamakura (鎌倉市)",        "kanagawa", 35.319, 139.547,
         ur_block="kanto", ur_tdfk="14", ur_skcs="204",
         suumo_code="sc_kamakura",
         rej_prefecture="JP-14", rej_city="14204",
         gaijinpot_prefecture_id="14", wagaya_prefecture="kanagawa", canary_prefecture="kanagawa"),
    Area("Fujisawa (藤沢市)",        "kanagawa", 35.339, 139.490,
         ur_block="kanto", ur_tdfk="14", ur_skcs="205",
         suumo_code="sc_fujisawa",
         rej_prefecture="JP-14", rej_city="14205",
         gaijinpot_prefecture_id="14", wagaya_prefecture="kanagawa", canary_prefecture="kanagawa"),
    Area("Chigasaki (茅ヶ崎市)",     "kanagawa", 35.334, 139.405,
         ur_block="kanto", ur_tdfk="14", ur_skcs="207",
         suumo_code="sc_chigasaki",
         gaijinpot_prefecture_id="14", wagaya_prefecture="kanagawa", canary_prefecture="kanagawa"),

    # === TOKYO border ===
    Area("Kita-ku (北区)",           "tokyo", 35.753, 139.734,
         ur_block="kanto", ur_tdfk="13", ur_skcs="117",
         suumo_code="sc_kita",
         rej_prefecture="JP-13", rej_city="13117",
         best_estate_prefecture="tokyo",
         gaijinpot_prefecture_id="13", wagaya_prefecture="tokyo", canary_prefecture="tokyo"),
    Area("Itabashi-ku (板橋区)",     "tokyo", 35.769, 139.709,
         ur_block="kanto", ur_tdfk="13", ur_skcs="119",
         suumo_code="sc_itabashi",
         rej_prefecture="JP-13", rej_city="13119",
         gaijinpot_prefecture_id="13", wagaya_prefecture="tokyo", canary_prefecture="tokyo"),
    Area("Nerima-ku (練馬区)",       "tokyo", 35.736, 139.652,
         ur_block="kanto", ur_tdfk="13", ur_skcs="120",
         suumo_code="sc_nerima",
         rej_prefecture="JP-13", rej_city="13120",
         gaijinpot_prefecture_id="13", wagaya_prefecture="tokyo", canary_prefecture="tokyo"),
    Area("Adachi-ku (足立区)",       "tokyo", 35.776, 139.804,
         ur_block="kanto", ur_tdfk="13", ur_skcs="121",
         suumo_code="sc_adachi",
         rej_prefecture="JP-13", rej_city="13121",
         gaijinpot_prefecture_id="13", wagaya_prefecture="tokyo", canary_prefecture="tokyo"),
    Area("Edogawa-ku (江戸川区)",    "tokyo", 35.707, 139.868,
         ur_block="kanto", ur_tdfk="13", ur_skcs="123",
         suumo_code="sc_edogawa",
         rej_prefecture="JP-13", rej_city="13123",
         gaijinpot_prefecture_id="13", wagaya_prefecture="tokyo", canary_prefecture="tokyo"),
]
