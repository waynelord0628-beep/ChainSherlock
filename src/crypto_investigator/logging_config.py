import sys

from loguru import logger


def configure_logging(level: str = "INFO") -> None:
    logger.remove()
    logger.add(sys.stderr, level=level.upper(), format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")

