#!/usr/bin/env python3
"""
XOAUTH2 Proxy v2.0 - Thin wrapper for modular architecture

This is the entry point for the production XOAUTH2 SMTP proxy.
The actual implementation has been refactored into modular components in src/.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.main import main

if __name__ == '__main__':
    main()
