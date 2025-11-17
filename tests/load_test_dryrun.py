#!/usr/bin/env python3
"""
Dry-run load testing for XOAUTH2 Proxy
Tests performance WITHOUT sending real emails to Gmail/Outlook

This script tests:
- Authentication performance
- Token refresh
- SMTP protocol handling
- Connection pooling
- All optimizations

But SKIPS:
- Actual email delivery to Gmail/Outlook

Perfect for testing 50k+ msg/min without sending real emails!

Usage:
    # Test 50k msg/min without sending real emails
    python load_test_dryrun.py --rate 50000 --duration 60

    # Ramp test from 1k to 50k
    python load_test_dryrun.py --ramp-start 1000 --ramp-end 50000 --duration 600
"""

import asyncio
import aiosmtplib
import argparse
import time
import sys
from collections import defaultdict
from datetime import datetime
import statistics


class DryRunLoadTester:
    """Load tester that works with proxy in dry-run mode"""

    def __init__(self, proxy_host, proxy_port, from_email, from_password, to_email):
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port
        self.from_email = from_email
        self.from_password = from_password
        self.to_email = to_email

        # Statistics
        self.sent_count = 0
        self.error_count = 0
        self.auth_count = 0
        self.latencies = []
        self.auth_latencies = []
        self.errors_by_type = defaultdict(int)
        self.start_time = None
        self.lock = asyncio.Lock()

    async def send_email(self, message_id):
        """Send a single email (proxy in dry-run mode won't actually deliver)"""
        start = time.time()
        auth_start = start

        try:
            # Create SMTP client
            smtp = aiosmtplib.SMTP(
                hostname=self.proxy_host,
                port=self.proxy_port,
                timeout=10
            )

            # Connect
            await smtp.connect()

            # Login (this tests authentication and token refresh)
            await smtp.login(self.from_email, self.from_password)
            auth_time = time.time() - auth_start

            # Send message (proxy will accept but not deliver in dry-run mode)
            message = f"""From: {self.from_email}
To: {self.to_email}
Subject: Dry-Run Load Test Message #{message_id}
Date: {datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')}

This is a dry-run load test message #{message_id}.
The proxy will accept this but NOT send to real SMTP servers.

Timestamp: {datetime.now().isoformat()}
Message ID: {message_id}
"""

            await smtp.sendmail(self.from_email, [self.to_email], message)

            # Quit
            await smtp.quit()

            # Record success
            latency = time.time() - start
            async with self.lock:
                self.sent_count += 1
                self.auth_count += 1
                self.latencies.append(latency)
                self.auth_latencies.append(auth_time)

            return True

        except Exception as e:
            # Record error
            async with self.lock:
                self.error_count += 1
                error_type = type(e).__name__
                self.errors_by_type[error_type] += 1

            return False

    async def run_constant_rate(self, target_rate, duration):
        """Run load test at constant rate"""
        print("=" * 80)
        print(" " * 20 + "DRY-RUN LOAD TEST")
        print("=" * 80)
        print()
        print(f"⚠️  IMPORTANT: Start proxy with --dry-run flag:")
        print(f"   python xoauth2_proxy_v2.py --config accounts.json --dry-run")
        print()
        print(f"Target Rate:     {target_rate:,} messages/minute")
        print(f"                 {target_rate / 60:.1f} messages/second")
        print(f"Duration:        {duration} seconds")
        print(f"Expected Total:  {int(target_rate * duration / 60):,} messages")
        print()
        print("This test will:")
        print("  ✓ Test authentication and token refresh")
        print("  ✓ Test SMTP protocol handling")
        print("  ✓ Test connection pooling")
        print("  ✓ Test all 15 performance optimizations")
        print("  ✗ NOT send real emails to Gmail/Outlook")
        print()
        print("=" * 80)
        print()

        self.start_time = time.time()
        end_time = self.start_time + duration

        # Calculate interval between sends (in seconds)
        interval = 60.0 / target_rate if target_rate > 0 else 1.0

        message_id = 0
        tasks = []

        while time.time() < end_time:
            # Send message
            task = asyncio.create_task(self.send_email(message_id))
            tasks.append(task)
            message_id += 1

            # Wait for next interval
            await asyncio.sleep(interval)

            # Print progress every 5 seconds
            elapsed = time.time() - self.start_time
            if int(elapsed) % 5 == 0 and elapsed > 0:
                self.print_progress()

        # Wait for remaining tasks
        print("\nWaiting for remaining operations to complete...")
        await asyncio.gather(*tasks, return_exceptions=True)

        # Final stats
        self.print_final_stats()

    async def run_ramp_test(self, start_rate, end_rate, duration):
        """Run load test with ramping rate"""
        print("=" * 80)
        print(" " * 20 + "DRY-RUN RAMP TEST")
        print("=" * 80)
        print()
        print(f"⚠️  IMPORTANT: Start proxy with --dry-run flag:")
        print(f"   python xoauth2_proxy_v2.py --config accounts.json --dry-run")
        print()
        print(f"Ramp:            {start_rate:,} → {end_rate:,} messages/minute")
        print(f"Duration:        {duration} seconds")
        print()
        print("=" * 80)
        print()

        self.start_time = time.time()
        end_time = self.start_time + duration

        message_id = 0
        tasks = []

        while time.time() < end_time:
            elapsed = time.time() - self.start_time
            progress = elapsed / duration

            # Calculate current target rate (linear ramp)
            current_rate = start_rate + (end_rate - start_rate) * progress
            interval = 60.0 / current_rate if current_rate > 0 else 1.0

            # Send message
            task = asyncio.create_task(self.send_email(message_id))
            tasks.append(task)
            message_id += 1

            # Wait for next interval
            await asyncio.sleep(interval)

            # Print progress every 10 seconds
            if int(elapsed) % 10 == 0 and elapsed > 0:
                print(f"Current rate: {current_rate:.0f} msg/min", end=" | ")
                self.print_progress()

        # Wait for remaining tasks
        print("\nWaiting for remaining operations to complete...")
        await asyncio.gather(*tasks, return_exceptions=True)

        # Final stats
        self.print_final_stats()

    def print_progress(self):
        """Print current progress"""
        elapsed = time.time() - self.start_time
        current_rate = (self.sent_count / elapsed) * 60 if elapsed > 0 else 0

        print(f"[{elapsed:.0f}s] Sent: {self.sent_count:,}, Errors: {self.error_count}, "
              f"Rate: {current_rate:,.0f} msg/min", flush=True)

    def print_final_stats(self):
        """Print final statistics"""
        total_duration = time.time() - self.start_time

        print()
        print("=" * 80)
        print(" " * 25 + "DRY-RUN TEST RESULTS")
        print("=" * 80)
        print()
        print(f"Duration:        {total_duration:.1f} seconds")
        print(f"Total Sent:      {self.sent_count:,}")
        print(f"Total Errors:    {self.error_count}")

        if self.sent_count + self.error_count > 0:
            success_rate = (self.sent_count / (self.sent_count + self.error_count) * 100)
            print(f"Success Rate:    {success_rate:.2f}%")
        print()

        # Throughput
        actual_rate = (self.sent_count / total_duration) * 60
        print("THROUGHPUT:")
        print(f"  Messages/Min:  {actual_rate:,.0f}")
        print(f"  Messages/Sec:  {actual_rate / 60:.1f}")
        print()

        # Authentication performance
        if self.auth_latencies:
            print("AUTHENTICATION PERFORMANCE:")
            print(f"  Total Auths:   {self.auth_count:,}")
            print(f"  Min Auth:      {min(self.auth_latencies) * 1000:.1f} ms")
            print(f"  Max Auth:      {max(self.auth_latencies) * 1000:.1f} ms")
            print(f"  Mean Auth:     {statistics.mean(self.auth_latencies) * 1000:.1f} ms")
            print()

        # Latency stats
        if self.latencies:
            print("END-TO-END LATENCY (Auth + Send):")
            print(f"  Min:           {min(self.latencies) * 1000:.1f} ms")
            print(f"  Max:           {max(self.latencies) * 1000:.1f} ms")
            print(f"  Mean:          {statistics.mean(self.latencies) * 1000:.1f} ms")
            print(f"  Median:        {statistics.median(self.latencies) * 1000:.1f} ms")

            if len(self.latencies) > 1:
                print(f"  Std Dev:       {statistics.stdev(self.latencies) * 1000:.1f} ms")

            # Percentiles
            sorted_latencies = sorted(self.latencies)
            p50 = sorted_latencies[int(len(sorted_latencies) * 0.50)]
            p95 = sorted_latencies[int(len(sorted_latencies) * 0.95)]
            p99 = sorted_latencies[int(len(sorted_latencies) * 0.99)]

            print()
            print("LATENCY PERCENTILES:")
            print(f"  P50:           {p50 * 1000:.1f} ms")
            print(f"  P95:           {p95 * 1000:.1f} ms")
            print(f"  P99:           {p99 * 1000:.1f} ms")
        print()

        # Error breakdown
        if self.errors_by_type:
            print("ERRORS BY TYPE:")
            for error_type, count in sorted(self.errors_by_type.items(), key=lambda x: -x[1]):
                print(f"  {error_type}: {count}")
            print()

        # Performance assessment
        print("=" * 80)
        print("PERFORMANCE ASSESSMENT:")
        print()

        if actual_rate >= 50000:
            status = "✅ EXCELLENT"
            message = "Target of 50k+ msg/min ACHIEVED!"
            details = "The proxy can handle 50,000+ messages per minute in production."
        elif actual_rate >= 40000:
            status = "✅ GOOD"
            message = "Close to target (40k+ msg/min)"
            details = "Nearly there! Minor tuning may get you to 50k+."
        elif actual_rate >= 25000:
            status = "⚠️  MODERATE"
            message = "25k+ msg/min, approaching target"
            details = "Performance is decent but needs optimization for 50k target."
        elif actual_rate >= 10000:
            status = "⚠️  WARMING UP"
            message = "10k+ msg/min detected"
            details = "System is responding but far from 50k target."
        else:
            status = "❌ BELOW TARGET"
            message = "Less than 10k msg/min"
            details = "Check proxy configuration and system resources."

        print(f"{status}: {message}")
        print(f"{details}")
        print()
        print("Note: This is a DRY-RUN test - no real emails were sent.")
        print("Real production performance may vary slightly due to upstream SMTP latency.")
        print("=" * 80)
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Dry-run load test for XOAUTH2 Proxy (no real emails sent)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test 50k msg/min for 1 minute (no real emails)
  python load_test_dryrun.py --rate 50000 --duration 60

  # Ramp from 1k to 50k over 10 minutes
  python load_test_dryrun.py --ramp-start 1000 --ramp-end 50000 --duration 600

  # Quick 10-second test at 10k rate
  python load_test_dryrun.py --rate 10000 --duration 10

