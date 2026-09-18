import logging
import os
import sys
from datetime import datetime
from typing import Optional

# ANSI color codes for rich terminal output
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"

class ColoredFormatter(logging.Formatter):
    """Custom logging formatter that adds timestamps, module context, and ANSI colors."""

    LEVEL_COLORS = {
        logging.DEBUG: CYAN,
        logging.INFO: GREEN,
        logging.WARNING: YELLOW,
        logging.ERROR: RED,
        logging.CRITICAL: BOLD + RED,
    }

    def format(self, record: logging.LogRecord) -> str:
        color = self.LEVEL_COLORS.get(record.levelno, RESET)
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        level = f"{record.levelname:<8}"
        msg = record.getMessage()

        # Format with color for console
        colored_prefix = f"{BLUE}[{timestamp}]{RESET} {color}{level}{RESET} {MAGENTA}[{record.name}]{RESET}"
        return f"{colored_prefix} {msg}"

def setup_logger(name: str = "SelfHealingNetwork", log_file: Optional[str] = None, level: int = logging.INFO) -> logging.Logger:
    """Configures and returns a logger instance with console and optional file handlers."""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid duplicate handlers
    if logger.hasHandlers():
        return logger

    # Console Handler with Color Formatter
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(ColoredFormatter())
    logger.addHandler(console_handler)

    # Optional File Handler with Plain Formatter
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        plain_format = logging.Formatter(
            "[%(asctime)s.%(msecs)03d] [%(levelname)-8s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(plain_format)
        logger.addHandler(file_handler)

    return logger

# Global default logger
logger = setup_logger(log_file="logs/network_agent.log")
