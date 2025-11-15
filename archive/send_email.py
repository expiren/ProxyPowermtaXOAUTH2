#!/usr/bin/env python3
"""
Send email through PowerMTA SMTP relay with OAuth2

Architecture:
    Your Code (this script)
        ↓ SMTP (port 25/587)
    PowerMTA (127.0.0.1:25 or remote server)
        ├─ Receives email
        └─ Routes to XOAUTH2 proxy (port 2525)
           ├─ Proxy validates OAuth2 token
           └─ Proxy returns 235 OK
    PowerMTA forwards to Gmail/Outlook SMTP servers
        ↓
    Email delivered
"""

import smtplib
import json
import argparse
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path


def load_accounts(config_path: str) -> dict:
    """Load accounts from accounts.json"""
    try:
        with open(config_path, 'r') as f:
            data = json.load(f)
            # Return as dict indexed by email for easy lookup
            return {acc['email']: acc for acc in data.get('accounts', [])}
    except FileNotFoundError:
        print(f"[ERROR] Config file not found: {config_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid JSON in config: {e}")
        sys.exit(1)


def send_email(
    smtp_host: str,
    smtp_port: int,
    sender_email: str,
    recipient_email: str,
    subject: str,
    body: str,
    html: bool = False,
    dry_run: bool = False
) -> bool:
    """
    Send an email through PowerMTA

    Args:
        smtp_host: PowerMTA server address (e.g., 127.0.0.1 or 37.27.3.136)
        smtp_port: PowerMTA SMTP port (25 or 587)
        sender_email: From address (must be one of your configured accounts)
        recipient_email: To address
        subject: Email subject
        body: Email body (text or HTML)
        html: If True, treat body as HTML
        dry_run: If True, don't actually send (just test connection)

    Returns:
        True if successful, False if failed
    """

    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = recipient_email

        # Add body
        msg_part = MIMEText(body, 'html' if html else 'plain')
        msg.attach(msg_part)

        # Connect to PowerMTA
        print(f"[*] Connecting to {smtp_host}:{smtp_port}...")

        # Use SMTP (not SMTP_SSL) because PowerMTA handles TLS upgrade
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
        server.set_debuglevel(1)  # Print SMTP conversation

        print(f"[*] Server response: {server.helo()}")
        print(f"[*] Capabilities: {server.esmtp_features}")

        # Check if authentication is needed
        if 'auth' in server.esmtp_features or 'AUTH' in str(server.esmtp_features):
            print(f"[*] Authenticating as {sender_email}...")
            # PowerMTA will route AUTH to proxy for token validation
            server.auth_plain(sender_email, 'placeholder')
            print("[OK] Authentication successful")

        if not dry_run:
            print(f"[*] Sending email from {sender_email} to {recipient_email}...")
            server.sendmail(sender_email, recipient_email, msg.as_string())
            print("[OK] Email sent successfully")
        else:
            print("[*] DRY-RUN MODE: Email not actually sent")

        server.quit()
        return True

    except smtplib.SMTPAuthenticationError as e:
        print(f"[ERROR] Authentication failed: {e}")
        print(f"        Check that {sender_email} is in accounts.json")
        print(f"        Check that OAuth2 token is valid and not expired")
        return False
    except smtplib.SMTPException as e:
        print(f"[ERROR] SMTP error: {e}")
        return False
    except ConnectionRefusedError:
        print(f"[ERROR] Cannot connect to {smtp_host}:{smtp_port}")
        print(f"        Is PowerMTA running? Check firewall rules.")
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Send email through PowerMTA with OAuth2')

    parser.add_argument(
        '--host',
        default='127.0.0.1',
        help='PowerMTA server address (default: 127.0.0.1)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=25,
        help='PowerMTA SMTP port (default: 25)'
    )
    parser.add_argument(
        '--config',
        default='accounts.json',
        help='Path to accounts.json (default: accounts.json)'
    )
    parser.add_argument(
        '--from',
        dest='sender_email',
        required=True,
        help='Sender email address (must be in accounts.json)'
    )
    parser.add_argument(
        '--to',
        dest='recipient_email',
        required=True,
        help='Recipient email address'
    )
    parser.add_argument(
        '--subject',
        required=True,
        help='Email subject'
    )
    parser.add_argument(
        '--body',
        required=True,
        help='Email body text'
    )
    parser.add_argument(
        '--html',
        action='store_true',
        help='Treat body as HTML'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Test connection without sending'
    )

    args = parser.parse_args()

    # Verify sender is in accounts
    print(f"[*] Loading accounts from {args.config}...")
    accounts = load_accounts(args.config)

    if args.sender_email not in accounts:
        print(f"[ERROR] {args.sender_email} not found in {args.config}")
        print(f"[ERROR] Available accounts:")
        for email in sorted(accounts.keys()):
            print(f"        - {email}")
        sys.exit(1)

    account = accounts[args.sender_email]
    print(f"[OK] Found account: {args.sender_email} (provider: {account['provider']})")

    # Send email
    success = send_email(
        smtp_host=args.host,
        smtp_port=args.port,
        sender_email=args.sender_email,
        recipient_email=args.recipient_email,
        subject=args.subject,
        body=args.body,
        html=args.html,
        dry_run=args.dry_run
    )

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
