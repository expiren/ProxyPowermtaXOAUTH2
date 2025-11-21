#!/bin/bash
# Start XOAUTH2 Proxy with proper FD limits for high-volume traffic
#
# Usage:
#   ./start_proxy.sh                    # Start in foreground
#   ./start_proxy.sh --background       # Start in background (nohup)
#   ./start_proxy.sh --stop             # Stop running proxy

PROXY_DIR="/home/user/ProxyPowermtaXOAUTH2"
LOG_FILE="/var/log/xoauth2/xoauth2_proxy.log"
PID_FILE="/var/run/xoauth2_proxy.pid"

cd "$PROXY_DIR" || exit 1

# Set FD limits (critical for high-volume)
ulimit -n 65536

case "${1:-}" in
    --stop)
        echo "Stopping XOAUTH2 Proxy..."
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            if kill -0 "$PID" 2>/dev/null; then
                kill -TERM "$PID"
                echo "Sent SIGTERM to PID $PID"
                sleep 2
                if kill -0 "$PID" 2>/dev/null; then
                    echo "Force killing PID $PID"
                    kill -9 "$PID"
                fi
            fi
            rm -f "$PID_FILE"
        else
            pkill -f xoauth2_proxy
        fi
        echo "Stopped"
        exit 0
        ;;

    --background)
        echo "=== Starting XOAUTH2 Proxy (background) ==="
        echo "FD limit: $(ulimit -n)"
        echo "Starting at: $(date)"
        echo "Log file: $LOG_FILE"
        echo ""

        nohup python xoauth2_proxy_v2.py --config accounts.json >> "$LOG_FILE" 2>&1 &
        PID=$!
        echo "$PID" > "$PID_FILE"
        echo "Started with PID: $PID"
        echo "Monitor: tail -f $LOG_FILE"
        ;;

    *)
        echo "=== Starting XOAUTH2 Proxy (foreground) ==="
        echo "FD limit: $(ulimit -n)"
        echo "Starting at: $(date)"
        echo "Press Ctrl+C to stop"
        echo ""

        # Start proxy in foreground
        exec python xoauth2_proxy_v2.py --config accounts.json
        ;;
esac
