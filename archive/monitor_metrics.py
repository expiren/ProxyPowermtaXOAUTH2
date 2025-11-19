#!/usr/bin/env python3
"""
Real-time metrics monitor for XOAUTH2 Proxy
Displays live metrics from Prometheus endpoint

Usage:
    python monitor_metrics.py
    python monitor_metrics.py --host 127.0.0.1 --port 9090
"""

import requests
import time
import argparse
import sys
import os


def clear_screen():
    """Clear terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')


def parse_prometheus_metrics(text):
    """Parse Prometheus metrics text format"""
    metrics = {}
    for line in text.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        # Simple parsing (handles basic metrics without labels)
        if ' ' in line:
            parts = line.split(' ')
            metric_name = parts[0].split('{')[0]  # Get name without labels
            value = parts[-1]
            try:
                metrics[metric_name] = float(value)
            except ValueError:
                pass

    return metrics


def get_metrics(host, port):
    """Fetch metrics from Prometheus endpoint"""
    try:
        response = requests.get(f"http://{host}:{port}/metrics", timeout=5)
        if response.status_code == 200:
            return parse_prometheus_metrics(response.text)
        else:
            return None
    except Exception as e:
        return None


def display_metrics(metrics, prev_metrics):
    """Display metrics in formatted table"""
    clear_screen()

    print("=" * 80)
    print(" " * 25 + "XOAUTH2 PROXY - LIVE METRICS")
    print("=" * 80)
    print()

    # Calculate rates (messages per minute)
    if prev_metrics:
        messages_diff = metrics.get('messages_total', 0) - prev_metrics.get('messages_total', 0)
        auth_diff = metrics.get('auth_attempts_total', 0) - prev_metrics.get('auth_attempts_total', 0)
        msg_per_min = messages_diff * 6  # 10 second interval * 6 = per minute
        auth_per_min = auth_diff * 6
    else:
        msg_per_min = 0
        auth_per_min = 0

    # Messages
    print("📨 MESSAGE METRICS")
    print("-" * 80)
    print(f"  Total Messages:        {metrics.get('messages_total', 0):.0f}")
    print(f"  Current Rate:          {msg_per_min:.0f} messages/minute ({msg_per_min/60:.1f} msg/sec)")
    print(f"  Concurrent Messages:   {metrics.get('concurrent_messages', 0):.0f}")
    print()

    # Authentication
    print("🔐 AUTHENTICATION METRICS")
    print("-" * 80)
    print(f"  Total Auth Attempts:   {metrics.get('auth_attempts_total', 0):.0f}")
    print(f"  Current Auth Rate:     {auth_per_min:.0f} auth/minute")
    print(f"  Active Connections:    {metrics.get('smtp_connections_active', 0):.0f}")
    print(f"  Total Connections:     {metrics.get('smtp_connections_total', 0):.0f}")
    print()

    # Token Refresh
    print("🔄 TOKEN METRICS")
    print("-" * 80)
    print(f"  Token Refreshes:       {metrics.get('token_refresh_total', 0):.0f}")
    print(f"  Upstream Auth:         {metrics.get('upstream_auth_total', 0):.0f}")
    print()

    # Errors
    print("⚠️  ERROR METRICS")
    print("-" * 80)
    print(f"  Total Errors:          {metrics.get('errors_total', 0):.0f}")
    print(f"  Concurrent Limit Hit:  {metrics.get('concurrent_limit_exceeded', 0):.0f}")
    print()

    # Performance Assessment
    print("=" * 80)
    if msg_per_min >= 50000:
        status = "✅ EXCELLENT"
        message = "Target of 50k+ msg/min ACHIEVED!"
    elif msg_per_min >= 40000:
        status = "✅ GOOD"
        message = "Close to target (40k+ msg/min)"
    elif msg_per_min >= 25000:
        status = "⚠️  MODERATE"
        message = "25k+ msg/min, approaching target"
    elif msg_per_min >= 10000:
        status = "⚠️  WARMING UP"
        message = "10k+ msg/min, ramping up"
    elif msg_per_min >= 1000:
        status = "🔄 ACTIVE"
        message = "Processing messages..."
    else:
        status = "⏸️  IDLE"
        message = "Waiting for traffic..."

    print(f" {status}: {message}")
    print("=" * 80)
    print()
    print("Press Ctrl+C to exit | Refreshing every 10 seconds...")
    print()


def main():
    parser = argparse.ArgumentParser(description="Monitor XOAUTH2 Proxy metrics")
    parser.add_argument("--host", default="127.0.0.1", help="Metrics server host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=9090, help="Metrics server port (default: 9090)")
    parser.add_argument("--interval", type=int, default=10, help="Refresh interval in seconds (default: 10)")

    args = parser.parse_args()

    print(f"Connecting to metrics endpoint at http://{args.host}:{args.port}/metrics")
    print("Waiting for first metrics fetch...")
    print()

    prev_metrics = None

    try:
        while True:
            metrics = get_metrics(args.host, args.port)

            if metrics is None:
                clear_screen()
                print("=" * 80)
                print("ERROR: Unable to fetch metrics")
                print("=" * 80)
                print()
                print(f"Make sure the proxy is running on {args.host}:{args.port}")
                print("Check that the metrics server is enabled")
                print()
                print(f"Retrying in {args.interval} seconds...")
                time.sleep(args.interval)
                continue

            display_metrics(metrics, prev_metrics)

            prev_metrics = metrics.copy()
            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user")
        sys.exit(0)


if __name__ == "__main__":
    main()