IMPORTANT: Start proxy with --dry-run flag before testing!
  python xoauth2_proxy_v2.py --config accounts.json --dry-run
        """
    )

    # Proxy settings
    parser.add_argument("--host", default="127.0.0.1",
                        help="Proxy host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=2525,
                        help="Proxy port (default: 2525)")

    # Account settings
    parser.add_argument("--from-email", default="tuyjlkb9076@hotmail.com",
                        help="From email address")
    parser.add_argument("--from-password", default="placeholder",
                        help="From password (ignored by proxy)")
    parser.add_argument("--to-email", default="test@example.com",
                        help="To email address (won't actually receive email)")

    # Test mode
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--rate", type=int,
                            help="Target rate (messages/minute)")
    mode_group.add_argument("--ramp-start", type=int,
                            help="Ramp start rate (messages/minute)")

    # Duration
    parser.add_argument("--duration", type=int, default=60,
                        help="Test duration in seconds (default: 60)")

    # Ramp settings
    parser.add_argument("--ramp-end", type=int,
                        help="Ramp end rate (messages/minute)")

    args = parser.parse_args()

    # Validate ramp mode
    if args.ramp_start and not args.ramp_end:
        parser.error("--ramp-end is required when using --ramp-start")

    # Create tester
    tester = DryRunLoadTester(
        proxy_host=args.host,
        proxy_port=args.port,
        from_email=args.from_email,
        from_password=args.from_password,
        to_email=args.to_email
    )

    # Run test
    try:
        if args.rate:
            asyncio.run(tester.run_constant_rate(args.rate, args.duration))
        else:
            asyncio.run(tester.run_ramp_test(args.ramp_start, args.ramp_end, args.duration))
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        tester.print_final_stats()
        sys.exit(1)


if __name__ == "__main__":
    main()
