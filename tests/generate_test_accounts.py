"""
Generate test accounts.json for load testing

This script creates a test accounts.json file with multiple test accounts
for use with the SMTP load testing tools.

The generated accounts are:
- Gmail test accounts (for testing Gmail OAuth2 flow)
- Outlook test accounts (for testing Outlook OAuth2 flow)

NOTE: These accounts use PLACEHOLDER credentials. You must replace them with
real OAuth2 credentials from your actual Gmail/Outlook accounts.

Usage:
    python generate_test_accounts.py                    # Interactive mode
    python generate_test_accounts.py --skip-input      # Use defaults
    python generate_test_accounts.py --output my_accounts.json
"""

import json
import argparse
from pathlib import Path
from typing import List, Dict, Any


# Default test accounts with PLACEHOLDER credentials
# You MUST replace these with real OAuth2 credentials!
DEFAULT_TEST_ACCOUNTS = [
    {
        "account_id": "gmail_test_01",
        "email": "test.account1@gmail.com",
        "provider": "gmail",
        "oauth_endpoint": "smtp.gmail.com:587",
        "oauth_token_url": "https://oauth2.googleapis.com/token",
        "client_id": "YOUR_GMAIL_CLIENT_ID.apps.googleusercontent.com",
        "client_secret": "YOUR_GMAIL_CLIENT_SECRET",
        "refresh_token": "YOUR_GMAIL_REFRESH_TOKEN",
        "ip_address": "",
        "vmta_name": "vmta-gmail-test-01"
    },
    {
        "account_id": "gmail_test_02",
        "email": "test.account2@gmail.com",
        "provider": "gmail",
        "oauth_endpoint": "smtp.gmail.com:587",
        "oauth_token_url": "https://oauth2.googleapis.com/token",
        "client_id": "YOUR_GMAIL_CLIENT_ID.apps.googleusercontent.com",
        "client_secret": "YOUR_GMAIL_CLIENT_SECRET",
        "refresh_token": "YOUR_GMAIL_REFRESH_TOKEN_2",
        "ip_address": "",
        "vmta_name": "vmta-gmail-test-02"
    },
    {
        "account_id": "outlook_test_01",
        "email": "test.account1@outlook.com",
        "provider": "outlook",
        "oauth_endpoint": "smtp.office365.com:587",
        "oauth_token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "client_id": "YOUR_OUTLOOK_CLIENT_ID",
        "refresh_token": "YOUR_OUTLOOK_REFRESH_TOKEN",
        "ip_address": "",
        "vmta_name": "vmta-outlook-test-01"
    },
    {
        "account_id": "outlook_test_02",
        "email": "test.account2@outlook.com",
        "provider": "outlook",
        "oauth_endpoint": "smtp.office365.com:587",
        "oauth_token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "client_id": "YOUR_OUTLOOK_CLIENT_ID",
        "refresh_token": "YOUR_OUTLOOK_REFRESH_TOKEN_2",
        "ip_address": "",
        "vmta_name": "vmta-outlook-test-02"
    }
]


def prompt_for_account() -> Dict[str, Any]:
    """Interactively prompt user for account details"""
    print("\n" + "=" * 80)
    print("ADD NEW TEST ACCOUNT")
    print("=" * 80)

    email = input("Email address (e.g., test@gmail.com): ").strip()
    if not email or "@" not in email:
        print("ERROR: Invalid email address")
        return None

    print("\nProvider options: gmail, outlook")
    provider = input("Provider (gmail/outlook): ").strip().lower()
    if provider not in ["gmail", "outlook"]:
        print("ERROR: Invalid provider")
        return None

    client_id = input("Client ID (from OAuth2 app): ").strip()
    if not client_id:
        print("ERROR: Client ID required")
        return None

    refresh_token = input("Refresh token (from OAuth2 authorization): ").strip()
    if not refresh_token:
        print("ERROR: Refresh token required")
        return None

    client_secret = ""
    if provider == "gmail":
        client_secret = input("Client secret (from OAuth2 app): ").strip()
        if not client_secret:
            print("ERROR: Client secret required for Gmail")
            return None

    ip_address = input("IP address (optional, leave blank for auto-assign): ").strip()

    # Generate account_id and vmta_name
    account_id = f"{provider}_{email.split('@')[0]}_{email.split('@')[1].replace('.', '_')}"
    vmta_name = f"vmta-{provider}-{email.split('@')[0]}"

    account = {
        "account_id": account_id,
        "email": email,
        "provider": provider,
        "oauth_endpoint": "smtp.gmail.com:587" if provider == "gmail" else "smtp.office365.com:587",
        "oauth_token_url": "https://oauth2.googleapis.com/token" if provider == "gmail" else "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "client_id": client_id,
        "refresh_token": refresh_token,
        "ip_address": ip_address,
        "vmta_name": vmta_name
    }

    if client_secret:
        account["client_secret"] = client_secret

    return account


