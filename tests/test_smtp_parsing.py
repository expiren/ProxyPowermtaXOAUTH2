#!/usr/bin/env python3
"""Test script to verify SMTP command parsing fixes"""

import re
import sys

def test_mail_from_regex():
    """Test MAIL FROM regex with various inputs"""
    # Updated regex pattern: FROM:<([^>]*)>
    pattern = r'FROM:<([^>]*)>'

    test_cases = [
        ("FROM:<user@example.com>", "user@example.com"),
        ("FROM:<> BODY=8BITMIME AUTH=<>", ""),  # Empty address with extended params
        ("FROM:<> BODY=8BITMIME", ""),  # Empty address with params
        ("MAIL FROM:<sender@test.org>", "sender@test.org"),
        ("MAIL FROM:<> SIZE=1024", ""),
        ("FROM:<noreply@company.com> AUTH=<test>", "noreply@company.com"),
    ]

    print("=" * 70)
    print("Testing MAIL FROM Regex Pattern")
    print("Pattern: " + pattern)
    print("=" * 70)

    all_passed = True
    for test_input, expected in test_cases:
        match = re.search(pattern, test_input, re.IGNORECASE)
        if match:
            result = match.group(1)
            status = "[PASS]" if result == expected else "[FAIL]"
            if result != expected:
                all_passed = False
            print(f"{status}: '{test_input}'")
            print(f"       Expected: '{expected}' | Got: '{result}'")
        else:
            status = "[FAIL]"
            all_passed = False
            print(f"{status}: '{test_input}'")
            print(f"       Expected: '{expected}' | Got: NO MATCH")
        print()

    return all_passed

def test_rcpt_to_regex():
    """Test RCPT TO regex with various inputs"""
    # Updated regex pattern: TO:<([^>]*)>
    pattern = r'TO:<([^>]*)>'

    test_cases = [
        ("TO:<user@example.com>", "user@example.com"),
        ("TO:<recipient@test.org>", "recipient@test.org"),
        ("TO:<user+tag@domain.com> NOTIFY=SUCCESS", "user+tag@domain.com"),
        ("RCPT TO:<> NOTIFY=FAILURE", ""),
        ("TO:<admin@company.net> ORCPT=rfc822", "admin@company.net"),
    ]

    print("=" * 70)
    print("Testing RCPT TO Regex Pattern")
    print("Pattern: " + pattern)
    print("=" * 70)

    all_passed = True
    for test_input, expected in test_cases:
        match = re.search(pattern, test_input, re.IGNORECASE)
        if match:
            result = match.group(1)
            status = "[PASS]" if result == expected else "[FAIL]"
            if result != expected:
                all_passed = False
            print(f"{status}: '{test_input}'")
            print(f"       Expected: '{expected}' | Got: '{result}'")
        else:
            status = "[FAIL]"
            all_passed = False
            print(f"{status}: '{test_input}'")
            print(f"       Expected: '{expected}' | Got: NO MATCH")
        print()

    return all_passed

def test_domain_extraction():
    """Test domain extraction logic for EHLO handling"""
    print("=" * 70)
    print("Testing Domain Extraction Logic (for EHLO)")
    print("=" * 70)

    test_cases = [
        ("user@example.com", "example.com"),
        ("bounce@test.org", "test.org"),
        ("", "localhost"),  # Empty mail_from (bounce message)
        ("noreply", "localhost"),  # No @ symbol
    ]

    all_passed = True
    for mail_from, expected in test_cases:
        # This simulates the logic in upstream.py
        if mail_from and '@' in mail_from:
            result = mail_from.split('@')[1]
        else:
            result = "localhost"

        status = "[PASS]" if result == expected else "[FAIL]"
        if result != expected:
            all_passed = False

        print(f"{status}: mail_from='{mail_from}'")
        print(f"       Expected: '{expected}' | Got: '{result}'")
        print()

    return all_passed

if __name__ == '__main__':
    print("\nSMTP Command Parsing Test Suite")
    print("Testing fixes for extended SMTP parameters handling\n")

    results = []
    results.append(("MAIL FROM Regex", test_mail_from_regex()))
    print()
    results.append(("RCPT TO Regex", test_rcpt_to_regex()))
    print()
    results.append(("Domain Extraction", test_domain_extraction()))

    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)

    all_passed = True
    for test_name, passed in results:
        status = "[PASSED]" if passed else "[FAILED]"
        print(f"{status}: {test_name}")
        if not passed:
            all_passed = False

    print("=" * 70)

    if all_passed:
        print("\n[OK] All tests passed!")
        sys.exit(0)
    else:
        print("\n[ERROR] Some tests failed!")
        sys.exit(1)
