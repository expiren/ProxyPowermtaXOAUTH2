#!/bin/bash
# Diagnostic script to check actual limits when proxy runs

echo "=== System-wide limits ==="
echo "System-wide max files: $(cat /proc/sys/fs/file-max)"
echo "System-wide open files: $(cat /proc/sys/fs/file-nr | awk '{print $1}')"
echo ""

echo "=== Current shell limits ==="
echo "Soft limit (ulimit -Sn): $(ulimit -Sn)"
echo "Hard limit (ulimit -Hn): $(ulimit -Hn)"
echo ""

echo "=== TCP limits ==="
echo "TCP backlog (somaxconn): $(cat /proc/sys/net/core/somaxconn)"
echo "TCP syn backlog: $(cat /proc/sys/net/ipv4/tcp_max_syn_backlog)"
echo ""

echo "=== Starting proxy with increased limits ==="
ulimit -n 65536
echo "Set ulimit to: $(ulimit -n)"

cd /home/user/ProxyPowermtaXOAUTH2
python xoauth2_proxy_v2.py --config accounts.json &
PROXY_PID=$!

sleep 2

if ps -p $PROXY_PID > /dev/null; then
    echo ""
    echo "=== Proxy running (PID: $PROXY_PID) ==="
    echo "Proxy FD limits:"
    cat /proc/$PROXY_PID/limits | grep "open files"
    echo ""
    echo "Current FD usage:"
    lsof -p $PROXY_PID 2>/dev/null | wc -l
    echo ""
    echo "Press Ctrl+C to stop monitoring, or send test traffic now"
    echo "Monitoring FD usage every 2 seconds..."

    # Monitor FD usage
    while ps -p $PROXY_PID > /dev/null; do
        FD_COUNT=$(lsof -p $PROXY_PID 2>/dev/null | wc -l)
        echo "$(date +%H:%M:%S) - FDs in use: $FD_COUNT"
        sleep 2
    done
else
    echo "ERROR: Proxy failed to start!"
fi
