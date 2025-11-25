"""Command-line interface argument parser"""

import argparse
from argparse import Namespace
from pathlib import Path

from src.config.settings import Settings


def parse_arguments() -> tuple[Namespace, Path, Path]:
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description='Production XOAUTH2 SMTP Proxy for PowerMTA',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python xoauth2_proxy.py
  python xoauth2_proxy.py --config /path/to/config.json
  python xoauth2_proxy.py --host 0.0.0.0 --port 2525
  python xoauth2_proxy.py --dry-run
  python xoauth2_proxy.py --global-concurrency 1000
        """
    )

    # Configuration files (separated: config.json for settings, accounts.json for credentials)
    parser.add_argument(
        '--config',
        type=str,
        default='config.json',
        help='Path to config.json file (global settings, default: config.json)'
    )

    parser.add_argument(
        '--accounts',
        type=str,
        default='accounts.json',
        help='Path to accounts.json file (account credentials, default: accounts.json)'
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

    # Admin HTTP server settings
    parser.add_argument(
        '--admin-host',
        type=str,
        default='0.0.0.0',
        help='Admin HTTP server host (default: 0.0.0.0 for internet access, use 127.0.0.1 for localhost only)'
    )

    parser.add_argument(
        '--admin-port',
        type=int,
        default=9090,
        help='Admin HTTP server port (default: 9090)'
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

    parser.add_argument(
        '--admin-only',
        action='store_true',
        help='Run admin HTTP server only (no SMTP proxy server). Useful when using external relay (e.g., PowerMtaRelay)'
    )

    # Parse arguments
    args = parser.parse_args()

    # Smart config path discovery for both files
    config_path = Settings.get_config_path(args.config)
    accounts_path = Settings.get_config_path(args.accounts)

    return args, config_path, accounts_path


def create_settings(args: argparse.Namespace) -> Settings:
    """Create Settings object from parsed arguments"""
    return Settings(
        host=args.host,
        port=args.port,
        admin_host=args.admin_host,
        admin_port=args.admin_port,
        global_concurrency_limit=args.global_concurrency,
        dry_run=args.dry_run,
        admin_only=args.admin_only,
    )
