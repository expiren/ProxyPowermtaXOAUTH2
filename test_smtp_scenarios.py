"""
Advanced SMTP Load Testing Scenarios

This tool provides predefined test scenarios for different use cases:
- Quick validation
- Performance baseline
- Stress testing
- Stability testing
- Multi-account testing

Usage:
    python test_smtp_scenarios.py --scenario quick
    python test_smtp_scenarios.py --scenario stress --verbose
"""

import asyncio
import argparse
import sys
import logging
from datetime import datetime
from test_smtp_load import SMTPLoadTester

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger('smtp_scenarios')

# Predefined test scenarios
SCENARIOS = {
    'quick': {
        'name': 'Quick Validation',
        'description': 'Fast sanity check (2-3 minutes)',
        'num_emails': 100,
        'concurrent': 10,
        'expected_throughput': '10-20 req/s'
    },
    'baseline': {
        'name': 'Performance Baseline',
        'description': 'Before optimization (5-10 minutes)',
        'num_emails': 500,
        'concurrent': 25,
        'expected_throughput': '15-30 req/s'
    },
    'moderate': {
        'name': 'Moderate Load',
        'description': 'Normal production load (10-15 minutes)',
        'num_emails': 1000,
        'concurrent': 50,
        'expected_throughput': '30-60 req/s'
    },
    'stress': {
        'name': 'Stress Test',
        'description': 'Heavy load test (20-30 minutes)',
        'num_emails': 2000,
        'concurrent': 100,
        'expected_throughput': '50-150 req/s'
    },
    'sustained': {
        'name': 'Sustained Load',
        'description': 'Long-running stability test (60+ minutes)',
        'num_emails': 5000,
        'concurrent': 50,
        'expected_throughput': '30-80 req/s'
    },
    'peak': {
        'name': 'Peak Load',
        'description': 'Maximum throughput test (30+ minutes)',
        'num_emails': 10000,
        'concurrent': 150,
        'expected_throughput': '100-300+ req/s'
    }
}


async def run_scenario(
    scenario_name: str,
    host: str = '127.0.0.1',
    port: int = 2525,
    from_email: str = 'test@example.com',
    to_email: str = 'recipient@outlook.com',
    verbose: bool = False
):
    """Run a predefined test scenario"""

    if scenario_name not in SCENARIOS:
        logger.error(f"Unknown scenario: {scenario_name}")
        logger.info(f"Available scenarios: {', '.join(SCENARIOS.keys())}")
        return False

    scenario = SCENARIOS[scenario_name]

    # Print scenario info
    logger.info("=" * 80)
    logger.info(f"SCENARIO: {scenario['name']}")
    logger.info("=" * 80)
    logger.info(f"Description: {scenario['description']}")
    logger.info(f"Total emails: {scenario['num_emails']}")
    logger.info(f"Concurrent connections: {scenario['concurrent']}")
    logger.info(f"Expected throughput: {scenario['expected_throughput']}")
    logger.info(f"From: {from_email}")
    logger.info(f"To: {to_email}")
    logger.info(f"Target: {host}:{port}")
    logger.info("=" * 80)

    # Confirm before starting long tests
    if scenario['num_emails'] > 500 and not verbose:
        response = input("This is a long-running test. Continue? (y/n): ")
        if response.lower() != 'y':
            logger.info("Test cancelled by user")
            return False

    # Create and run tester
    tester = SMTPLoadTester(
        host=host,
        port=port,
        num_emails=scenario['num_emails'],
        concurrent=scenario['concurrent'],
        from_email=from_email,
        to_email=to_email
    )

    try:
        await tester.run_load_test()
        return True
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return False


