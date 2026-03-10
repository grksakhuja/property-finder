"""Base scraper template — handles CLI, pagination, HTTP, and JSON output.

New scrapers subclass BaseScraper and override build_url() and parse_page().
Existing scrapers are NOT refactored to use this — it's opt-in for new scrapers only.
"""

import glob as glob_mod
import json
import os
import tempfile
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional

import requests

from shared.cli import build_arg_parser, filter_areas
from shared.config import get_areas_for_source, Area
from shared.http_client import create_session, fetch_page
from shared.logging_setup import setup_logging


# ---------------------------------------------------------------------------
# Safe JSON writing with backup rotation
# ---------------------------------------------------------------------------

def safe_write_json(data: dict, filepath: str, max_backups: int = 3) -> None:
    """Write JSON atomically with timestamped backup rotation.

    1. Write to a temp file first (same directory)
    2. If filepath already exists, rename it to filepath.YYYY-MM-DDTHH-MM-SS.json
    3. Rename temp file to filepath (atomic on same filesystem)
    4. Prune old backups keeping only the last max_backups
    """
    dirpath = os.path.dirname(os.path.abspath(filepath))
    base, ext = os.path.splitext(filepath)

    # Step 1: Write to temp file in the same directory
    fd, tmp_path = tempfile.mkstemp(suffix=ext, dir=dirpath)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        os.unlink(tmp_path)
        raise

    # Step 2: If filepath exists, rename to timestamped backup
    if os.path.exists(filepath):
        mtime = os.path.getmtime(filepath)
        ts = datetime.fromtimestamp(mtime).strftime("%Y-%m-%dT%H-%M-%S")
        backup_path = f"{base}.{ts}{ext}"
        # Avoid overwriting an existing backup with the same timestamp
        if os.path.exists(backup_path):
            backup_path = f"{base}.{ts}-{int(time.time()) % 1000}{ext}"
        os.rename(filepath, backup_path)

    # Step 3: Atomic rename temp → target
    os.rename(tmp_path, filepath)

    # Step 4: Prune old backups
    pattern = f"{base}.*T*{ext}"
    backups = sorted(glob_mod.glob(pattern))
    while len(backups) > max_backups:
        try:
            os.unlink(backups.pop(0))
        except OSError:
            pass  # Best-effort cleanup; file may be locked or already removed


# ---------------------------------------------------------------------------
# Standard data classes (matching viewer JSON format)
# ---------------------------------------------------------------------------

@dataclass
class StandardRoom:
    floor: str
    rent: str
    rent_value: int
    admin_fee: str
    admin_fee_value: int
    total_value: int
    deposit: str
    deposit_value: int
    key_money: str
    key_money_value: int
    layout: str
    size: str
    detail_url: str


@dataclass
class StandardProperty:
    name: str
    address: str
    access: str
    building_age: str
    building_age_years: int
    area_name: str
    prefecture: str
    rooms: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Base scraper class
# ---------------------------------------------------------------------------

