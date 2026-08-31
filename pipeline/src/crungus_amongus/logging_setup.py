"""Loguru configuration: clean INFO by default, DEBUG with --verbose."""

import sys

from loguru import logger


def setup_logging(verbose: bool = False) -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level="DEBUG" if verbose else "INFO",
        format="<green>{time:HH:mm:ss}</green> <level>{level: <8}</level> {message}",
    )
