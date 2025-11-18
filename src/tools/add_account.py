#!/usr/bin/env python3
"""Interactive tool to add accounts to accounts.json"""

import asyncio
import json
import sys
import os
import re
from pathlib import Path
from typing import Dict, Any, Optional
import aiohttp

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config.settings import Settings


def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def get_oauth_endpoint(provider: str) -> str:
    """Get SMTP endpoint based on provider"""
    if provider == 'gmail':
        return 'smtp.gmail.com:587'
    elif provider == 'outlook':
        return 'smtp.office365.com:587'
    else:
        return ''


def get_token_url(provider: str) -> str:
    """Get OAuth2 token URL based on provider"""
    if provider == 'gmail':
        return 'https://oauth2.googleapis.com/token'
    elif provider == 'outlook':
        return 'https://login.microsoftonline.com/common/oauth2/v2.0/token'
    else:
        return ''


async def verify_oauth_credentials(account_data: Dict[str, Any]) -> tuple[bool, str]:
    """Verify OAuth2 credentials by attempting token refresh"""
    provider = account_data['provider']
    token_url = get_token_url(provider)

    if not token_url:
        return False, f"Unknown provider: {provider}"

    print(f"\nVerifying OAuth2 credentials for {account_data['email']}...")

    try:
        if provider == 'gmail':
            data = {
                'client_id': account_data['client_id'],
                'client_secret': account_data['client_secret'],
                'refresh_token': account_data['refresh_token'],
                'grant_type': 'refresh_token'
            }
        elif provider == 'outlook':
            data = {
                'client_id': account_data['client_id'],
                'refresh_token': account_data['refresh_token'],
                'grant_type': 'refresh_token',
                'scope': 'https://outlook.office365.com/SMTP.Send offline_access'
            }
            # Add client_secret only if provided
            if account_data.get('client_secret'):
                data['client_secret'] = account_data['client_secret']

        async with aiohttp.ClientSession() as session:
            async with session.post(token_url, data=data, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    token_data = await response.json()
                    access_token = token_data.get('access_token')
                    if access_token:
                        print("✓ OAuth2 credentials verified successfully!")
                        return True, "Credentials verified"
                    else:
                        return False, "No access token in response"
                else:
                    response_text = await response.text()
                    try:
                        error_json = json.loads(response_text)
                        error_msg = error_json.get('error_description', response_text)
                    except:
                        error_msg = response_text
                    return False, f"Token refresh failed: {error_msg}"

    except asyncio.TimeoutError:
        return False, "Network error: Request timeout"
    except aiohttp.ClientError as e:
        return False, f"Network error: {str(e)}"
    except Exception as e:
        return False, f"Verification error: {str(e)}"


def prompt_account_details() -> Optional[Dict[str, Any]]:
    """Prompt user for account details"""
    print("\n" + "="*60)
    print("ADD NEW ACCOUNT TO XOAUTH2 PROXY")
    print("="*60)

    # Email
    while True:
        email = input("\nEmail address: ").strip()
        if validate_email(email):
            break
        print("✗ Invalid email format. Please try again.")

    # Provider
    while True:
        provider = input("Provider (gmail/outlook): ").strip().lower()
        if provider in ['gmail', 'outlook']:
            break
        print("✗ Provider must be 'gmail' or 'outlook'. Please try again.")

    # Auto-detect oauth_endpoint (SMTP endpoint)
    oauth_endpoint = get_oauth_endpoint(provider)
    print(f"SMTP endpoint: {oauth_endpoint} (auto-detected)")

    # Auto-detect oauth_token_url (OAuth2 token endpoint)
    oauth_token_url = get_token_url(provider)
    print(f"OAuth2 token URL: {oauth_token_url} (auto-detected)")

    # IP Address (optional for source IP binding)
    ip_address = input("IP Address (optional, press Enter to skip): ").strip()
    if ip_address:
        print(f"Source IP: {ip_address}")
    else:
        print("Source IP: Not set (will not use source IP binding for this account)")

    # Auto-generate account_id and vmta_name (with option to override)
    default_account_id = f"{provider}_{email.replace('@', '_').replace('.', '_')}"
    account_id = input(f"Account ID [default: {default_account_id}]: ").strip() or default_account_id

    default_vmta_name = f"vmta-{provider}-{email.split('@')[0]}"
    vmta_name = input(f"VMTA Name [default: {default_vmta_name}]: ").strip() or default_vmta_name

    # Client ID
    while True:
        client_id = input("Client ID: ").strip()
        if client_id:
            break
        print("✗ Client ID cannot be empty.")

    # Client Secret (optional for some Outlook flows)
    client_secret = input(f"Client Secret{' (optional for Outlook)' if provider == 'outlook' else ''}: ").strip()
    if provider == 'gmail' and not client_secret:
        print("✗ Client Secret is required for Gmail.")
        return None

    # Refresh Token
    while True:
        refresh_token = input("Refresh Token: ").strip()
        if refresh_token:
            break
        print("✗ Refresh Token cannot be empty.")

    # Build account object (with all required fields)
    account = {
        'account_id': account_id,
        'email': email,
        'ip_address': ip_address,
        'vmta_name': vmta_name,
        'provider': provider,
        'oauth_endpoint': oauth_endpoint,
        'oauth_token_url': oauth_token_url,
        'client_id': client_id,
        'refresh_token': refresh_token
    }

    # Only add client_secret if provided
    if client_secret:
        account['client_secret'] = client_secret

    return account


def load_accounts(accounts_path: Path) -> list:
    """Load existing accounts from JSON file"""
    if not accounts_path.exists():
        return []

    try:
        with open(accounts_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Handle both array and object formats
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return list(data.values()) if data else []
            else:
                return []
    except json.JSONDecodeError:
        print(f"✗ Warning: {accounts_path} contains invalid JSON. Starting fresh.")
        return []
    except Exception as e:
        print(f"✗ Error loading {accounts_path}: {e}")
        return []


def save_accounts(accounts_path: Path, accounts: list) -> bool:
    """Save accounts to JSON file"""
    try:
        # Create parent directory if it doesn't exist
        accounts_path.parent.mkdir(parents=True, exist_ok=True)

        # Save with pretty formatting
        with open(accounts_path, 'w', encoding='utf-8') as f:
            json.dump(accounts, f, indent=2, ensure_ascii=False)

        return True
    except Exception as e:
        print(f"✗ Error saving {accounts_path}: {e}")
        return False


async def main():
    """Main entry point"""
    # Get accounts.json path
    if len(sys.argv) > 1:
        accounts_path = Path(sys.argv[1])
    else:
        # Try to find accounts.json using Settings logic
        accounts_path = Settings.get_config_path('accounts.json')

    print(f"Accounts file: {accounts_path}")

    # Prompt for account details
    account = prompt_account_details()
    if not account:
        print("\n✗ Failed to collect account details.")
        sys.exit(1)

    # Ask if user wants to verify credentials
    verify = input("\nVerify OAuth2 credentials? (y/n) [y]: ").strip().lower()
    if verify != 'n':
        success, message = await verify_oauth_credentials(account)
        if not success:
            print(f"\n✗ Verification failed: {message}")
            proceed = input("\nAdd account anyway? (y/n) [n]: ").strip().lower()
            if proceed != 'y':
                print("✗ Account not added.")
                sys.exit(1)

    # Load existing accounts
    accounts = load_accounts(accounts_path)

    # Check for duplicate email
    existing_emails = [acc.get('email') for acc in accounts]
    if account['email'] in existing_emails:
        print(f"\n⚠ Warning: Account {account['email']} already exists.")
        overwrite = input("Overwrite existing account? (y/n) [n]: ").strip().lower()
        if overwrite == 'y':
            # Remove old account
            accounts = [acc for acc in accounts if acc.get('email') != account['email']]
        else:
            print("✗ Account not added.")
            sys.exit(1)

    # Add new account
    accounts.append(account)

    # Save to file
    if save_accounts(accounts_path, accounts):
        print(f"\n✓ Account {account['email']} added successfully!")
        print(f"✓ Total accounts: {len(accounts)}")
        print(f"✓ Saved to: {accounts_path}")

        # Show next steps
        print("\n" + "="*60)
        print("NEXT STEPS:")
        print("="*60)
        print("1. Restart the XOAUTH2 proxy to load the new account:")
        print("   python xoauth2_proxy_v2.py --accounts accounts.json")
        print("\n2. Or send SIGHUP signal to reload accounts without restart:")
        print("   kill -HUP <pid>")
        print("\n3. Test the account:")
        print(f"   swaks --server 127.0.0.1:2525 --auth-user {account['email']} \\")
        print("         --from test@example.com --to recipient@example.com")
        print("="*60)
    else:
        print(f"\n✗ Failed to save accounts to {accounts_path}")
        sys.exit(1)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n✗ Cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
