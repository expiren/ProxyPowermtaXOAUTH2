"""
Direct Provider Throughput Testing

This tool tests the proxy by connecting DIRECTLY to OAuth2 provider endpoints
(Gmail/Outlook SMTP servers) and attempting real authentication and message sending.

It bypasses the proxy and goes straight to the provider to measure:
- Real OAuth2 token refresh performance
- Real SMTP protocol latency to providers
- Real-world throughput and failure rates
- Provider-specific performance characteristics

This is the "real world" test - it shows actual performance with real credentials.

Usage:
    # Test with real OAuth2 credentials
    python test_provider_throughput.py --from your-real-email@gmail.com

    # High throughput test (5000 messages)
    python test_provider_throughput.py --num-emails 5000 --concurrent 100

    # Stress test with detailed error tracking
    python test_provider_throughput.py --num-emails 10000 --concurrent 200 --verbose

    # Test specific provider
    python test_provider_throughput.py --provider gmail --num-emails 1000
"""

import asyncio
import time
import argparse
import logging
import json
import signal
import sys
from typing import Tuple, Optional, Dict
from datetime import datetime
import aiosmtplib
import aiohttp

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger('provider_throughput')


class ProviderThroughputTester:
    """Test real provider endpoints with concurrent message sending"""

    def __init__(
        self,
        email: str,
        password: str,
        num_emails: int = 100,
        concurrent: int = 10,
        provider: Optional[str] = None,
        verbose: bool = False
    ):
        """
        Initialize provider throughput tester

        Args:
            email: Email address (determines provider)
            password: Email password or OAuth2 access token
            num_emails: Number of emails to send
            concurrent: Concurrent connections
            provider: Force provider (gmail/outlook)
            verbose: Verbose logging
        """
        self.email = email
        self.password = password
        self.num_emails = num_emails
        self.concurrent = concurrent
        self.verbose = verbose

        # Determine provider
        if provider:
            self.provider = provider.lower()
        elif '@gmail.com' in email.lower():
            self.provider = 'gmail'
        elif '@outlook.com' in email.lower() or '@hotmail.com' in email.lower():
            self.provider = 'outlook'
        else:
            self.provider = 'gmail'  # Default

        # Provider endpoints
        self.endpoints = {
            'gmail': {
                'host': 'smtp.gmail.com',
                'port': 587,
                'oauth_token_url': 'https://oauth2.googleapis.com/token'
            },
            'outlook': {
                'host': 'smtp.office365.com',
                'port': 587,
                'oauth_token_url': 'https://login.microsoftonline.com/common/oauth2/v2.0/token'
            }
        }

        # Statistics
        self.stats = {
            'total_requests': num_emails,
            'successful': 0,
            'failed': 0,
            'auth_failed': 0,
            'send_failed': 0,
            'connection_failed': 0,
            'total_latency': 0.0,
            'min_latency': float('inf'),
            'max_latency': 0.0,
            'latencies': [],
            'start_time': None,
            'end_time': None,
            'errors': {}  # Error type -> count
        }

    async def send_email(self, email_index: int) -> Tuple[bool, float, str]:
        """
        Send single email directly to provider endpoint

        Returns:
            Tuple of (success: bool, latency: float, error_msg: str)
        """
        start_time = time.time()
        error_msg = ""

        try:
            endpoint = self.endpoints[self.provider]

            # Connect to provider
            async with aiosmtplib.SMTP(
                hostname=endpoint['host'],
                port=endpoint['port'],
                timeout=10
            ) as smtp:
                # Use EHLO
                await smtp.ehlo()

                # Start TLS (required by Gmail/Outlook)
                await smtp.starttls()
                await smtp.ehlo()

                # Authenticate
                # For real testing, this would be your actual OAuth2 access token
                # Since we're testing with placeholders, this will fail with auth error
                try:
                    await smtp.login(self.email, self.password)
                except asyncio.TimeoutError:
                    error_msg = f"AUTH timeout to {endpoint['host']}"
                    self.stats['auth_failed'] += 1
                    latency = time.time() - start_time
                    return False, latency, error_msg
                except Exception as e:
                    error_msg = f"AUTH failed: {str(e)[:100]}"
                    self.stats['auth_failed'] += 1
                    latency = time.time() - start_time
                    return False, latency, error_msg

                # Build email
                message = f"""\
From: {self.email}
To: test@example.com
Subject: Throughput Test Email #{email_index}
Date: {datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0000')}

This is a direct provider throughput test email #{email_index}.
Sent directly to {endpoint['host']} at {datetime.now().isoformat()}
"""

                # Send email
                try:
                    await smtp.sendmail(
                        self.email,
                        ['test@example.com'],
                        message
                    )
                except Exception as e:
                    error_msg = f"SEND failed: {str(e)[:100]}"
                    self.stats['send_failed'] += 1
                    latency = time.time() - start_time
                    return False, latency, error_msg

                # QUIT
                await smtp.quit()

            latency = time.time() - start_time
            return True, latency, ""

        except asyncio.TimeoutError:
            latency = time.time() - start_time
            error_msg = "Connection timeout"
            self.stats['connection_failed'] += 1
            return False, latency, error_msg
        except Exception as e:
            latency = time.time() - start_time
            error_msg = str(e)[:100]
            self.stats['connection_failed'] += 1
            return False, latency, error_msg

    async def run_load_test(self):
        """Execute the full throughput test"""
        logger.info("=" * 80)
        logger.info("DIRECT PROVIDER THROUGHPUT TEST")
        logger.info("=" * 80)
        logger.info(f"Provider: {self.provider.upper()}")
        logger.info(f"Email: {self.email}")
        logger.info(f"Endpoint: {self.endpoints[self.provider]['host']}:{self.endpoints[self.provider]['port']}")
        logger.info(f"Total emails: {self.num_emails}")
        logger.info(f"Concurrent connections: {self.concurrent}")
        logger.info("=" * 80)
        logger.info("Press Ctrl+C to cancel at any time")
        logger.info("=" * 80)

        self.stats['start_time'] = datetime.now()
        test_start = time.time()

        # Calculate batches
        num_batches = (self.num_emails + self.concurrent - 1) // self.concurrent
        logger.info(f"Will send in {num_batches} batches of {self.concurrent}")

        # Send emails in batches
        try:
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
                        # Track error types
                        error_type = error_msg.split(':')[0] if error_msg else 'Unknown'
                        self.stats['errors'][error_type] = self.stats['errors'].get(error_type, 0) + 1

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

        except KeyboardInterrupt:
            logger.info("\n\nTest interrupted by user (Ctrl+C)")
            logger.info(f"Stopped after {self.stats['successful']} successful sends")
        finally:
            self.stats['end_time'] = datetime.now()
            total_time = time.time() - test_start

            # Print results
            self._print_results(total_time)

    def _print_results(self, total_time: float):
        """Print detailed test results"""
        logger.info("=" * 80)
        logger.info("DIRECT PROVIDER TEST RESULTS")
        logger.info("=" * 80)

        # Basic stats
        logger.info(f"Total time: {total_time:.2f} seconds")
        logger.info(f"Total requests: {self.stats['total_requests']}")
        logger.info(f"Successful: {self.stats['successful']}")
        logger.info(f"Failed: {self.stats['failed']}")
        if self.stats['total_requests'] > 0:
            logger.info(f"Success rate: {self.stats['successful']/self.stats['total_requests']*100:.1f}%")

        # Throughput
        if total_time > 0:
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

        # Failure breakdown
        if self.stats['failed'] > 0:
            logger.warning(f"\nFailure Analysis ({self.stats['failed']} total):")
            logger.warning(f"  Authentication failures: {self.stats['auth_failed']}")
            logger.warning(f"  Send failures: {self.stats['send_failed']}")
            logger.warning(f"  Connection failures: {self.stats['connection_failed']}")

            if self.stats['errors']:
                logger.warning(f"\nError Types:")
                for error_type, count in sorted(self.stats['errors'].items(), key=lambda x: x[1], reverse=True):
                    logger.warning(f"  {error_type}: {count}")

        # Save results
        results_file = f"provider_test_results_{int(time.time())}.json"
        self._save_results(results_file)
        logger.info(f"\nResults saved to: {results_file}")
        logger.info("=" * 80)

    def _save_results(self, filename: str):
        """Save test results to JSON file"""
        results = {
            'test_type': 'direct_provider',
            'timestamp': self.stats['start_time'].isoformat() if self.stats['start_time'] else None,
            'provider': self.provider,
            'email': self.email,
            'endpoint': f"{self.endpoints[self.provider]['host']}:{self.endpoints[self.provider]['port']}",
            'config': {
                'num_emails': self.num_emails,
                'concurrent': self.concurrent,
            },
            'results': {
                'total_requests': self.stats['total_requests'],
                'successful': self.stats['successful'],
                'failed': self.stats['failed'],
                'auth_failed': self.stats['auth_failed'],
                'send_failed': self.stats['send_failed'],
                'connection_failed': self.stats['connection_failed'],
                'success_rate': self.stats['successful'] / self.stats['total_requests'] if self.stats['total_requests'] > 0 else 0,
                'total_time_seconds': sum(self.stats['latencies']) if self.stats['latencies'] else 0,
                'throughput_rps': self.stats['successful'] / sum(self.stats['latencies']) if sum(self.stats['latencies']) > 0 else 0,
                'latency': {
                    'min_seconds': self.stats['min_latency'] if self.stats['latencies'] else 0,
                    'max_seconds': self.stats['max_latency'] if self.stats['latencies'] else 0,
                    'avg_seconds': self.stats['total_latency'] / len(self.stats['latencies']) if self.stats['latencies'] else 0,
                    'p50_seconds': sorted(self.stats['latencies'])[len(self.stats['latencies']) // 2] if self.stats['latencies'] else 0,
                    'p95_seconds': sorted(self.stats['latencies'])[int(len(self.stats['latencies']) * 0.95)] if self.stats['latencies'] else 0,
                    'p99_seconds': sorted(self.stats['latencies'])[int(len(self.stats['latencies']) * 0.99)] if self.stats['latencies'] else 0,
                },
                'errors': self.stats['errors']
            }
        }

        try:
            with open(filename, 'w') as f:
                json.dump(results, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save results: {e}")


def handle_signal(signum, frame):
    """Handle Ctrl+C gracefully"""
    logger.info("\n\nShutting down gracefully... (Ctrl+C again to force quit)")
    sys.exit(0)


async def main():
    """Main entry point"""
    # Register signal handler for Ctrl+C
    signal.signal(signal.SIGINT, handle_signal)

    parser = argparse.ArgumentParser(
        description='Direct Provider Throughput Test',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test with real credentials (you must provide these)
  python test_provider_throughput.py --from your-email@gmail.com --password YOUR_ACCESS_TOKEN

  # High throughput test (5000 messages, 100 concurrent)
  python test_provider_throughput.py --num-emails 5000 --concurrent 100 --from email@gmail.com --password token

  # Stress test (10000 messages, 200 concurrent)
  python test_provider_throughput.py --num-emails 10000 --concurrent 200 --verbose --from email@gmail.com --password token

  # Specific provider (force Gmail even if Outlook email)
  python test_provider_throughput.py --provider gmail --from email@example.com --password token
        """
    )

    parser.add_argument(
        '--from',
        dest='from_email',
        type=str,
        required=True,
        help='Email address (determines provider unless --provider specified)'
    )
    parser.add_argument(
        '--password',
        type=str,
        required=True,
        help='Email password or OAuth2 access token for authentication'
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
        '--provider',
        type=str,
        choices=['gmail', 'outlook'],
        help='Force provider (auto-detect from email if not specified)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Verbose logging'
    )

    args = parser.parse_args()

    # Create and run tester
    tester = ProviderThroughputTester(
        email=args.from_email,
        password=args.password,
        num_emails=args.num_emails,
        concurrent=args.concurrent,
        provider=args.provider,
        verbose=args.verbose
    )

    try:
        await tester.run_load_test()
    except KeyboardInterrupt:
        logger.info("\nTest interrupted")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
