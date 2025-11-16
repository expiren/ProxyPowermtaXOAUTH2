"""XOAUTH2 Proxy v2.0 - Production SMTP relay with OAuth2 authentication

A complete refactoring of the XOAUTH2 proxy with modular architecture designed
to handle 1000+ accounts and 1000+ requests per second.

Modules:
- config: Configuration management
- oauth2: OAuth2 token management
- accounts: Account management
- smtp: SMTP protocol
- logging: Logging setup
- utils: Infrastructure

Entry points:
- python xoauth2_proxy_v2.py (new version)
- python xoauth2_proxy.py (old version, deprecated)

Example usage:
  from src.main import main
  main()

Or:
  from src.config import Settings
  from src.oauth2 import OAuthManager
  from src.accounts import AccountManager
"""

__version__ = "2.0.0"
__author__ = "XOAUTH2 Proxy"
__description__ = "Production XOAUTH2 SMTP Proxy for PowerMTA"

__all__ = [
    '__version__',
    '__author__',
    '__description__',
]