def validate_accounts(accounts: List[Dict[str, Any]]) -> bool:
    """Validate that accounts have required fields"""
    if not accounts:
        print("ERROR: No accounts provided")
        return False

    required_fields = ["email", "provider", "client_id", "refresh_token", "oauth_endpoint"]

    for i, account in enumerate(accounts):
        email = account.get("email", "")
        provider = account.get("provider", "")

        # Check required fields
        for field in required_fields:
            if field not in account or not account[field]:
                print(f"ERROR: Account {i+1} ({email}) missing required field: {field}")
                return False

        # Check provider is valid
        if provider not in ["gmail", "outlook"]:
            print(f"ERROR: Account {i+1} ({email}) has invalid provider: {provider}")
            return False

        # Check Gmail requires client_secret
        if provider == "gmail" and not account.get("client_secret"):
            print(f"ERROR: Account {i+1} ({email}) is Gmail but missing client_secret")
            return False

        # Check placeholders haven't been left in
        for field in ["client_id", "refresh_token", "client_secret"]:
            if field in account and account[field].startswith("YOUR_"):
                print(f"WARNING: Account {i+1} ({email}) field '{field}' contains placeholder: {account[field]}")

    return True


def generate_accounts_interactive() -> List[Dict[str, Any]]:
    """Interactively generate accounts"""
    accounts = []

    print("\n" + "=" * 80)
    print("TEST ACCOUNTS GENERATOR")
    print("=" * 80)
    print("\nYou can use default test accounts or create custom ones.")
    print("Default accounts have PLACEHOLDER credentials that need to be replaced.")

    use_default = input("\nUse default test accounts? (y/n): ").strip().lower()

    if use_default == "y":
        accounts = DEFAULT_TEST_ACCOUNTS.copy()
        print(f"\nLoaded {len(accounts)} default test accounts")
        print_accounts_summary(accounts)
    else:
        print("\nEnter custom accounts (press Ctrl+C when done)")
        try:
            while True:
                account = prompt_for_account()
                if account:
                    accounts.append(account)
                    print(f"✓ Account added: {account['email']}")

                    add_more = input("\nAdd another account? (y/n): ").strip().lower()
                    if add_more != "y":
                        break
        except KeyboardInterrupt:
            print("\n\nAccount entry cancelled")

    return accounts


def generate_accounts_default() -> List[Dict[str, Any]]:
    """Generate with default accounts"""
    print("Using default test accounts...")
    return DEFAULT_TEST_ACCOUNTS.copy()


def print_accounts_summary(accounts: List[Dict[str, Any]]):
    """Print a summary of accounts"""
    print("\n" + "=" * 80)
    print(f"ACCOUNTS SUMMARY ({len(accounts)} accounts)")
    print("=" * 80)

    for i, account in enumerate(accounts, 1):
        print(f"\n{i}. {account['email']}")
        print(f"   Provider: {account['provider']}")
        print(f"   Account ID: {account['account_id']}")
        print(f"   Client ID: {account['client_id'][:20]}..." if len(account['client_id']) > 20 else f"   Client ID: {account['client_id']}")
        print(f"   Refresh Token: {account['refresh_token'][:20]}..." if len(account['refresh_token']) > 20 else f"   Refresh Token: {account['refresh_token']}")
        if "client_secret" in account:
            print(f"   Client Secret: {account['client_secret'][:20]}..." if len(account['client_secret']) > 20 else f"   Client Secret: {account['client_secret']}")
        if account.get("ip_address"):
            print(f"   IP Address: {account['ip_address']}")

    print("\n" + "=" * 80)


