#!/usr/bin/env python3
"""
Wrapper script to add accounts to accounts.json

Usage:
    python add_account.py [path/to/accounts.json]

If no path is provided, uses default accounts.json location.
"""

from src.tools.add_account import main

if __name__ == '__main__':
    main()
