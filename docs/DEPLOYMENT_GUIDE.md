# PowerMTA + XOAUTH2 Proxy - Complete Deployment Guide

**Version:** 1.0
**Last Updated:** 2025-11-14
**Status:** Production-Ready

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [System Requirements](#system-requirements)
3. [Installation & Setup](#installation--setup)
4. [Configuration](#configuration)
5. [Deployment](#deployment)
6. [Monitoring & Maintenance](#monitoring--maintenance)
7. [Troubleshooting](#troubleshooting)
8. [Production Checklist](#production-checklist)

---

## Architecture Overview

### System Design

```
┌─────────────────────────────────────────────────────────────────┐
│                    EXTERNAL SMTP CLIENTS                         │
│                  (PMTA Input Port: 25/587)                       │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                                                                   │
│  POWERMTA V6                                                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ INPUT SOURCES                                            │  │
│  │ - Port 25:  Standard SMTP                                │  │
│  │ - Port 587: Submission with AUTH                         │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ ROUTING ENGINE                                           │  │
│  │ - 20 Routes (user1-gmail to user20-gmail)                │  │
│  │ - 20 Virtual-MTAs (vmta-user1 to vmta-user20)            │  │
│  │ - Each VMTA bound to unique IP (192.168.1.100-.119)      │  │
│  │ - Domain-based routing (gmail.com)                       │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ SMTP AUTH PLAIN
                             │ account1@gmail.com
                             │ account2@gmail.com
                             │ ... (20 accounts)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                                                                   │
│  XOAUTH2 PROXY (127.0.0.1:2525)                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ AUTH Handler                                             │  │
│  │ - Accepts AUTH PLAIN from PMTA                           │  │
│  │ - Extracts account email                                 │  │
│  │ - Validates against accounts.json                        │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Token Management                                         │  │
│  │ - Stores OAuth tokens per account                        │  │
│  │ - Refreshes expired tokens (expires_at - 300s buffer)    │  │
│  │ - Tracks token age for metrics                           │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ XOAUTH2 Verification                                     │  │
│  │ - Constructs XOAUTH2 string: user=<email>\1auth=Bearer  │  │
│  │ - Verifies with Gmail/Outlook                            │  │
│  │ - Returns 535 on verification failure                    │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Message Flow                                             │  │
│  │ - Validates MAIL FROM / RCPT TO                          │  │
│  │ - Accepts DATA                                           │  │
│  │ - Supports dry-run mode (accept, don't send upstream)    │  │
│  │ - Enforces concurrency limits per-account               │  │
│  │ - Logs every step                                        │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Monitoring                                               │  │
│  │ - Prometheus metrics (port 9090/metrics)                 │  │
│  │ - Health endpoint (port 9090/health)                     │  │
│  │ - Verbose logging to /var/log/xoauth2_proxy.log          │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ XOAUTH2 Auth
                             │ user=account@gmail.com
                             │ auth=Bearer <token>
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ GMAIL / OUTLOOK SMTP (smtp.gmail.com:587)                        │
│ - Receives message                                              │
│ - Validates XOAUTH2 token                                       │
│ - Delivers message to recipients                                │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Client → PMTA**: Client connects to PMTA port 25/587, sends MAIL FROM
2. **PMTA Routing**: PMTA matches domain (gmail.com) to route, selects VMTA
3. **PMTA → Proxy**: PMTA connects to proxy (127.0.0.1:2525) with AUTH PLAIN
4. **Proxy AUTH**: Proxy extracts email, validates in accounts.json
5. **Token Refresh**: Proxy checks if token needs refresh, refreshes if needed
6. **XOAUTH2 Verify**: Proxy verifies token with Gmail
7. **Message Relay**: Proxy accepts message, can optionally send upstream
8. **Metrics**: Proxy records metrics (Prometheus)
9. **Logging**: Proxy logs all operations

### Key Features

✅ **20 Dedicated Accounts**: Each with own IP, VMTA, route
✅ **AUTH PLAIN Support**: PMTA authenticates with email as username
✅ **Token Management**: Automatic refresh before expiration (300s buffer)
✅ **Verbose Logging**: Every step logged with timestamps
✅ **Dry-Run Mode**: Accept messages but don't send upstream
✅ **Concurrency Limits**: Per-account (10) and global (100)
✅ **Prometheus Metrics**: Full instrumentation with 15+ metrics
✅ **SIGHUP Reload**: Hot-reload accounts.json without restart
✅ **Health Checks**: HTTP health endpoint
✅ **Production Quality**: Error handling, timeouts, resource limits

---

## System Requirements

### Hardware

- **CPU**: 2+ cores (proxy is I/O-bound, not CPU-intensive)
- **RAM**: 2-4 GB minimum (Python process ~100-200 MB, PMTA 1-2 GB)
- **Storage**: 10 GB for logs + queue

### Software

- **OS**: Linux (Ubuntu 18.04+, CentOS 7+, Debian 9+)
- **Python**: 3.6+ (for XOAUTH2 proxy)
- **PowerMTA**: v6.x (tested with 6.01 and later)
- **Dependencies**:
  - prometheus-client: `pip install prometheus-client`
  - base64, asyncio, json: Built-in Python libraries

### Network

- **IPs Required**: 20 dedicated IPs (192.168.1.100-192.168.1.119 in demo)
- **Ports Required**:
  - Port 25/587: PMTA input (from clients)
  - Port 2525: Proxy SMTP (PMTA → Proxy)
  - Port 9090: Prometheus metrics (internal monitoring)
- **Firewall**: Open outbound to smtp.gmail.com:587

---

## Installation & Setup

### Step 1: Install Python Dependencies

```bash
# Update package manager
sudo apt-get update
sudo apt-get install -y python3 python3-pip

# Install required packages
sudo pip3 install prometheus-client

# Verify installation
python3 --version
pip3 show prometheus-client
```

### Step 2: Create Application Directories

```bash
# Create directories
sudo mkdir -p /etc/xoauth2
sudo mkdir -p /var/log/xoauth2
sudo mkdir -p /opt/xoauth2
sudo mkdir -p /var/spool/xoauth2

# Set permissions
sudo chown root:root /etc/xoauth2
sudo chmod 750 /etc/xoauth2
sudo chown syslog:syslog /var/log/xoauth2
sudo chmod 755 /var/log/xoauth2
```

### Step 3: Install XOAUTH2 Proxy

```bash
# Copy proxy code
sudo cp xoauth2_proxy.py /opt/xoauth2/
sudo chmod 755 /opt/xoauth2/xoauth2_proxy.py

# Copy accounts configuration
sudo cp accounts.json /etc/xoauth2/
sudo chmod 600 /etc/xoauth2/accounts.json
sudo chown root:root /etc/xoauth2/accounts.json

# Test proxy startup
python3 /opt/xoauth2/xoauth2_proxy.py \
  --config /etc/xoauth2/accounts.json \
  --host 127.0.0.1 \
  --port 2525 \
  --metrics-port 9090

# Press Ctrl+C to stop, or run in background:
# python3 /opt/xoauth2/xoauth2_proxy.py ... &
```

### Step 4: Install PowerMTA Configuration

```bash
# Install PMTA (if not already installed)
# Follow PowerMTA official installation guide

# Backup existing config
sudo cp /etc/pmta/pmta.cfg /etc/pmta/pmta.cfg.backup.$(date +%Y%m%d)

# Copy new configuration
sudo cp pmta.cfg /etc/pmta/pmta.cfg

# Verify PMTA config syntax
sudo pmta check-config

# Fix any syntax errors before proceeding
```

### Step 5: Create Systemd Service Files

```bash
# Create XOAUTH2 proxy service
sudo tee /etc/systemd/system/xoauth2-proxy.service << 'EOF'
[Unit]
Description=XOAUTH2 SMTP Proxy for PowerMTA
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/xoauth2
ExecStart=/usr/bin/python3 /opt/xoauth2/xoauth2_proxy.py \
  --config /etc/xoauth2/accounts.json \
  --host 127.0.0.1 \
  --port 2525 \
  --metrics-port 9090

Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=xoauth2-proxy

# Resource limits
LimitNOFILE=65536
LimitNPROC=65536

[Install]
WantedBy=multi-user.target
EOF

# Create PMTA service (may already exist)
sudo systemctl daemon-reload
sudo systemctl enable xoauth2-proxy
```

---

## Configuration

### Accounts Configuration (accounts.json)

```json
{
  "accounts": [
    {
      "account_id": "user1",
      "email": "account1@gmail.com",
      "ip_address": "192.168.1.100",
      "vmta_name": "vmta-user1",
      "provider": "gmail",
      "client_id": "YOUR_CLIENT_ID_1.apps.googleusercontent.com",
      "client_secret": "YOUR_CLIENT_SECRET_1",
      "refresh_token": "1//0gJA7asfdZKRE8z...",
      "oauth_endpoint": "smtp.gmail.com:587",
      "oauth_token_url": "https://oauth2.googleapis.com/token",
      "max_concurrent_messages": 10,
      "max_messages_per_hour": 10000
    }
    // ... 19 more accounts
  ]
}
```

**Key Fields**:
- `account_id`: Unique identifier (used for VMTA/route naming)
- `email`: Gmail address (used for AUTH username)
- `ip_address`: Dedicated IP for this account
- `vmta_name`: Virtual-MTA name (must match PMTA config)
- `provider`: "gmail" or "outlook"
- `refresh_token`: OAuth2 refresh token from Google
- `max_concurrent_messages`: Limit concurrent messages (recommend 10)
- `max_messages_per_hour`: Rate limit (recommend 10000)

### Generating OAuth Tokens

```bash
# For Gmail:
# 1. Go to https://myaccount.google.com/security
# 2. Enable "Less secure app access"
# 3. Or use OAuth 2.0 Playground:
#    https://developers.google.com/oauthplayground
# 4. Select Gmail SMTP scope
# 5. Authorize and get refresh_token

# For Outlook:
# 1. Go to https://azure.microsoft.com/
# 2. Register application
# 3. Get client_id, client_secret
# 4. Request authorization code
# 5. Exchange for refresh_token
```

### PMTA Configuration

Key sections in pmta.cfg:

**Virtual-MTAs** (20 total):
```
<virtual-mta vmta-user1>
  smtp-source-host 192.168.1.100
</virtual-mta>
```

**Routes** (20 total):
```
<route user1-gmail>
  virtual-mta vmta-user1
  domain gmail.com
  smtp-host 127.0.0.1 port=2525
  auth-username account1@gmail.com
  auth-password placeholder
  max-smtp-out 10
  max-smtp-connections 5
</route>
```

### Proxy Command-Line Options

```bash
python3 xoauth2_proxy.py --help

Options:
  --config PATH          Path to accounts.json (default: /etc/xoauth2/accounts.json)
  --host HOST            Listen host (default: 127.0.0.1)
  --port PORT            Listen port (default: 2525)
  --metrics-port PORT    Prometheus metrics port (default: 9090)
  --dry-run              Accept messages but don't send upstream
  --global-concurrency N Global concurrency limit (default: 100)
```

---

## Deployment

### Step 1: Pre-Deployment Verification

```bash
# Check Python installation
python3 --version

# Check PMTA installation
which pmta
pmta show config | head -20

# Check network interfaces
ip addr show | grep "192.168.1.10"

# Check required ports available
netstat -tlnp | grep -E "2525|9090"
```

### Step 2: Start XOAUTH2 Proxy

```bash
# Option A: Start with systemd
sudo systemctl start xoauth2-proxy
sudo systemctl status xoauth2-proxy

# Option B: Start manually
python3 /opt/xoauth2/xoauth2_proxy.py \
  --config /etc/xoauth2/accounts.json

# Option C: Start in background with nohup
nohup python3 /opt/xoauth2/xoauth2_proxy.py \
  --config /etc/xoauth2/accounts.json \
  > /var/log/xoauth2_proxy.log 2>&1 &
```

### Step 3: Verify Proxy is Running

```bash
# Check listening ports
netstat -tlnp | grep 2525
# Expected: tcp  0  0 127.0.0.1:2525  0.0.0.0:*  LISTEN

# Test connectivity
echo "EHLO test" | nc 127.0.0.1 2525
# Expected: 220 xoauth2-proxy ESMTP service ready

# Check metrics
curl http://127.0.0.1:9090/metrics | head -20

# Check health
curl http://127.0.0.1:9090/health
# Expected: {"status": "healthy"}
```

### Step 4: Start/Reload PMTA

```bash
# Verify config syntax
sudo pmta check-config

# Start PMTA if not running
sudo systemctl start pmta

# Reload config
sudo pmta reload

# Verify startup
sudo pmta show config | grep -c "<virtual-mta"
# Expected: 20

sudo pmta show route | grep -c "user.*-gmail"
# Expected: 20
```

### Step 5: Test Message Flow

```bash
# Send test message through PMTA
swaks \
  --server 127.0.0.1:25 \
  --auth-user account1@gmail.com \
  --auth-password placeholder \
  --auth-method PLAIN \
  --from "test@example.com" \
  --to "recipient@gmail.com" \
  --h-Subject "Deployment Test" \
  --body "Testing complete deployment"

# Expected SMTP response: 250 2.0.0 OK

# Check logs
tail -50 /var/log/xoauth2_proxy.log | grep -i "auth\|connection"
tail -50 /var/log/pmta/pmta.log | grep -i "message\|route"
```

---

## Monitoring & Maintenance

### Real-Time Monitoring

```bash
# Monitor proxy logs
tail -f /var/log/xoauth2_proxy.log

# Monitor PMTA logs
tail -f /var/log/pmta/pmta.log

# Monitor metrics
watch -n 5 'curl -s http://127.0.0.1:9090/metrics | grep -v "^#"'

# Monitor system resources
watch -n 5 'ps aux | grep -E "python3|pmta"'
```

### Prometheus Integration

```bash
# Install Prometheus (if not installed)
sudo apt-get install prometheus

# Add scrape job to /etc/prometheus/prometheus.yml
cat >> /etc/prometheus/prometheus.yml << 'EOF'
scrape_configs:
  - job_name: 'xoauth2-proxy'
    static_configs:
      - targets: ['127.0.0.1:9090']
    scrape_interval: 15s
    scrape_timeout: 10s
EOF

# Restart Prometheus
sudo systemctl restart prometheus

# Access Prometheus UI
# http://localhost:9090
```

### Key Metrics to Monitor

```bash
# Authentication success rate
curl -s http://127.0.0.1:9090/metrics | grep "auth_attempts_total"

# Message delivery rate
curl -s http://127.0.0.1:9090/metrics | grep "messages_total"

# Token refresh status
curl -s http://127.0.0.1:9090/metrics | grep "token_refresh"

# Active connections
curl -s http://127.0.0.1:9090/metrics | grep "smtp_connections_active"

# Concurrent message limits
curl -s http://127.0.0.1:9090/metrics | grep "concurrent_messages"
```

### Hot-Reload Accounts

```bash
# Update accounts.json with new credentials
sudo nano /etc/xoauth2/accounts.json

# Reload without restarting
kill -HUP <proxy-pid>

# Or find PID automatically
kill -HUP $(pgrep -f xoauth2_proxy)

# Verify reload
grep "Loaded.*accounts" /var/log/xoauth2_proxy.log | tail -1
```

### Backup & Recovery

```bash
# Backup configurations
sudo tar -czf /backup/xoauth2_backup_$(date +%Y%m%d).tar.gz \
  /etc/xoauth2/ \
  /etc/pmta/pmta.cfg

# Backup logs
sudo tar -czf /backup/xoauth2_logs_$(date +%Y%m%d).tar.gz \
  /var/log/xoauth2_proxy.log \
  /var/log/pmta/pmta.log

# Restore from backup
sudo tar -xzf /backup/xoauth2_backup_YYYYMMDD.tar.gz -C /

# Verify restored config
cat /etc/xoauth2/accounts.json | jq '.' | head -20
```

---

## Troubleshooting

### Common Issues

#### Proxy Won't Start

```bash
# Check Python syntax
python3 -m py_compile /opt/xoauth2/xoauth2_proxy.py

# Check dependencies
python3 -c "import prometheus_client"

# Check file permissions
ls -la /etc/xoauth2/accounts.json
ls -la /var/log/xoauth2/

# Start with verbose output
python3 /opt/xoauth2/xoauth2_proxy.py \
  --config /etc/xoauth2/accounts.json \
  2>&1 | head -50
```

#### AUTH Fails

```bash
# Check accounts.json for email
grep "account1@gmail.com" /etc/xoauth2/accounts.json

# Check for typos
cat /etc/xoauth2/accounts.json | jq '.accounts[0].email'

# Test directly
echo 'Testing account...' && \
python3 -c "
import json
with open('/etc/xoauth2/accounts.json') as f:
    accounts = json.load(f)
    for acc in accounts['accounts']:
        print(f\"{acc['email']} -> {acc['account_id']}\")
"
```

#### Messages Stuck in Queue

```bash
# Check PMTA queue
sudo pmta show queue

# Force delivery attempt
sudo pmta send-queued-messages

# Check route statistics
sudo pmta show route user1-gmail

# Check connection status
sudo pmta show connections
```

#### Metrics Not Available

```bash
# Check metrics port
netstat -tlnp | grep 9090

# Test metrics endpoint
curl -v http://127.0.0.1:9090/metrics

# Check for port conflicts
lsof -i :9090
```

### Debug Commands

```bash
# Check proxy process
ps aux | grep xoauth2_proxy

# Check open files
lsof -p $(pgrep -f xoauth2_proxy)

# Check network connections
netstat -tnp | grep python3

# Trace system calls
strace -p $(pgrep -f xoauth2_proxy)

# Check disk space
df -h /var/log
du -sh /var/log/xoauth2_proxy.log
```

---

## Production Checklist

Before going production, verify:

### Security

- [ ] accounts.json is readable only by proxy user (chmod 600)
- [ ] OAuth tokens are valid and not expired
- [ ] Proxy listens only on 127.0.0.1 (not 0.0.0.0)
- [ ] Metrics port (9090) is not exposed to internet
- [ ] PMTA auth passwords are placeholders (proxy ignores them)
- [ ] SSH access to proxy server is restricted
- [ ] Logs don't contain sensitive information (tokens, passwords)
- [ ] Firewall rules are in place

### Performance

- [ ] All 20 VMTAs bound to correct IPs
- [ ] All 20 routes pointing to proxy on 127.0.0.1:2525
- [ ] max-smtp-out set to 10 per route
- [ ] max-concurrent-messages set to 10 per account
- [ ] Global concurrency limit set to 100
- [ ] Proxy starts within 5 seconds
- [ ] No memory leaks (monitor over 24 hours)
- [ ] CPU usage stays below 50%

### Reliability

- [ ] Proxy restarts on crash (systemd Restart=on-failure)
- [ ] Logs are rotated (logrotate or journalctl)
- [ ] Disk space is sufficient (check /var/log)
- [ ] Network connectivity to Gmail is stable
- [ ] Backup of accounts.json exists
- [ ] Backup of pmta.cfg exists
- [ ] SIGHUP reload tested and working
- [ ] Health endpoint returns 200 OK

### Testing

- [ ] AUTH succeeds for all 20 accounts
- [ ] Messages deliver through all 20 routes
- [ ] VMTA IP binding verified
- [ ] SPF/DKIM validation passes
- [ ] Prometheus metrics exported
- [ ] Dry-run mode functional
- [ ] Concurrency limits enforced
- [ ] Load test with 1000+ messages
- [ ] Stress test with 100+ concurrent connections

### Documentation

- [ ] accounts.json schema documented
- [ ] PMTA config changes documented
- [ ] Runbook for common issues created
- [ ] Monitoring/alerting rules created
- [ ] Escalation contacts documented
- [ ] Backup schedule established
- [ ] Change log maintained

---

## Support & Troubleshooting Reference

### Log Locations

```
/var/log/xoauth2_proxy.log      - Proxy logs
/var/log/pmta/pmta.log          - PMTA logs
/var/log/pmta/bounces.log       - Bounce logs
/var/log/pmta/failures.log      - Failure logs
```

### Port Reference

```
25    - PMTA standard SMTP input
587   - PMTA submission (with AUTH)
2525  - XOAUTH2 proxy SMTP
9090  - Prometheus metrics
```

### File Locations

```
/etc/xoauth2/accounts.json      - Account configuration
/etc/pmta/pmta.cfg              - PMTA configuration
/opt/xoauth2/xoauth2_proxy.py   - Proxy executable
/etc/systemd/system/xoauth2-proxy.service - Systemd service
```

### Useful Commands

```bash
# View proxy status
sudo systemctl status xoauth2-proxy

# View PMTA status
sudo systemctl status pmta

# Restart both
sudo systemctl restart xoauth2-proxy pmta

# View recent errors
sudo grep ERROR /var/log/xoauth2_proxy.log | tail -20

# Monitor metrics
curl -s http://127.0.0.1:9090/metrics | grep smtp_connections_active

# Force config reload
kill -HUP $(pgrep -f xoauth2_proxy)
```

---

## Next Steps

1. **Customize accounts.json** with your 20 Gmail accounts and IPs
2. **Generate OAuth tokens** for each account using Google OAuth playground
3. **Update proxy** with actual OAuth credentials
4. **Deploy** to production server
5. **Run test plan** to verify all components
6. **Monitor metrics** and establish alerting rules
7. **Document** any customizations or changes
8. **Train team** on operational procedures

---

**End of Deployment Guide**