def save_accounts(accounts: List[Dict[str, Any]], output_file: str = "accounts.json") -> bool:
    """Save accounts to JSON file"""
    try:
        output_path = Path(output_file)

        # Check if file exists and warn
        if output_path.exists():
            overwrite = input(f"\n{output_file} already exists. Overwrite? (y/n): ").strip().lower()
            if overwrite != "y":
                print("Cancelled - file not overwritten")
                return False

        # Write JSON
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(accounts, f, indent=2, ensure_ascii=False)

        print(f"\n✓ Accounts saved to: {output_path.absolute()}")
        return True

    except Exception as e:
        print(f"ERROR: Failed to save accounts: {e}")
        return False


async def verify_accounts(accounts: List[Dict[str, Any]]) -> bool:
    """Verify accounts can connect (requires aiosmtplib)"""
    print("\n" + "=" * 80)
    print("VERIFY ACCOUNTS")
    print("=" * 80)

    verify = input("Verify accounts by connecting to proxy? (y/n): ").strip().lower()
    if verify != "y":
        return True

    print("\nNOTE: This requires the proxy to be running on port 2525")
    print("Make sure to start the proxy first:")
    print("  python xoauth2_proxy_v2.py --config accounts.json --port 2525")

    input("\nPress ENTER to start verification...")

    try:
        import aiosmtplib

        for i, account in enumerate(accounts, 1):
            email = account["email"]
            print(f"\n[{i}/{len(accounts)}] Verifying {email}...", end=" ")

            try:
                async with aiosmtplib.SMTP(hostname="127.0.0.1", port=2525, timeout=5) as smtp:
                    await smtp.ehlo()
                    await smtp.login(email, "test_password")  # Password doesn't matter, proxy validates OAuth2
                    print("✓ OK")
            except Exception as e:
                print(f"✗ FAILED: {str(e)[:60]}")

    except ImportError:
        print("\naiosmtplib not installed - skipping verification")
        print("Install with: pip install aiosmtplib")

    return True


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Generate test accounts.json for SMTP load testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode (default)
  python generate_test_accounts.py

  # Use default accounts without prompting
  python generate_test_accounts.py --skip-input

  # Save to custom location
  python generate_test_accounts.py --output my_test_accounts.json

  # Show what default accounts would be generated
  python generate_test_accounts.py --show-defaults
        """
    )

    parser.add_argument(
        "--output",
        type=str,
        default="accounts.json",
        help="Output file path (default: accounts.json)"
    )
    parser.add_argument(
        "--skip-input",
        action="store_true",
        help="Use default accounts without prompting"
    )
    parser.add_argument(
        "--show-defaults",
        action="store_true",
        help="Show default accounts and exit"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify accounts can connect to proxy"
    )

    args = parser.parse_args()

    # Show defaults
    if args.show_defaults:
        print_accounts_summary(DEFAULT_TEST_ACCOUNTS)
        print("\nNOTE: Replace placeholder credentials with real OAuth2 tokens!")
        return

    # Generate accounts
    if args.skip_input:
        accounts = generate_accounts_default()
    else:
        accounts = generate_accounts_interactive()

    if not accounts:
        print("ERROR: No accounts to save")
        return

    # Validate
    print("\nValidating accounts...")
    if not validate_accounts(accounts):
        print("\nWARNING: Accounts have validation issues")
        proceed = input("Proceed anyway? (y/n): ").strip().lower()
        if proceed != "y":
            return

    # Print summary
    print_accounts_summary(accounts)

    # Save
    if not save_accounts(accounts, args.output):
        return

    print("\n" + "=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print(f"\n1. Edit {args.output} and replace placeholder credentials:")
    print("   - YOUR_GMAIL_CLIENT_ID")
    print("   - YOUR_GMAIL_CLIENT_SECRET")
    print("   - YOUR_GMAIL_REFRESH_TOKEN")
    print("   - YOUR_OUTLOOK_CLIENT_ID")
    print("   - YOUR_OUTLOOK_REFRESH_TOKEN")

    print(f"\n2. Start the proxy:")
    print(f"   python xoauth2_proxy_v2.py --config {args.output} --port 2525")

    print(f"\n3. Run load tests:")
    print(f"   python test_smtp_scenarios.py --scenario quick")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
