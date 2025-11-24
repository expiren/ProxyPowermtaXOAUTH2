"""
SMTP Load Testing Tool - Benchmark proxy performance

This test tool sends multiple emails to the proxy on port 2525 and measures:
- Requests received per second
- Requests processed per second
- Total time to process all requests
- Success/failure rates
- Latency per request

Usage:
    python test_smtp_load.py --num-emails 1000 --concurrent 50 --host 127.0.0.1 --port 2525
"""

import asyncio
import time
import argparse
import logging
from typing import List, Tuple
from datetime import datetime
import aiosmtplib
import json
import sys

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger('smtp_load_test')


class SMTPLoadTester:
    """Load test the SMTP proxy with concurrent email sends"""

    def __init__(
        self,
        host: str = '127.0.0.1',
        port: int = 2525,
        num_emails: int = 100,
        concurrent: int = 10,
        from_email: str = 'test@example.com',
        to_email: str = 'recipient@outlook.com'
    ):
        self.host = host
        self.port = port
        self.num_emails = num_emails
        self.concurrent = concurrent
        self.from_email = from_email
        self.to_email = to_email

        # Statistics
        self.stats = {
            'total_requests': num_emails,
            'successful': 0,
            'failed': 0,
            'total_latency': 0.0,
            'min_latency': float('inf'),
            'max_latency': 0.0,
            'latencies': [],
            'start_time': None,
            'end_time': None,
            'errors': []
        }

    async def send_email(self, email_index: int) -> Tuple[bool, float, str]:
        """
        Send a single email through the proxy

        Returns:
            Tuple of (success: bool, latency: float, error_msg: str)
        """
        start_time = time.time()
        error_msg = ""

        try:
            # Connect to proxy
            async with aiosmtplib.SMTP(hostname=self.host, port=self.port) as smtp:
                # Use EHLO
                await smtp.ehlo()

                # Authenticate with test credentials
                # (password doesn't matter, proxy validates OAuth2 token)
                await smtp.login(
                    self.from_email,
                    'placeholder_password'
                )

                # Build email
                message = f"""\
From: {self.from_email}
To: {self.to_email}
Subject: Load Test Email #{email_index}
Date: {datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0000')}

This is a load test email #{email_index}.
Testing proxy performance and throughput.
Sent at: {datetime.now().isoformat()}
"""

                # Send email
                await smtp.sendmail(
                    self.from_email,
                    [self.to_email],
                    message
                )

                # QUIT
                await smtp.quit()

            latency = time.time() - start_time
            return True, latency, ""

        except asyncio.TimeoutError:
            latency = time.time() - start_time
            error_msg = "Connection timeout"
            return False, latency, error_msg
        except Exception as e:
            latency = time.time() - start_time
            error_msg = str(e)
            return False, latency, error_msg

    async def run_concurrent_sends(self, num_concurrent: int):
        """Run multiple concurrent email sends"""
        tasks = []

        for i in range(num_concurrent):
            task = self.send_email(i)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=False)
        return results

    async def run_load_test(self):
        """Execute the full load test"""
        logger.info("=" * 80)
        logger.info("SMTP Load Test Starting")
        logger.info("=" * 80)
        logger.info(f"Target: {self.host}:{self.port}")
        logger.info(f"Total emails: {self.num_emails}")
        logger.info(f"Concurrent connections: {self.concurrent}")
        logger.info(f"From: {self.from_email}")
        logger.info(f"To: {self.to_email}")
        logger.info("=" * 80)

        self.stats['start_time'] = datetime.now()
        test_start = time.time()

        # Calculate batches
        num_batches = (self.num_emails + self.concurrent - 1) // self.concurrent
        logger.info(f"Will send in {num_batches} batches of {self.concurrent}")

        # Send emails in batches
        for batch_num in range(num_batches):
            batch_start = time.time()
            batch_size = min(self.concurrent, self.num_emails - batch_num * self.concurrent)

            # Create batch tasks
            tasks = [
                self.send_email(batch_num * self.concurrent + i)
                for i in range(batch_size)
            ]

            # Wait for batch to complete
            results = await asyncio.gather(*tasks, return_exceptions=False)

            # Process results
            for success, latency, error_msg in results:
                self.stats['total_latency'] += latency
                self.stats['latencies'].append(latency)

                if success:
                    self.stats['successful'] += 1
                else:
                    self.stats['failed'] += 1
                    self.stats['errors'].append(error_msg)

                # Update min/max latency
                self.stats['min_latency'] = min(self.stats['min_latency'], latency)
                self.stats['max_latency'] = max(self.stats['max_latency'], latency)

            batch_time = time.time() - batch_start
            sent_so_far = batch_num * self.concurrent + batch_size
            requests_per_sec = batch_size / batch_time if batch_time > 0 else 0

            logger.info(
                f"[Batch {batch_num + 1}/{num_batches}] "
                f"Sent: {sent_so_far}/{self.num_emails} | "
                f"Success: {self.stats['successful']} | "
                f"Failed: {self.stats['failed']} | "
                f"Batch time: {batch_time:.2f}s | "
                f"Throughput: {requests_per_sec:.1f} req/s"
            )

        self.stats['end_time'] = datetime.now()
        total_time = time.time() - test_start

        # Print results
        self._print_results(total_time)

    def _print_results(self, total_time: float):
        """Print detailed test results"""
        logger.info("=" * 80)
        logger.info("LOAD TEST RESULTS")
        logger.info("=" * 80)

        # Basic stats
        logger.info(f"Total time: {total_time:.2f} seconds")
        logger.info(f"Total requests: {self.stats['total_requests']}")
        logger.info(f"Successful: {self.stats['successful']}")
        logger.info(f"Failed: {self.stats['failed']}")
        logger.info(f"Success rate: {self.stats['successful']/self.stats['total_requests']*100:.1f}%")

        # Throughput
        overall_throughput = self.stats['successful'] / total_time
        logger.info(f"\nThroughput:")
        logger.info(f"  Overall: {overall_throughput:.1f} requests/sec")
        logger.info(f"  Per minute: {overall_throughput * 60:.0f} requests/minute")

        # Latency stats
        if self.stats['latencies']:
            avg_latency = self.stats['total_latency'] / len(self.stats['latencies'])
            latencies_sorted = sorted(self.stats['latencies'])
            p50_latency = latencies_sorted[len(latencies_sorted) // 2]
            p95_latency = latencies_sorted[int(len(latencies_sorted) * 0.95)]
            p99_latency = latencies_sorted[int(len(latencies_sorted) * 0.99)]

            logger.info(f"\nLatency (seconds):")
            logger.info(f"  Min: {self.stats['min_latency']:.3f}s")
            logger.info(f"  Max: {self.stats['max_latency']:.3f}s")
            logger.info(f"  Average: {avg_latency:.3f}s")
            logger.info(f"  P50 (median): {p50_latency:.3f}s")
            logger.info(f"  P95: {p95_latency:.3f}s")
            logger.info(f"  P99: {p99_latency:.3f}s")

        # Error summary
        if self.stats['failed'] > 0:
            logger.warning(f"\nErrors ({self.stats['failed']}):")
            error_counts = {}
            for error in self.stats['errors']:
                error_counts[error] = error_counts.get(error, 0) + 1

            for error, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True):
                logger.warning(f"  {error}: {count}")

        # Save results to file
        results_file = f"load_test_results_{int(time.time())}.json"
        self._save_results(results_file)
        logger.info(f"\nResults saved to: {results_file}")
        logger.info("=" * 80)

    def _save_results(self, filename: str):
        """Save test results to JSON file"""
        results = {
            'timestamp': self.stats['start_time'].isoformat() if self.stats['start_time'] else None,
            'target': f"{self.host}:{self.port}",
            'config': {
                'num_emails': self.num_emails,
                'concurrent': self.concurrent,
                'from_email': self.from_email,
                'to_email': self.to_email
            },
            'results': {
                'total_requests': self.stats['total_requests'],
                'successful': self.stats['successful'],
                'failed': self.stats['failed'],
                'success_rate': self.stats['successful'] / self.stats['total_requests'],
                'total_time_seconds': sum(self.stats['latencies']),
                'throughput_rps': self.stats['successful'] / (sum(self.stats['latencies']) or 1),
                'throughput_rpm': (self.stats['successful'] / (sum(self.stats['latencies']) or 1)) * 60,
                'latency': {
                    'min_seconds': self.stats['min_latency'],
                    'max_seconds': self.stats['max_latency'],
                    'avg_seconds': self.stats['total_latency'] / len(self.stats['latencies']) if self.stats['latencies'] else 0,
                    'p50_seconds': sorted(self.stats['latencies'])[len(self.stats['latencies']) // 2] if self.stats['latencies'] else 0,
                    'p95_seconds': sorted(self.stats['latencies'])[int(len(self.stats['latencies']) * 0.95)] if self.stats['latencies'] else 0,
                    'p99_seconds': sorted(self.stats['latencies'])[int(len(self.stats['latencies']) * 0.99)] if self.stats['latencies'] else 0,
                }
            }
        }

        try:
            with open(filename, 'w') as f:
                json.dump(results, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save results: {e}")


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='SMTP Load Testing Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test with 100 emails, 10 concurrent connections
  python test_smtp_load.py --num-emails 100 --concurrent 10

  # Test with 1000 emails, 50 concurrent connections to remote server
  python test_smtp_load.py --num-emails 1000 --concurrent 50 --host 192.168.1.100

  # Test with custom from/to emails
  python test_smtp_load.py --num-emails 500 --from sales@gmail.com --to test@outlook.com
        """
    )

    parser.add_argument(
        '--num-emails',
        type=int,
        default=100,
        help='Number of emails to send (default: 100)'
    )
    parser.add_argument(
        '--concurrent',
        type=int,
        default=10,
        help='Concurrent connections (default: 10)'
    )
    parser.add_argument(
        '--host',
        type=str,
        default='127.0.0.1',
        help='Proxy host (default: 127.0.0.1)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=2525,
        help='Proxy port (default: 2525)'
    )
    parser.add_argument(
        '--from',
        dest='from_email',
        type=str,
        default='test@example.com',
        help='From email address (default: test@example.com)'
    )
    parser.add_argument(
        '--to',
        dest='to_email',
        type=str,
        default='recipient@outlook.com',
        help='To email address (default: recipient@outlook.com)'
    )

    args = parser.parse_args()

    # Create and run tester
    tester = SMTPLoadTester(
        host=args.host,
        port=args.port,
        num_emails=args.num_emails,
        concurrent=args.concurrent,
        from_email=args.from_email,
        to_email=args.to_email
    )

    try:
        await tester.run_load_test()
    except KeyboardInterrupt:
        logger.info("\nLoad test interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Load test failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