async def run_comparison(
    host: str = '127.0.0.1',
    port: int = 2525,
    from_email: str = 'test@example.com',
    to_email: str = 'recipient@outlook.com'
):
    """
    Run a before/after comparison test

    This runs a baseline test, waits for user to make changes (e.g., restart proxy),
    then runs the same test again to compare results.
    """
    logger.info("=" * 80)
    logger.info("BEFORE/AFTER COMPARISON TEST")
    logger.info("=" * 80)
    logger.info("")
    logger.info("This will help you measure the impact of optimizations.")
    logger.info("")

    # Run baseline test
    logger.info("PHASE 1: Running BASELINE test...")
    logger.info("-" * 80)

    baseline_tester = SMTPLoadTester(
        host=host,
        port=port,
        num_emails=500,
        concurrent=25,
        from_email=from_email,
        to_email=to_email
    )

    try:
        await baseline_tester.run_load_test()
        baseline_stats = {
            'successful': baseline_tester.stats['successful'],
            'total_latency': baseline_tester.stats['total_latency'],
            'min_latency': baseline_tester.stats['min_latency'],
            'max_latency': baseline_tester.stats['max_latency'],
            'latencies': baseline_tester.stats['latencies']
        }
    except Exception as e:
        logger.error(f"Baseline test failed: {e}")
        return

    logger.info("")
    logger.info("=" * 80)
    logger.info("PHASE 2: Make your optimization changes")
    logger.info("=" * 80)
    logger.info("")
    logger.info("Examples:")
    logger.info("  1. Apply Phase 1 performance fixes")
    logger.info("  2. Restart the proxy: python xoauth2_proxy_v2.py --config accounts.json --port 2525")
    logger.info("  3. Come back here and press ENTER to continue")
    logger.info("")

    input("Press ENTER when you're ready to run the OPTIMIZED test...")

    # Run optimized test
    logger.info("")
    logger.info("PHASE 3: Running OPTIMIZED test...")
    logger.info("-" * 80)

    optimized_tester = SMTPLoadTester(
        host=host,
        port=port,
        num_emails=500,
        concurrent=25,
        from_email=from_email,
        to_email=to_email
    )

    try:
        await optimized_tester.run_load_test()
        optimized_stats = {
            'successful': optimized_tester.stats['successful'],
            'total_latency': optimized_tester.stats['total_latency'],
            'min_latency': optimized_tester.stats['min_latency'],
            'max_latency': optimized_tester.stats['max_latency'],
            'latencies': optimized_tester.stats['latencies']
        }
    except Exception as e:
        logger.error(f"Optimized test failed: {e}")
        return

    # Print comparison
    logger.info("")
    logger.info("=" * 80)
    logger.info("COMPARISON RESULTS")
    logger.info("=" * 80)

    # Throughput comparison
    if baseline_stats['latencies'] and optimized_stats['latencies']:
        baseline_rps = baseline_stats['successful'] / sum(baseline_stats['latencies'])
        optimized_rps = optimized_stats['successful'] / sum(optimized_stats['latencies'])
        improvement = ((optimized_rps - baseline_rps) / baseline_rps) * 100

        logger.info(f"\nThroughput:")
        logger.info(f"  Baseline: {baseline_rps:.1f} req/s")
        logger.info(f"  Optimized: {optimized_rps:.1f} req/s")
        logger.info(f"  Improvement: {improvement:+.1f}% ({optimized_rps/baseline_rps:.1f}x)")

    # Latency comparison
    if baseline_stats['latencies'] and optimized_stats['latencies']:
        baseline_avg = sum(baseline_stats['latencies']) / len(baseline_stats['latencies'])
        optimized_avg = sum(optimized_stats['latencies']) / len(optimized_stats['latencies'])
        improvement = ((baseline_avg - optimized_avg) / baseline_avg) * 100

        logger.info(f"\nAverage Latency:")
        logger.info(f"  Baseline: {baseline_avg:.3f}s")
        logger.info(f"  Optimized: {optimized_avg:.3f}s")
        logger.info(f"  Improvement: {improvement:+.1f}% faster")

    # P95 latency comparison
    if baseline_stats['latencies'] and optimized_stats['latencies']:
        baseline_p95 = sorted(baseline_stats['latencies'])[int(len(baseline_stats['latencies']) * 0.95)]
        optimized_p95 = sorted(optimized_stats['latencies'])[int(len(optimized_stats['latencies']) * 0.95)]
        improvement = ((baseline_p95 - optimized_p95) / baseline_p95) * 100

        logger.info(f"\nP95 Latency (95th percentile):")
        logger.info(f"  Baseline: {baseline_p95:.3f}s")
        logger.info(f"  Optimized: {optimized_p95:.3f}s")
        logger.info(f"  Improvement: {improvement:+.1f}% faster")

    logger.info("=" * 80)


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Advanced SMTP Load Testing Scenarios',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Scenarios:
  quick       - Quick validation (2-3 min, 100 emails)
  baseline    - Performance baseline (5-10 min, 500 emails)
  moderate    - Moderate load (10-15 min, 1000 emails)
  stress      - Heavy stress test (20-30 min, 2000 emails)
  sustained   - Long-running stability (60+ min, 5000 emails)
  peak        - Maximum throughput (30+ min, 10000 emails)
  compare     - Before/after comparison

Examples:
  # Run quick test
  python test_smtp_scenarios.py --scenario quick

  # Run baseline test
  python test_smtp_scenarios.py --scenario baseline

  # Run stress test (auto-confirm for long tests)
  python test_smtp_scenarios.py --scenario stress --verbose

  # Run before/after comparison
  python test_smtp_scenarios.py --scenario compare
        """
    )

    parser.add_argument(
        '--scenario',
        type=str,
        choices=list(SCENARIOS.keys()) + ['compare'],
        default='quick',
        help='Test scenario to run (default: quick)'
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
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Skip confirmation prompts for long tests'
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help='List all available scenarios'
    )

    args = parser.parse_args()

    # List scenarios
    if args.list:
        logger.info("Available Scenarios:")
        logger.info("=" * 80)
        for name, config in SCENARIOS.items():
            logger.info(f"\n{name.upper()}")
            logger.info(f"  Name: {config['name']}")
            logger.info(f"  Description: {config['description']}")
            logger.info(f"  Emails: {config['num_emails']}")
            logger.info(f"  Concurrent: {config['concurrent']}")
            logger.info(f"  Expected throughput: {config['expected_throughput']}")
        logger.info("\n" + "=" * 80)
        return

    # Run scenario
    try:
        if args.scenario == 'compare':
            await run_comparison(
                host=args.host,
                port=args.port,
                from_email=args.from_email,
                to_email=args.to_email
            )
        else:
            success = await run_scenario(
                scenario_name=args.scenario,
                host=args.host,
                port=args.port,
                from_email=args.from_email,
                to_email=args.to_email,
                verbose=args.verbose
            )
            sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
