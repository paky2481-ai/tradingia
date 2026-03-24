"""Centralized logging with Loguru"""

import sys
from loguru import logger
from config.settings import settings
import os

os.makedirs(settings.log_dir, exist_ok=True)

logger.remove()

# Console
logger.add(
    sys.stdout,
    level=settings.log_level,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    colorize=True,
)

# File - rotating
logger.add(
    f"{settings.log_dir}/tradingia.log",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} - {message}",
    rotation="100 MB",
    retention="30 days",
    compression="zip",
)

# Trades log
logger.add(
    f"{settings.log_dir}/trades.log",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
    filter=lambda record: "TRADE" in record["message"],
    rotation="50 MB",
    retention="365 days",
)

get_logger = logger


def attach_test_server_sink() -> None:
    """Aggiunge il sink loguru → TestServer (chiamato da app.py dopo avvio server)."""
    try:
        from core.test_server import test_server
        logger.add(test_server.loguru_sink, level="DEBUG", format="{message}")
    except Exception as e:
        logger.warning(f"TestServer sink non agganciato: {e}")
