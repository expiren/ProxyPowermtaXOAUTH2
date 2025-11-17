#!/usr/bin/env python3
"""
XOAUTH2 Proxy Account Manager
Complete interactive application for managing email accounts
"""

import sys
import os
import re
import requests
from typing import Dict, Any, Optional, List
import json
from datetime import datetime


class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class AccountManager:
    """Interactive account management application"""

    def __init__(self, proxy_url: str = None):
        """Initialize account manager"""
        self.proxy_url = proxy_url or os.getenv('XOAUTH2_PROXY_URL', 'http://127.0.0.1:9090')
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json'})

    def print_header(self, text: str):
        """Print formatted header"""
        print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*70}")
        print(f"{text:^70}")
        print(f"{'='*70}{Colors.ENDC}\n")

    def print_success(self, text: str):
        """Print success message"""
        print(f"{Colors.GREEN}✓ {text}{Colors.ENDC}")

    def print_error(self, text: str):
        """Print error message"""
        print(f"{Colors.RED}✗ {text}{Colors.ENDC}")

    def print_info(self, text: str):
        """Print info message"""
        print(f"{Colors.CYAN}ℹ {text}{Colors.ENDC}")

    def print_warning(self, text: str):
        """Print warning message"""
        print(f"{Colors.YELLOW}⚠ {text}{Colors.ENDC}")

    def validate_email(self, email: str) -> bool:
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    def check_connection(self) -> bool:
        """Check if proxy server is reachable"""
        try:
            response = self.session.get(f"{self.proxy_url}/health", timeout=5)
            if response.status_code == 200:
                return True
            else:
                self.print_error(f"Proxy returned status {response.status_code}")
                return False
        except requests.exceptions.ConnectionError:
            self.print_error(f"Cannot connect to proxy at {self.proxy_url}")
            self.print_info("Make sure the XOAUTH2 proxy is running")
            return False
        except Exception as e:
            self.print_error(f"Connection error: {e}")
            return False

    def list_accounts(self) -> Optional[List[Dict]]:
        """List all accounts"""
        try:
            response = self.session.get(f"{self.proxy_url}/admin/accounts", timeout=10)

            if response.status_code == 200:
                result = response.json()
                accounts = result.get('accounts', [])

                if not accounts:
                    self.print_warning("No accounts found")
                    return []

                self.print_header("CURRENT ACCOUNTS")

                for idx, account in enumerate(accounts, 1):
                    email = account.get('email', 'N/A')
                    provider = account.get('provider', 'N/A')
                    endpoint = account.get('oauth_endpoint', 'N/A')

                    print(f"{Colors.BOLD}{idx}. {email}{Colors.ENDC}")
                    print(f"   Provider: {Colors.CYAN}{provider}{Colors.ENDC}")
                    print(f"   Endpoint: {endpoint}")
                    print()

                self.print_success(f"Total accounts: {len(accounts)}")
                return accounts
            else:
                error = response.json().get('error', 'Unknown error')
                self.print_error(f"Failed to list accounts: {error}")
                return None

        except Exception as e:
            self.print_error(f"Error listing accounts: {e}")
            return None

    def add_account(self):
        """Add a new account interactively"""
        self.print_header("ADD NEW ACCOUNT")

        # Email
        while True:
            email = input(f"{Colors.CYAN}Email address: {Colors.ENDC}").strip()
            if not email:
                self.print_error("Email cannot be empty")
                continue
            if not self.validate_email(email):
                self.print_error("Invalid email format")
                continue
            break

        # Provider
        while True:
            provider = input(f"{Colors.CYAN}Provider (gmail/outlook): {Colors.ENDC}").strip().lower()
            if provider in ['gmail', 'outlook']:
                break
            self.print_error("Provider must be 'gmail' or 'outlook'")

        self.print_info(f"Detected endpoint: smtp.{provider}.com:587")

        # Client ID
        while True:
            client_id = input(f"{Colors.CYAN}Client ID: {Colors.ENDC}").strip()
            if client_id:
                break
            self.print_error("Client ID cannot be empty")

        # Client Secret
        if provider == 'gmail':
            while True:
                client_secret = input(f"{Colors.CYAN}Client Secret: {Colors.ENDC}").strip()
                if client_secret:
                    break
                self.print_error("Client Secret is required for Gmail")
        else:
            client_secret = input(f"{Colors.CYAN}Client Secret (optional for Outlook): {Colors.ENDC}").strip()

        # Refresh Token
        while True:
            refresh_token = input(f"{Colors.CYAN}Refresh Token: {Colors.ENDC}").strip()
            if refresh_token:
                break
            self.print_error("Refresh Token cannot be empty")

        # Verify credentials?
        verify_input = input(f"{Colors.YELLOW}Verify OAuth2 credentials before adding? (Y/n): {Colors.ENDC}").strip().lower()
        verify = verify_input != 'n'

        # Build request
        data = {
            'email': email,
            'provider': provider,
            'client_id': client_id,
            'refresh_token': refresh_token,
            'verify': verify
        }

        if client_secret:
            data['client_secret'] = client_secret

        # Send request
        try:
            print(f"\n{Colors.CYAN}Adding account...{Colors.ENDC}")
            response = self.session.post(
                f"{self.proxy_url}/admin/accounts",
                json=data,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                self.print_success(result['message'])
                self.print_info(f"Total accounts: {result['total_accounts']}")

                # Show account details
                account_info = result.get('account', {})
                print(f"\n{Colors.BOLD}Account Details:{Colors.ENDC}")
                print(f"  Email: {account_info.get('email')}")
                print(f"  Provider: {account_info.get('provider')}")
                print(f"  Endpoint: {account_info.get('oauth_endpoint')}")

                return True
            else:
                error_data = response.json()
                self.print_error(f"Failed to add account: {error_data.get('error', 'Unknown error')}")
                return False

        except requests.exceptions.Timeout:
            self.print_error("Request timeout - verification may take longer")
            return False
        except Exception as e:
            self.print_error(f"Error adding account: {e}")
            return False

    def verify_account(self):
        """Verify a specific account's OAuth2 credentials"""
        self.print_header("VERIFY ACCOUNT")

        # List accounts first
        accounts = self.list_accounts()
        if not accounts:
            return

        email = input(f"\n{Colors.CYAN}Enter email to verify: {Colors.ENDC}").strip()

        if not email:
            self.print_error("Email cannot be empty")
            return

        # Find account
        account = next((acc for acc in accounts if acc['email'] == email), None)

        if not account:
            self.print_error(f"Account {email} not found")
            return

        self.print_info(f"Verifying {email}...")
        self.print_warning("Note: This requires the account to be in accounts.json with full credentials")
        self.print_info("Use 'Delete Invalid Accounts' from main menu to test all accounts")

    def delete_account(self):
        """Delete a specific account"""
        self.print_header("DELETE ACCOUNT")

        # List accounts first
        accounts = self.list_accounts()
        if not accounts:
            return

        email = input(f"\n{Colors.CYAN}Enter email to delete: {Colors.ENDC}").strip()

        if not email:
            self.print_error("Email cannot be empty")
            return

        if not self.validate_email(email):
            self.print_error("Invalid email format")
            return

        # Confirm deletion
        confirm = input(f"{Colors.YELLOW}Are you sure you want to delete {email}? (y/N): {Colors.ENDC}").strip().lower()

        if confirm != 'y':
            self.print_info("Deletion cancelled")
            return

        # Send delete request
        try:
            print(f"\n{Colors.CYAN}Deleting account...{Colors.ENDC}")
            response = self.session.delete(
                f"{self.proxy_url}/admin/accounts/{email}",
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                self.print_success(result['message'])
                self.print_info(f"Remaining accounts: {result['total_accounts']}")
                return True
            elif response.status_code == 404:
                error = response.json().get('error', 'Account not found')
                self.print_error(error)
                return False
            else:
                error = response.json().get('error', 'Unknown error')
                self.print_error(f"Failed to delete account: {error}")
                return False

        except Exception as e:
            self.print_error(f"Error deleting account: {e}")
            return False

    def delete_all_accounts(self):
        """Delete all accounts"""
        self.print_header("DELETE ALL ACCOUNTS")

        # List accounts first
        accounts = self.list_accounts()
        if not accounts:
            return

        self.print_warning(f"This will delete ALL {len(accounts)} accounts!")
        confirm1 = input(f"{Colors.YELLOW}Type 'DELETE ALL' to confirm: {Colors.ENDC}").strip()

        if confirm1 != 'DELETE ALL':
            self.print_info("Deletion cancelled")
            return

        confirm2 = input(f"{Colors.RED}Are you ABSOLUTELY sure? (yes/no): {Colors.ENDC}").strip().lower()

        if confirm2 != 'yes':
            self.print_info("Deletion cancelled")
            return

        # Send delete request
        try:
            print(f"\n{Colors.CYAN}Deleting all accounts...{Colors.ENDC}")
            response = self.session.delete(
                f"{self.proxy_url}/admin/accounts",
                params={'confirm': 'true'},
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                self.print_success(result['message'])
                return True
            else:
                error = response.json().get('error', 'Unknown error')
                self.print_error(f"Failed to delete accounts: {error}")
                return False

        except Exception as e:
            self.print_error(f"Error deleting accounts: {e}")
            return False

    def delete_invalid_accounts(self):
        """Delete accounts with bad OAuth2 credentials"""
        self.print_header("DELETE INVALID ACCOUNTS")

        # List accounts first
        accounts = self.list_accounts()
        if not accounts:
            return

        self.print_info(f"Testing {len(accounts)} accounts for validity...")
        self.print_warning("This may take a few moments...")

        # Send delete request
        try:
            response = self.session.delete(
                f"{self.proxy_url}/admin/accounts/invalid",
                timeout=60  # Longer timeout for testing multiple accounts
            )

            if response.status_code == 200:
                result = response.json()

                if result['deleted_count'] == 0:
                    self.print_success(result['message'])
                    self.print_info("All accounts have valid OAuth2 credentials")
                else:
                    self.print_success(result['message'])

                    print(f"\n{Colors.RED}Deleted accounts:{Colors.ENDC}")
                    for email in result['deleted_accounts']:
                        print(f"  ✗ {email}")

                    self.print_info(f"Remaining accounts: {result['total_accounts']}")

                return True
            else:
                error = response.json().get('error', 'Unknown error')
                self.print_error(f"Failed to delete invalid accounts: {error}")
                return False

        except requests.exceptions.Timeout:
            self.print_error("Request timeout - testing many accounts may take longer")
            return False
        except Exception as e:
            self.print_error(f"Error deleting invalid accounts: {e}")
            return False

    def show_main_menu(self):
        """Show main menu"""
        self.print_header("XOAUTH2 PROXY - ACCOUNT MANAGER")

        print(f"{Colors.BOLD}Proxy URL:{Colors.ENDC} {Colors.CYAN}{self.proxy_url}{Colors.ENDC}")
        print()

        menu_options = [
            ("1", "List All Accounts", Colors.CYAN),
            ("2", "Add New Account", Colors.GREEN),
            ("3", "Delete Account", Colors.YELLOW),
            ("4", "Delete All Accounts", Colors.RED),
            ("5", "Delete Invalid Accounts", Colors.YELLOW),
            ("6", "Change Proxy URL", Colors.BLUE),
            ("7", "Test Connection", Colors.CYAN),
            ("0", "Exit", Colors.RED),
        ]

        for key, label, color in menu_options:
            print(f"  {color}{key}.{Colors.ENDC} {label}")

        print()

    def change_proxy_url(self):
        """Change proxy URL"""
        self.print_header("CHANGE PROXY URL")

        print(f"Current URL: {Colors.CYAN}{self.proxy_url}{Colors.ENDC}")
        new_url = input(f"\n{Colors.CYAN}Enter new proxy URL: {Colors.ENDC}").strip()

        if not new_url:
            self.print_info("URL not changed")
            return

        # Validate URL format
        if not new_url.startswith('http://') and not new_url.startswith('https://'):
            self.print_error("URL must start with http:// or https://")
            return

        self.proxy_url = new_url
        self.print_success(f"Proxy URL changed to: {self.proxy_url}")

        # Test connection
        if self.check_connection():
            self.print_success("Connection successful!")
        else:
            self.print_warning("Could not connect to new URL")

    def test_connection(self):
        """Test connection to proxy"""
        self.print_header("TEST CONNECTION")

        print(f"Testing connection to: {Colors.CYAN}{self.proxy_url}{Colors.ENDC}")

        if self.check_connection():
            self.print_success("Connection successful!")

            # Get server info
            try:
                response = self.session.get(f"{self.proxy_url}/health", timeout=5)
                data = response.json()
                print(f"\n{Colors.BOLD}Server Info:{Colors.ENDC}")
                print(f"  Status: {Colors.GREEN}{data.get('status')}{Colors.ENDC}")
                print(f"  Service: {data.get('service')}")
            except:
                pass

            # Get account count
            try:
                response = self.session.get(f"{self.proxy_url}/admin/accounts", timeout=5)
                data = response.json()
                account_count = data.get('total_accounts', 0)
                print(f"  Accounts: {Colors.CYAN}{account_count}{Colors.ENDC}")
            except:
                pass
        else:
            self.print_error("Connection failed!")

    def run(self):
        """Run the interactive account manager"""
        # Check connection first
        print(f"\n{Colors.BOLD}XOAUTH2 Proxy Account Manager{Colors.ENDC}")
        print(f"Connecting to: {Colors.CYAN}{self.proxy_url}{Colors.ENDC}\n")

        if not self.check_connection():
            self.print_error("Cannot connect to proxy server")
            self.print_info("Please check:")
            print("  1. Proxy is running: python xoauth2_proxy_v2.py")
            print(f"  2. URL is correct: {self.proxy_url}")
            print("  3. Firewall allows connections")
            sys.exit(1)

        self.print_success("Connected to proxy server!")

        # Main loop
        while True:
            try:
                self.show_main_menu()

                choice = input(f"{Colors.BOLD}Select option: {Colors.ENDC}").strip()

                if choice == '1':
                    self.list_accounts()
                elif choice == '2':
                    self.add_account()
                elif choice == '3':
                    self.delete_account()
                elif choice == '4':
                    self.delete_all_accounts()
                elif choice == '5':
                    self.delete_invalid_accounts()
                elif choice == '6':
                    self.change_proxy_url()
                elif choice == '7':
                    self.test_connection()
                elif choice == '0':
                    self.print_info("Goodbye!")
                    sys.exit(0)
                else:
                    self.print_error("Invalid option")

                # Pause before showing menu again
                input(f"\n{Colors.CYAN}Press Enter to continue...{Colors.ENDC}")

            except KeyboardInterrupt:
                print(f"\n\n{Colors.YELLOW}Interrupted by user{Colors.ENDC}")
                sys.exit(0)
            except Exception as e:
                self.print_error(f"Unexpected error: {e}")
                import traceback
                traceback.print_exc()


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description='XOAUTH2 Proxy Account Manager',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python account_manager.py
  python account_manager.py --url http://192.168.1.100:9090
  python account_manager.py --url http://proxy.example.com:9090

Environment Variables:
  XOAUTH2_PROXY_URL    Proxy URL (default: http://127.0.0.1:9090)
        """
    )

    parser.add_argument(
        '--url',
        type=str,
        help='Proxy server URL (default: http://127.0.0.1:9090)'
    )

    args = parser.parse_args()

    # Create and run manager
    manager = AccountManager(proxy_url=args.url)
    manager.run()


if __name__ == '__main__':
    main()
