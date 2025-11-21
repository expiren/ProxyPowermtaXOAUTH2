#!/bin/bash
# Start proxy with explicit FD limit

cd /home/user/ProxyPowermtaXOAUTH2

# Set limits
ulimit -n 65536

echo "=== Starting XOAUTH2 Proxy ==="
echo "FD limit: $(ulimit -n)"
echo "Starting at: $(date)"
echo ""

# Start proxy
exec python xoauth2_proxy_v2.py --config accounts.json
