#!/usr/bin/env python3
"""
Load testing script for XOAUTH2 Proxy
Tests performance with increasing message volumes up to 50k+ msg/min

Usage:
    # Test with 100 messages/min for 1 minute
    python load_test.py --rate 100 --duration 60

    # Test with 10k messages/min for 5 minutes
    python load_test.py --rate 10000 --duration 300

    # Test with 50k messages/min for 1 minute
    python load_test.py --rate 50000 --duration 60

    # Ramp test: start at 1k, increase to 50k over 10 minutes
    python load_test.py --ramp-start 1000 --ramp-end 50000 --duration 600
"""

import asyncio
import aiosmtplib
import argparse
import time
import sys
from collections import defaultdict
from datetime import datetime
import statistics


class LoadTester:
    def __init__(self, proxy_host, proxy_port, from_email, from_password, to_email):
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port
        self.from_email = from_email
        self.from_password = from_password
        self.to_email = to_email

        # Statistics
        self.sent_count = 0
        self.error_count = 0
        self.latencies = []
        self.errors_by_type = defaultdict(int)
        self.start_time = None
        self.lock = asyncio.Lock()

    async def send_email(self, message_id):
        """Send a single email asynchronously"""
        start = time.time()

        try:
            # Create SMTP client
            smtp = aiosmtplib.SMTP(
                hostname=self.proxy_host,
                port=self.proxy_port,
                timeout=10
            )

            # Connect
            await smtp.connect()

            # Login
            await smtp.login(self.from_email, self.from_password)

            # Send message
            message = f"""From: {self.from_email}
To: {self.to_email}
Subject: Load Test Message #{message_id}

This is load test message #{message_id} sent at {datetime.now().isoformat()}
"""

            await smtp.sendmail(self.from_email, [self.to_email], message)

            # Quit
            await smtp.quit()

            # Record success
            latency = time.time() - start
            async with self.lock:
                self.sent_count += 1
                self.latencies.append(latency)

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
        print(f"Starting load test: {target_rate} msg/min for {duration} seconds")
        print(f"Target: {target_rate / 60:.1f} msg/sec")
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

            # Print progress every 10 seconds
            elapsed = time.time() - self.start_time
            if int(elapsed) % 10 == 0 and elapsed > 0:
                self.print_progress()

        # Wait for remaining tasks
        print("\nWaiting for remaining sends to complete...")
        await asyncio.gather(*tasks, return_exceptions=True)

        # Final stats
        self.print_final_stats()

    async def run_ramp_test(self, start_rate, end_rate, duration):
        """Run load test with ramping rate"""
        print(f"Starting ramp test: {start_rate} → {end_rate} msg/min over {duration} seconds")
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
        print("\nWaiting for remaining sends to complete...")
        await asyncio.gather(*tasks, return_exceptions=True)

        # Final stats
        self.print_final_stats()

    def print_progress(self):
        """Print current progress"""
        elapsed = time.time() - self.start_time
        current_rate = (self.sent_count / elapsed) * 60 if elapsed > 0 else 0

        print(f"[{elapsed:.0f}s] Sent: {self.sent_count}, Errors: {self.error_count}, "
              f"Rate: {current_rate:.0f} msg/min", flush=True)

    def print_final_stats(self):
        """Print final statistics"""
        total_duration = time.time() - self.start_time

        print()
        print("=" * 70)
        print("LOAD TEST RESULTS")
        print("=" * 70)
        print()
        print(f"Duration:        {total_duration:.1f} seconds")
        print(f"Total Sent:      {self.sent_count}")
        print(f"Total Errors:    {self.error_count}")
        print(f"Success Rate:    {(self.sent_count / (self.sent_count + self.error_count) * 100):.1f}%")
        print()

        # Throughput
        actual_rate = (self.sent_count / total_duration) * 60
        print(f"Actual Rate:     {actual_rate:.0f} messages/minute")
        print(f"                 {actual_rate / 60:.1f} messages/second")
        print()

        # Latency stats
        if self.latencies:
            print("Latency Statistics:")
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
            print("Percentiles:")
            print(f"  P50:           {p50 * 1000:.1f} ms")
            print(f"  P95:           {p95 * 1000:.1f} ms")
            print(f"  P99:           {p99 * 1000:.1f} ms")
        print()

        # Error breakdown
        if self.errors_by_type:
            print("Errors by Type:")
            for error_type, count in sorted(self.errors_by_type.items(), key=lambda x: -x[1]):
                print(f"  {error_type}: {count}")
            print()

        # Performance assessment
        print("=" * 70)
        if actual_rate >= 50000:
            print("✓ EXCELLENT: Target of 50k+ msg/min ACHIEVED!")
        elif actual_rate >= 40000:
            print("✓ GOOD: Close to target (40k+ msg/min)")
        elif actual_rate >= 25000:
            print("⚠ MODERATE: 25k+ msg/min, but below 50k target")
        else:
            print("✗ BELOW TARGET: Less than 25k msg/min")
        print("=" * 70)
        print()


def main():
    parser = argparse.ArgumentParser(description="Load test XOAUTH2 Proxy")

    # Proxy settings
    parser.add_argument("--host", default="127.0.0.1", help="Proxy host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=2525, help="Proxy port (default: 2525)")

    # Account settings
    parser.add_argument("--from-email", default="tuyjlkb9076@hotmail.com",
                        help="From email address (default: tuyjlkb9076@hotmail.com)")
    parser.add_argument("--from-password", default="placeholder",
                        help="From password (default: placeholder)")
    parser.add_argument("--to-email", default="test@example.com",
                        help="To email address (default: test@example.com)")

    # Test mode
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--rate", type=int, help="Target rate (messages/minute)")
    mode_group.add_argument("--ramp-start", type=int, help="Ramp start rate (messages/minute)")

    # Duration
    parser.add_argument("--duration", type=int, default=60,
                        help="Test duration in seconds (default: 60)")

    # Ramp settings
    parser.add_argument("--ramp-end", type=int, help="Ramp end rate (messages/minute)")

    args = parser.parse_args()

    # Validate ramp mode
    if args.ramp_start and not args.ramp_end:
        parser.error("--ramp-end is required when using --ramp-start")

    # Create tester
    tester = LoadTester(
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
