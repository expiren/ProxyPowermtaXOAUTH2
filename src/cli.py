"""Command-line interface argument parser"""

import argparse
from pathlib import Path

from src.config.settings import Settings


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description='Production XOAUTH2 SMTP Proxy for PowerMTA',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python xoauth2_proxy.py --config accounts.json
  python xoauth2_proxy.py --config accounts.json --proxy-config config.json
  python xoauth2_proxy.py --host 0.0.0.0 --port 2525 --config /etc/xoauth2/accounts.json
  python xoauth2_proxy.py --dry-run --config accounts.json
  python xoauth2_proxy.py --global-concurrency 1000 --config accounts.json
        """
    )

    # Configuration
    parser.add_argument(
        '--config',
        type=str,
        default='accounts.json',
        help='Path to accounts.json configuration file (default: accounts.json)'
    )

    parser.add_argument(
        '--proxy-config',
        type=str,
        default=None,
        help='Path to config.json proxy configuration file (default: auto-detect from accounts.json directory or use built-in defaults)'
    )

    # Server settings
    parser.add_argument(
        '--host',
        type=str,
        default='127.0.0.1',
        help='Listen host (default: 127.0.0.1, use 0.0.0.0 for remote access)'
    )

    parser.add_argument(
        '--port',
        type=int,
        default=2525,
        help='Listen port (default: 2525)'
    )

    # Performance tuning
    parser.add_argument(
        '--global-concurrency',
        type=int,
        default=100,
        help='Global concurrency limit (default: 100, increase for high throughput)'
    )

    # Features
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Enable dry-run mode (test connections without sending messages)'
    )

    # Parse arguments
    args = parser.parse_args()

    # Smart config path discovery
    config_path = Settings.get_config_path(args.config)

    # Proxy config path (optional, will be auto-detected if not provided)
    proxy_config_path = None
    if args.proxy_config:
        proxy_config_path = Settings.get_config_path(args.proxy_config)

    return args, config_path, proxy_config_path


def create_settings(args: argparse.Namespace) -> Settings:
    """Create Settings object from parsed arguments"""
    return Settings(
        host=args.host,
        port=args.port,
        global_concurrency_limit=args.global_concurrency,
        dry_run=args.dry_run,
    )
