"""
Ultra-High Throughput Testing (5000+ msg/sec)

This tool tests the proxy with ultra-high message throughput:
- Sends 5000-50000+ messages per second
- Tests connection pool limits
- Measures peak performance
- Handles failures gracefully
- Tracks latency under extreme load

This is the "stress test" version - pushes the proxy to its limits.

Usage:
    # 5000 messages per second (100 concurrent, 50 messages each)
    python test_ultra_high_throughput.py --num-emails 5000 --concurrent 100

    # 10000 messages per second (200 concurrent)
    python test_ultra_high_throughput.py --num-emails 10000 --concurrent 200

    # 50000 messages per second (500 concurrent, extreme stress)
    python test_ultra_high_throughput.py --num-emails 50000 --concurrent 500 --verbose

    # Real provider test at 5000 msg/sec
    python test_ultra_high_throughput.py --num-emails 5000 --concurrent 100 --use-real-provider --from email@gmail.com --password token
"""

import asyncio
import time
import argparse
import logging
import json
import signal
import sys
from typing import Tuple, Dict, List
from datetime import datetime
import aiosmtplib

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger('ultra_throughput')


class UltraHighThroughputTester:
    """Test ultra-high throughput (5000+ msg/sec)"""

    def __init__(
        self,
        host: str = '127.0.0.1',
        port: int = 2525,
        num_emails: int = 5000,
        concurrent: int = 100,
        from_email: str = 'test.account1@gmail.com',
        to_email: str = 'recipient@outlook.com',
        use_real_provider: bool = False,
        provider_host: str = 'smtp.gmail.com',
        provider_port: int = 587,
        provider_password: str = 'placeholder',
        verbose: bool = False
    ):
        """
        Initialize ultra-high throughput tester

        Args:
            host: Proxy host (or provider host if using real)
            port: Proxy port (or provider port if using real)
            num_emails: Total messages to send
            concurrent: Concurrent connections (higher = more throughput)
            from_email: From email address
            to_email: To email address
            use_real_provider: Connect to real provider endpoint
            provider_host: Real provider host (if use_real_provider=True)
            provider_port: Real provider port
            provider_password: Real provider password/token
            verbose: Verbose logging
        """
        self.host = host
        self.port = port
        self.num_emails = num_emails
        self.concurrent = concurrent
        self.from_email = from_email
        self.to_email = to_email
        self.use_real_provider = use_real_provider
        self.provider_host = provider_host
        self.provider_port = provider_port
        self.provider_password = provider_password
        self.verbose = verbose

        # Target: X requests per second
        self.target_rps = concurrent  # Will update based on results

        # Statistics
        self.stats = {
            'total_requests': num_emails,
            'successful': 0,
            'failed': 0,
            'total_latency': 0.0,
            'min_latency': float('inf'),
            'max_latency': 0.0,
            'latencies': [],
            'batch_throughputs': [],
            'start_time': None,
            'end_time': None,
            'errors': {}
        }

    async def send_email_fast(self, email_index: int) -> Tuple[bool, float]:
        """
        Send email as fast as possible with minimal overhead

        Returns:
            Tuple of (success: bool, latency: float)
        """
        start_time = time.time()

        try:
            # Connect to proxy or provider
            if self.use_real_provider:
                host = self.provider_host
                port = self.provider_port
                password = self.provider_password
            else:
                host = self.host
                port = self.port
                password = 'placeholder'

            async with aiosmtplib.SMTP(hostname=host, port=port, timeout=10) as smtp:
                await smtp.ehlo()

                # For real provider, need TLS and real auth
                if self.use_real_provider:
                    await smtp.starttls()
                    await smtp.ehlo()
                    try:
                        await smtp.login(self.from_email, password)
                    except Exception:
                        latency = time.time() - start_time
                        return False, latency

                # Minimal email (fastest possible)
                message = f"From: {self.from_email}\r\nTo: {self.to_email}\r\nSubject: T#{email_index}\r\n\r\nTest"

                await smtp.sendmail(self.from_email, [self.to_email], message)
                await smtp.quit()

            latency = time.time() - start_time
            return True, latency

        except Exception:
            latency = time.time() - start_time
            return False, latency

    async def run_ultra_high_throughput_test(self):
        """Execute ultra-high throughput test"""
        logger.info("=" * 80)
        logger.info("ULTRA-HIGH THROUGHPUT TEST (5000+ msg/sec)")
        logger.info("=" * 80)

        if self.use_real_provider:
            logger.info(f"Target: {self.provider_host}:{self.provider_port} (REAL PROVIDER)")
        else:
            logger.info(f"Target: {self.host}:{self.port} (Proxy)")

        logger.info(f"Total emails: {self.num_emails}")
        logger.info(f"Concurrent connections: {self.concurrent}")
        logger.info(f"From: {self.from_email}")
        logger.info(f"To: {self.to_email}")
        logger.info("=" * 80)
        logger.info("Press Ctrl+C to cancel")
        logger.info("=" * 80)

        self.stats['start_time'] = datetime.now()
        test_start = time.time()

        # Send all emails as fast as possible
        # Use chunks to avoid memory overload
        chunk_size = min(self.concurrent * 2, 1000)  # Process in chunks
        num_chunks = (self.num_emails + chunk_size - 1) // chunk_size

        try:
            for chunk_num in range(num_chunks):
                chunk_start = time.time()
                chunk_start_index = chunk_num * chunk_size
                chunk_actual_size = min(chunk_size, self.num_emails - chunk_start_index)

                # Create tasks for this chunk
                tasks = [
                    self.send_email_fast(chunk_start_index + i)
                    for i in range(chunk_actual_size)
                ]

                # Execute tasks with limited concurrency
                # Split into smaller batches to control concurrency
                batch_size = self.concurrent
                for batch_start in range(0, len(tasks), batch_size):
                    batch_end = min(batch_start + batch_size, len(tasks))
                    batch_tasks = tasks[batch_start:batch_end]

                    results = await asyncio.gather(*batch_tasks, return_exceptions=False)

                    # Process results
                    for success, latency in results:
                        self.stats['total_latency'] += latency
                        self.stats['latencies'].append(latency)

                        if success:
                            self.stats['successful'] += 1
                        else:
                            self.stats['failed'] += 1

                        # Update min/max
                        self.stats['min_latency'] = min(self.stats['min_latency'], latency)
                        self.stats['max_latency'] = max(self.stats['max_latency'], latency)

                # Chunk stats
                chunk_time = time.time() - chunk_start
                chunk_throughput = chunk_actual_size / chunk_time if chunk_time > 0 else 0
                self.stats['batch_throughputs'].append(chunk_throughput)

                sent_so_far = chunk_start_index + chunk_actual_size
                logger.info(
                    f"[Chunk {chunk_num + 1}/{num_chunks}] "
                    f"Sent: {sent_so_far}/{self.num_emails} | "
                    f"Success: {self.stats['successful']} | "
                    f"Failed: {self.stats['failed']} | "
                    f"Throughput: {chunk_throughput:.0f} msg/sec"
                )

        except KeyboardInterrupt:
            logger.info("\n\nTest interrupted by user (Ctrl+C)")
            logger.info(f"Stopped after {self.stats['successful']} successful sends")
        finally:
            self.stats['end_time'] = datetime.now()
            total_time = time.time() - test_start
            self._print_results(total_time)

    def _print_results(self, total_time: float):
        """Print ultra-detailed results"""
        logger.info("=" * 80)
        logger.info("ULTRA-HIGH THROUGHPUT TEST RESULTS")
        logger.info("=" * 80)

        # Basic stats
        logger.info(f"Total time: {total_time:.2f} seconds")
        logger.info(f"Total requests: {self.stats['total_requests']}")
        logger.info(f"Successful: {self.stats['successful']}")
        logger.info(f"Failed: {self.stats['failed']}")
        if self.stats['total_requests'] > 0:
            logger.info(f"Success rate: {self.stats['successful']/self.stats['total_requests']*100:.1f}%")

        # THROUGHPUT (most important for 5000 msg/sec test)
        if total_time > 0:
            overall_throughput = self.stats['successful'] / total_time
            logger.info(f"\nTHROUGHPUT (MAIN METRIC):")
            logger.info(f"  Overall: {overall_throughput:.1f} requests/sec")
            logger.info(f"  Per minute: {overall_throughput * 60:.0f} requests/minute")
            logger.info(f"  Per hour: {overall_throughput * 3600:.0f} requests/hour")

            # Peak throughput from batches
            if self.stats['batch_throughputs']:
                peak_throughput = max(self.stats['batch_throughputs'])
                avg_batch_throughput = sum(self.stats['batch_throughputs']) / len(self.stats['batch_throughputs'])
                logger.info(f"\nBatch Throughput:")
                logger.info(f"  Peak: {peak_throughput:.1f} msg/sec")
                logger.info(f"  Average: {avg_batch_throughput:.1f} msg/sec")

        # Latency under load
        if self.stats['latencies']:
            avg_latency = self.stats['total_latency'] / len(self.stats['latencies'])
            latencies_sorted = sorted(self.stats['latencies'])
            p50 = latencies_sorted[len(latencies_sorted) // 2]
            p95 = latencies_sorted[int(len(latencies_sorted) * 0.95)]
            p99 = latencies_sorted[int(len(latencies_sorted) * 0.99)]

            logger.info(f"\nLATENCY UNDER LOAD:")
            logger.info(f"  Min: {self.stats['min_latency']:.3f}s ({self.stats['min_latency']*1000:.1f}ms)")
            logger.info(f"  Max: {self.stats['max_latency']:.3f}s ({self.stats['max_latency']*1000:.1f}ms)")
            logger.info(f"  Average: {avg_latency:.3f}s ({avg_latency*1000:.1f}ms)")
            logger.info(f"  P50: {p50:.3f}s ({p50*1000:.1f}ms)")
            logger.info(f"  P95: {p95:.3f}s ({p95*1000:.1f}ms)")
            logger.info(f"  P99: {p99:.3f}s ({p99*1000:.1f}ms)")

        # Save results
        results_file = f"ultra_throughput_results_{int(time.time())}.json"
        self._save_results(results_file)
        logger.info(f"\nResults saved to: {results_file}")
        logger.info("=" * 80)

    def _save_results(self, filename: str):
        """Save results to JSON"""
        overall_throughput = self.stats['successful'] / sum(self.stats['latencies']) if sum(self.stats['latencies']) > 0 else 0

        results = {
            'test_type': 'ultra_high_throughput',
            'timestamp': self.stats['start_time'].isoformat() if self.stats['start_time'] else None,
            'target': f"{self.provider_host if self.use_real_provider else self.host}:{self.provider_port if self.use_real_provider else self.port}",
            'test_mode': 'real_provider' if self.use_real_provider else 'proxy',
            'config': {
                'num_emails': self.num_emails,
                'concurrent': self.concurrent,
                'from_email': self.from_email,
            },
            'results': {
                'total_requests': self.stats['total_requests'],
                'successful': self.stats['successful'],
                'failed': self.stats['failed'],
                'success_rate': self.stats['successful'] / self.stats['total_requests'] if self.stats['total_requests'] > 0 else 0,
                'throughput_rps': overall_throughput,
                'throughput_rpm': overall_throughput * 60,
                'throughput_rph': overall_throughput * 3600,
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


def handle_signal(signum, frame):
    """Handle Ctrl+C gracefully"""
    logger.info("\n\nShutting down gracefully...")
    sys.exit(0)


async def main():
    """Main entry point"""
    signal.signal(signal.SIGINT, handle_signal)

    parser = argparse.ArgumentParser(
        description='Ultra-High Throughput Test (5000+ msg/sec)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 5000 msg/sec (100 concurrent)
  python test_ultra_high_throughput.py --num-emails 5000 --concurrent 100

  # 10000 msg/sec (200 concurrent)
  python test_ultra_high_throughput.py --num-emails 10000 --concurrent 200

  # 50000 msg/sec (500 concurrent, extreme stress)
  python test_ultra_high_throughput.py --num-emails 50000 --concurrent 500 --verbose

  # Real provider at 5000 msg/sec
  python test_ultra_high_throughput.py --num-emails 5000 --concurrent 100 --use-real-provider --from email@gmail.com --password YOUR_TOKEN
        """
    )

    parser.add_argument(
        '--num-emails',
        type=int,
        default=5000,
        help='Number of emails to send (default: 5000)'
    )
    parser.add_argument(
        '--concurrent',
        type=int,
        default=100,
        help='Concurrent connections (default: 100)'
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
        default='test.account1@gmail.com',
        help='From email (default: test.account1@gmail.com)'
    )
    parser.add_argument(
        '--to',
        dest='to_email',
        type=str,
        default='recipient@outlook.com',
        help='To email (default: recipient@outlook.com)'
    )
    parser.add_argument(
        '--use-real-provider',
        action='store_true',
        help='Connect to real provider endpoint (Gmail/Outlook)'
    )
    parser.add_argument(
        '--provider-host',
        type=str,
        help='Real provider host (smtp.gmail.com or smtp.office365.com)'
    )
    parser.add_argument(
        '--provider-port',
        type=int,
        default=587,
        help='Real provider port (default: 587)'
    )
    parser.add_argument(
        '--password',
        type=str,
        default='placeholder',
        help='Password/token for real provider auth'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Verbose logging'
    )

    args = parser.parse_args()

    # Auto-detect provider host
    provider_host = args.provider_host
    if args.use_real_provider and not provider_host:
        if '@gmail.com' in args.from_email:
            provider_host = 'smtp.gmail.com'
        else:
            provider_host = 'smtp.office365.com'

    # Create tester
    tester = UltraHighThroughputTester(
        host=args.host,
        port=args.port,
        num_emails=args.num_emails,
        concurrent=args.concurrent,
        from_email=args.from_email,
        to_email=args.to_email,
        use_real_provider=args.use_real_provider,
        provider_host=provider_host or 'smtp.gmail.com',
        provider_port=args.provider_port,
        provider_password=args.password,
        verbose=args.verbose
    )

    try:
        await tester.run_ultra_high_throughput_test()
    except KeyboardInterrupt:
        logger.info("\nTest interrupted")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