class BaseScraper(ABC):
    """Template for property scrapers with common boilerplate.

    Subclasses must set class-level config and implement:
      - build_url(area, page) -> str
      - parse_page(html, area) -> list[StandardProperty]
    """

    # --- Class-level config (override in subclass) ---
    SOURCE_NAME: str = ""
    BASE_URL: str = ""
    OUTPUT_FILE: str = ""
    REQUEST_DELAY: float = 1.0
    MAX_PAGES_PER_AREA: int = 5
    ITEMS_PER_PAGE: int = 20
    DEFAULT_WORKERS: int = 3
    ROOM_TYPE_FILTER: List[str] = []
    EXTRA_HEADERS: Optional[dict] = None

    def __init__(self):
        self.logger = setup_logging(name=self.SOURCE_NAME)

    # --- Abstract methods (must override) ---

    @abstractmethod
    def build_url(self, area: Area, page: int = 1) -> str:
        """Construct search URL for an area and page number."""

    @abstractmethod
    def parse_page(self, html: str, area: Area) -> List[StandardProperty]:
        """Parse HTML into StandardProperty objects."""

    # --- Default implementations ---

    def search_area(self, area: Area, session: requests.Session,
                    max_pages: int = 0) -> List[StandardProperty]:
        """Paginate through search results for a single area."""
        if max_pages <= 0:
            max_pages = self.MAX_PAGES_PER_AREA

        all_properties: List[StandardProperty] = []

        for page_num in range(1, max_pages + 1):
            url = self.build_url(area, page_num)

            try:
                resp = fetch_page(session, url, delay=self.REQUEST_DELAY if page_num > 1 else 0)
            except requests.RequestException as e:
                self.logger.error("Request failed (page %d): %s", page_num, e)
                break

            try:
                properties = self.parse_page(resp.text, area)
            except Exception as e:
                self.logger.error("Parse failed (page %d): %s", page_num, e)
                break

            if not properties:
                if page_num == 1:
                    self.logger.info("  No listings found")
                break

            all_properties.extend(properties)
            room_count = sum(len(p.rooms) for p in properties)
            self.logger.info("  Page %d: %d buildings, %d units",
                             page_num, len(properties), room_count)

            # Stop if fewer results than a full page
            if room_count < self.ITEMS_PER_PAGE:
                break

        return all_properties

    def save_results(self, all_properties: List[StandardProperty],
                     filename: str = "") -> None:
        """Save structured results to JSON, compatible with viewer."""
        filename = filename or self.OUTPUT_FILE
        data = {
            "source": self.SOURCE_NAME,
            "search_date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "room_type_filter": self.ROOM_TYPE_FILTER,
            "total_properties": len(all_properties),
            "total_rooms": sum(len(p.rooms) for p in all_properties),
            "areas": {},
        }

        for prop in all_properties:
            area = prop.area_name
            if area not in data["areas"]:
                data["areas"][area] = []

            prop_dict = {
                "name": prop.name,
                "address": prop.address,
                "access": prop.access,
                "building_age": prop.building_age,
                "building_age_years": prop.building_age_years,
                "rooms": [asdict(r) for r in prop.rooms],
            }
            data["areas"][area].append(prop_dict)

        safe_write_json(data, filename)

        self.logger.info("Results saved to %s", filename)

    def run(self) -> None:
        """Full CLI entry point — parse args, scrape, save."""
        parser = build_arg_parser(
            self.SOURCE_NAME, f"Search {self.SOURCE_NAME} rental listings")
        args = parser.parse_args()

        if args.verbose:
            self.logger.setLevel("DEBUG")
            for h in self.logger.handlers:
                h.setLevel("DEBUG")

        max_pages = args.max_pages if args.max_pages is not None else self.MAX_PAGES_PER_AREA
        if args.delay is not None:
            self.REQUEST_DELAY = args.delay
        output_file = args.output or self.OUTPUT_FILE

        areas = filter_areas(get_areas_for_source(self.SOURCE_NAME), args.areas)

        self.logger.info("%s Rental Search", self.SOURCE_NAME)
        if self.ROOM_TYPE_FILTER:
            self.logger.info("Filtering for: %s", ", ".join(self.ROOM_TYPE_FILTER))
        self.logger.info("Searching %d areas (max %d pages each)...",
                         len(areas), max_pages)

        if args.dry_run:
            for area in areas:
                self.logger.info("[DRY RUN] %s", self.build_url(area))
            return

        all_properties: List[StandardProperty] = []
        max_workers = args.workers if args.workers is not None else self.DEFAULT_WORKERS

        # Note: self.REQUEST_DELAY is set above (line 228) before the
        # ThreadPoolExecutor starts, so workers always see the final value.
        extra_headers = self.EXTRA_HEADERS or {"Accept-Language": "ja,en;q=0.9"}

        def _search_one(area):
            thread_session = create_session(extra_headers=extra_headers)
            self.logger.info("[%s] Searching...", area.name)
            return area, self.search_area(area, thread_session, max_pages)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_search_one, area): area for area in areas}
            for future in as_completed(futures):
                try:
                    area, props = future.result()
                except Exception as e:
                    area = futures[future]
                    self.logger.error("[%s] Unexpected error: %s", area.name, e)
                    continue
                if props:
                    room_count = sum(len(p.rooms) for p in props)
                    self.logger.info("[%s] Total: %d buildings with %d units",
                                     area.name, len(props), room_count)
                    all_properties.extend(props)
                else:
                    self.logger.info("[%s] No listings", area.name)

        self.save_results(all_properties, output_file)
