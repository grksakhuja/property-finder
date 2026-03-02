"""Logging configuration for scrapers."""

import logging
import sys


def setup_logging(verbose: bool = False, name: str = "scraper") -> logging.Logger:
    """Configure and return a logger.

    Args:
        verbose: If True, set DEBUG level; otherwise INFO.
        name: Logger name.

    Returns:
        Configured logging.Logger.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # already configured

    level = logging.DEBUG if verbose else logging.INFO
    logger.setLevel(level)

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
    handler.setFormatter(fmt)
    logger.addHandler(handler)

    return logger
