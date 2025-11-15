#!/usr/bin/env python3
"""
Import Accounts from CSV/Data Format
Converts account data into accounts.json format for XOAUTH2 proxy
"""

import json
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Any
import csv
import io


class AccountImporter:
    """Imports accounts from CSV/data format"""

    # Provider detection based on email domain
    PROVIDER_MAPPING = {
        'gmail.com': 'gmail',
        'googlemail.com': 'gmail',
        'hotmail.com': 'outlook',
        'outlook.com': 'outlook',
        'live.com': 'outlook',
        'msn.com': 'outlook',
    }

    # OAuth endpoints by provider
    OAUTH_ENDPOINTS = {
        'gmail': {
            'endpoint': 'smtp.gmail.com:587',
            'token_url': 'https://oauth2.googleapis.com/token'
        },
        'outlook': {
            'endpoint': 'smtp.office365.com:587',
            'token_url': 'https://login.live.com/oauth20_token.srf'
        }
    }

    def __init__(self, start_ip: str = '192.168.1.100', start_port: int = 2525):
        self.accounts = []
        self.start_ip = start_ip
        self.start_port = start_port
        self.ip_counter = self._ip_to_int(start_ip)

    def _ip_to_int(self, ip: str) -> int:
        """Convert IP address to integer"""
        parts = ip.split('.')
        return (int(parts[0]) << 24) + (int(parts[1]) << 16) + (int(parts[2]) << 8) + int(parts[3])

    def _int_to_ip(self, ip_int: int) -> str:
        """Convert integer to IP address"""
        return f"{(ip_int >> 24) & 255}.{(ip_int >> 16) & 255}.{(ip_int >> 8) & 255}.{ip_int & 255}"

    def _get_next_ip(self) -> str:
        """Get next IP address"""
        ip = self._int_to_ip(self.ip_counter)
        self.ip_counter += 1
        return ip

    def _detect_provider(self, email: str) -> str:
        """Detect provider from email domain"""
        domain = email.split('@')[1].lower() if '@' in email else 'gmail.com'
        return self.PROVIDER_MAPPING.get(domain, 'gmail')

    def parse_line(self, line: str) -> Dict[str, Any]:
        """
        Parse a single data line
        Format: email,account_id,refresh_token,client_id,timestamp,hostname
        """
        parts = line.strip().split(',')

        if len(parts) < 4:
            raise ValueError(f"Invalid format. Expected at least 4 fields, got {len(parts)}")

        email = parts[0].strip()
        account_id = parts[1].strip()
        refresh_token = parts[2].strip()
        client_id = parts[3].strip()

        if not email or not account_id or not refresh_token or not client_id:
            raise ValueError("Email, account_id, refresh_token, and client_id cannot be empty")

        # Detect provider
        provider = self._detect_provider(email)

        # Generate IP address
        ip_address = self._get_next_ip()

        # Create vmta_name from account_id
        vmta_name = f"vmta-{account_id}"

        # Get provider-specific endpoints
        oauth_config = self.OAUTH_ENDPOINTS[provider]

        # Build account
        account = {
            "account_id": account_id,
            "email": email,
            "ip_address": ip_address,
            "vmta_name": vmta_name,
            "provider": provider,
            "client_id": client_id,
            "client_secret": "" if provider == "outlook" else "",  # Outlook doesn't use client_secret
            "refresh_token": refresh_token,
            "oauth_endpoint": oauth_config['endpoint'],
            "oauth_token_url": oauth_config['token_url'],
            "max_concurrent_messages": 10,
            "max_messages_per_hour": 10000
        }

        return account

    def import_from_file(self, input_file: str, skip_errors: bool = False) -> int:
        """Import accounts from file"""
        count = 0
        errors = []

        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue

                    try:
                        account = self.parse_line(line)
                        self.accounts.append(account)
                        count += 1
                        print(f"[{count}] Imported: {account['email']} (account_id: {account['account_id']}, provider: {account['provider']})")
                    except ValueError as e:
                        error_msg = f"Line {line_num}: {e}"
                        errors.append(error_msg)
                        print(f"[ERROR] {error_msg}")
                        if not skip_errors:
                            raise

        except FileNotFoundError:
            print(f"Error: File not found: {input_file}", file=sys.stderr)
            return -1
        except Exception as e:
            print(f"Error reading file: {e}", file=sys.stderr)
            return -1

        if errors:
            print(f"\nWarning: {len(errors)} errors occurred during import")
            if skip_errors:
                print("Continuing with valid accounts...")

        return count

    def import_from_string(self, data: str) -> int:
        """Import accounts from string data"""
        count = 0
        errors = []

        for line_num, line in enumerate(data.strip().split('\n'), 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            try:
                account = self.parse_line(line)
                self.accounts.append(account)
                count += 1
                print(f"[{count}] Imported: {account['email']} (account_id: {account['account_id']}, provider: {account['provider']})")
            except ValueError as e:
                error_msg = f"Line {line_num}: {e}"
                errors.append(error_msg)
                print(f"[ERROR] {error_msg}")

        if errors:
            print(f"\nWarning: {len(errors)} errors occurred during import")

        return count

    def validate(self) -> bool:
        """Validate imported accounts"""
        if not self.accounts:
            print("Error: No accounts imported")
            return False

        # Check for duplicates
        emails = [acc['email'] for acc in self.accounts]
        account_ids = [acc['account_id'] for acc in self.accounts]

        email_dupes = [e for e in emails if emails.count(e) > 1]
        id_dupes = [id for id in account_ids if account_ids.count(id) > 1]

        if email_dupes:
            print(f"Error: Duplicate emails: {set(email_dupes)}")
            return False

        if id_dupes:
            print(f"Error: Duplicate account IDs: {set(id_dupes)}")
            return False

        print(f"[OK] Validation passed: {len(self.accounts)} unique accounts")
        return True

    def save_to_json(self, output_file: str) -> bool:
        """Save accounts to JSON file"""
        try:
            output_data = {"accounts": self.accounts}

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2)

            print(f"[OK] Saved {len(self.accounts)} accounts to {output_file}")

            # Print summary
            gmail_count = sum(1 for acc in self.accounts if acc['provider'] == 'gmail')
            outlook_count = sum(1 for acc in self.accounts if acc['provider'] == 'outlook')

            print(f"\nSummary:")
            print(f"  Total accounts: {len(self.accounts)}")
            print(f"  Gmail accounts: {gmail_count}")
            print(f"  Outlook accounts: {outlook_count}")
            print(f"  IP range: {self.accounts[0]['ip_address']} to {self.accounts[-1]['ip_address']}")

            return True

        except Exception as e:
            print(f"Error saving JSON: {e}", file=sys.stderr)
            return False

    def print_summary(self):
        """Print accounts summary"""
        if not self.accounts:
            print("No accounts to display")
            return

        print(f"\n{'='*80}")
        print(f"Imported Accounts Summary ({len(self.accounts)} total)")
        print(f"{'='*80}")

        for acc in self.accounts:
            print(f"\nAccount ID: {acc['account_id']}")
            print(f"  Email:    {acc['email']}")
            print(f"  Provider: {acc['provider']}")
            print(f"  IP:       {acc['ip_address']}")
            print(f"  VMTA:     {acc['vmta_name']}")
            print(f"  Client:   {acc['client_id'][:20]}...")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Import accounts from CSV/data format and generate accounts.json',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:

  # Import from file
  python import_accounts.py -i accounts_data.txt -o accounts.json

  # Import from stdin (paste data)
  python import_accounts.py -o accounts.json

  # Data format (comma-separated):
  email,account_id,refresh_token,client_id,timestamp,hostname

  Example line:
  pilareffiema0407@hotmail.com,sUMYSfcav2,M.C519_BAY...,9e5f94bc-e8a4-4e73-b8be-63364c29d753,2025-09-24T00:00:00.0000000Z,localhost
        '''
    )

    parser.add_argument(
        '-i', '--input',
        help='Input file with account data (if not provided, reads from stdin)'
    )
    parser.add_argument(
        '-o', '--output',
        default='accounts.json',
        help='Output accounts.json file (default: accounts.json)'
    )
    parser.add_argument(
        '--start-ip',
        default='192.168.1.100',
        help='Starting IP address (default: 192.168.1.100)'
    )
    parser.add_argument(
        '--skip-errors',
        action='store_true',
        help='Skip lines with errors and continue'
    )
    parser.add_argument(
        '--validate-only',
        action='store_true',
        help='Only validate, do not save'
    )
    parser.add_argument(
        '--summary',
        action='store_true',
        help='Print summary after import'
    )

    args = parser.parse_args()

    # Create importer
    importer = AccountImporter(start_ip=args.start_ip)

    # Import data
    print("Importing accounts...")
    if args.input:
        count = importer.import_from_file(args.input, skip_errors=args.skip_errors)
    else:
        print("Reading from stdin (paste data, then Ctrl+D when done):")
        data = sys.stdin.read()
        count = importer.import_from_string(data)

    if count <= 0:
        print("No accounts imported")
        sys.exit(1)

    print(f"\n[OK] Successfully imported {count} accounts")

    # Validate
    if not importer.validate():
        sys.exit(1)

    # Save or just display
    if args.validate_only:
        print("\nValidation passed (--validate-only specified, not saving)")
    else:
        if not importer.save_to_json(args.output):
            sys.exit(1)

    # Print summary
    if args.summary or True:  # Always print summary
        importer.print_summary()

    print(f"\n[OK] Done!")


if __name__ == '__main__':
    main()
