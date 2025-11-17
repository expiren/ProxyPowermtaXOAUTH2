#!/usr/bin/env python3
"""
Simple test script to send a single email through the proxy
Use this to verify basic functionality before load testing
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import sys
import time

# Configuration
PROXY_HOST = "127.0.0.1"  # Change to your proxy IP if needed
PROXY_PORT = 2525

# Account credentials (from your accounts.json)
FROM_EMAIL = "tuyjlkb9076@hotmail.com"
FROM_PASSWORD = "placeholder"  # Password is ignored by proxy, but required by SMTP protocol

# Test email details
TO_EMAIL = "recipient@example.com"  # Change to a real email for testing
SUBJECT = "Test Email from XOAUTH2 Proxy"
BODY = "This is a test email sent through the XOAUTH2 proxy."


def send_test_email():
    """Send a single test email"""
    print(f"Connecting to proxy at {PROXY_HOST}:{PROXY_PORT}...")

    try:
        # Connect to proxy
        start_time = time.time()
        server = smtplib.SMTP(PROXY_HOST, PROXY_PORT, timeout=30)

        # Enable debug output (comment out for cleaner output)
        # server.set_debuglevel(1)

        # Say EHLO
        server.ehlo()
        print(f"✓ Connected to proxy")

        # Authenticate
        print(f"Authenticating as {FROM_EMAIL}...")
        server.login(FROM_EMAIL, FROM_PASSWORD)
        print(f"✓ Authentication successful")

        # Create message
        msg = MIMEMultipart()
        msg['From'] = FROM_EMAIL
        msg['To'] = TO_EMAIL
        msg['Subject'] = SUBJECT
        msg.attach(MIMEText(BODY, 'plain'))

        # Send email
        print(f"Sending email to {TO_EMAIL}...")
        server.sendmail(FROM_EMAIL, [TO_EMAIL], msg.as_string())

        # Calculate duration
        duration = time.time() - start_time
        print(f"✓ Email sent successfully in {duration:.2f} seconds")

        # Quit
        server.quit()
        print(f"✓ Connection closed")

        return True

    except smtplib.SMTPException as e:
        print(f"✗ SMTP Error: {e}")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("XOAUTH2 Proxy - Single Email Test")
    print("=" * 60)
    print()

    success = send_test_email()

    print()
    print("=" * 60)
    if success:
        print("✓ TEST PASSED - Proxy is working correctly!")
        print()
        print("Next step: Run load_test.py to test high-volume performance")
        sys.exit(0)
    else:
        print("✗ TEST FAILED - Check proxy logs for errors")
        sys.exit(1)
