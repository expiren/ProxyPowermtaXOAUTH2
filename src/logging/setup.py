"""Logging setup for XOAUTH2 Proxy"""

import logging
import platform
import sys
from pathlib import Path
import os


def get_log_path() -> str:
    """Get platform-specific log file path"""
    system = platform.system()

    if system == "Windows":
        # Windows: Use local directory or temp
        log_dir = Path(os.environ.get('TEMP', '.')) / 'xoauth2_proxy'
    elif system == "Darwin":
        # macOS
        log_dir = Path('/var/log/xoauth2')
    else:
        # Linux and other Unix-like systems
        log_dir = Path('/var/log/xoauth2')

    # Create directory if it doesn't exist
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        # If we don't have permission, use current directory
        log_dir = Path('.')
    except Exception as e:
        print(f"Warning: Could not create log directory {log_dir}: {e}")
        log_dir = Path('.')

    log_file = log_dir / 'xoauth2_proxy.log'
    return str(log_file)


def setup_logging(log_level: int = logging.DEBUG) -> str:
    """
    Configure logging for the application

    Args:
        log_level: Logging level (default: DEBUG)

    Returns:
        Path to log file
    """
    log_file_path = get_log_path()

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s] - %(message)s',
        handlers=[
            logging.FileHandler(log_file_path),
            logging.StreamHandler(sys.stdout)
        ]
    )

    logger = logging.getLogger('xoauth2_proxy')
    logger.info(f"XOAUTH2 Proxy starting on {platform.system()} - Logs: {log_file_path}")

    return log_file_path


def get_logger(name: str) -> logging.Logger:
    """Get logger instance"""
    return logging.getLogger(name)
