# PowerMTA + XOAUTH2 Proxy - Comprehensive Test Plan

**Document Version:** 1.0
**Last Updated:** 2025-11-14
**Test Environment:** Production-Ready

---

## Table of Contents

1. [Pre-Test Requirements](#pre-test-requirements)
2. [Test Environment Setup](#test-environment-setup)
3. [Proxy Authentication Tests](#proxy-authentication-tests)
4. [PMTA Routing Tests](#pmta-routing-tests)
5. [VMTA IP Binding Tests](#vmta-ip-binding-tests)
6. [End-to-End Message Flow Tests](#end-to-end-message-flow-tests)
7. [SPF/DKIM Validation](#spfdkim-validation)
8. [Gmail-Specific Tests](#gmail-specific-tests)
9. [Concurrency & Rate Limiting Tests](#concurrency--rate-limiting-tests)
10. [Prometheus Metrics Validation](#prometheus-metrics-validation)
11. [Troubleshooting Guide](#troubleshooting-guide)

---

## Pre-Test Requirements

### Required Tools

```bash
# Install swaks (Swiss Army Knife for SMTP)
sudo apt-get install swaks

# Install prometheus client (optional, for manual metric checks)
pip install prometheus-client

# Install curl (for health checks)
sudo apt-get install curl

# Install tcpdump (for packet analysis)
sudo apt-get install tcpdump

# Install openssl (for TLS testing)
sudo apt-get install openssl

# Install dig/nslookup (for DNS validation)
sudo apt-get install dnsutils
```

### Test Data Preparation

```bash
# Create test email addresses
TEST_EMAIL_1="account1@gmail.com"
TEST_EMAIL_2="account2@gmail.com"
TEST_EMAIL_N="account20@gmail.com"

# Create test recipient list
cat > test_recipients.txt << 'EOF'
test.user@example.com
verify.email@example.com
qa.test@example.com
EOF

# Generate test messages
TIMESTAMP=$(date +%s)
TEST_SUBJECT="ProxyPMTA Test Message $TIMESTAMP"
```

### Environment Configuration

```bash
# Set environment variables
export PROXY_HOST="127.0.0.1"
export PROXY_PORT="2525"
export PMTA_HOST="127.0.0.1"
export PMTA_PORT="25"
export METRICS_PORT="9090"
export LOG_DIR="/var/log/xoauth2"
export PMTA_LOG_DIR="/var/log/pmta"

# Create log directories
sudo mkdir -p $LOG_DIR $PMTA_LOG_DIR
sudo chown pmta:pmta $PMTA_LOG_DIR
```

---

## Test Environment Setup

### Step 1: Verify Proxy is Running

```bash
# Check if proxy is listening
netstat -tlnp | grep 2525
# Expected output: tcp  0  0  127.0.0.1:2525  0.0.0.0:*  LISTEN  <pid>/python3

# Alternative with ss
ss -tlnp | grep 2525

# Test connectivity
echo "EHLO test" | nc -w 5 127.0.0.1 2525
# Expected response: 220 xoauth2-proxy ESMTP service ready

# Check metrics endpoint
curl -s http://127.0.0.1:9090/metrics | head -20

# Check health endpoint
curl -s http://127.0.0.1:9090/health
# Expected response: {"status": "healthy"}
```

### Step 2: Verify PMTA is Running

```bash
# Check PMTA status
sudo service pmta status

# Verify PMTA ports
netstat -tlnp | grep pmta

# Check PMTA is configured
sudo pmta show config | head -50

# Verify virtual-mtas are loaded
sudo pmta show vmta

# Expected output should show all 20 vmta-user1 through vmta-user20
```

### Step 3: Verify Network Configuration

```bash
# Check if all IPs are bound
ip addr show

# Verify proxy IP binding
ip addr show | grep "192.168.1.10"

# Check routing
route -n | head -20

# Test DNS resolution
nslookup gmail.com
nslookup smtp.gmail.com
```

### Step 4: Check Log Files

```bash
# Monitor proxy logs in real-time
tail -f /var/log/xoauth2_proxy.log

# Monitor PMTA logs in real-time
tail -f /var/log/pmta/pmta.log

# Check for startup errors
grep -i "error\|warning" /var/log/xoauth2_proxy.log | tail -20
grep -i "error\|warning" /var/log/pmta/pmta.log | tail -20
```

---

## Proxy Authentication Tests

### Test 1.1: Basic Connection to Proxy

```bash
# Open raw SMTP connection
nc -v 127.0.0.1 2525

# Type the following commands
EHLO test.example.com
# Expected: 250-xoauth2-proxy
# Expected: 250-AUTH PLAIN
# Expected: 250-SIZE 52428800
# Expected: 250 8BITMIME

QUIT
```

### Test 1.2: AUTH PLAIN with Valid Account

```bash
# Create AUTH credentials for account1@gmail.com
# Format: base64(\\0account1@gmail.com\\0password)

AUTH_CREDS=$(echo -ne '\0account1@gmail.com\0placeholder' | base64 -w 0)
echo "AUTH_CREDS=$AUTH_CREDS"

# Connect and authenticate
swaks \
  --server 127.0.0.1:2525 \
  --auth-user account1@gmail.com \
  --auth-password placeholder \
  --auth-method PLAIN \
  --from test@example.com \
  --to verify@example.com \
  --h-Subject "AUTH Test" \
  --body "Test AUTH PLAIN"

# Expected response: 235 2.7.0 Authentication successful

# Verify in logs
grep "AUTH attempt" /var/log/xoauth2_proxy.log | tail -5
grep "AUTH successful" /var/log/xoauth2_proxy.log | tail -5
```

### Test 1.3: AUTH PLAIN with Invalid Account

```bash
# Try with non-existent account
swaks \
  --server 127.0.0.1:2525 \
  --auth-user nonexistent@gmail.com \
  --auth-password placeholder \
  --auth-method PLAIN \
  --from test@example.com \
  --to verify@example.com \
  --h-Subject "Invalid AUTH Test" \
  --body "This should fail"

# Expected: 535 authentication failed

# Verify in logs
grep "account nonexistent@gmail.com not found" /var/log/xoauth2_proxy.log
```

### Test 1.4: AUTH Without Credentials

```bash
# Try to send without AUTH
swaks \
  --server 127.0.0.1:2525 \
  --from test@example.com \
  --to verify@example.com \
  --h-Subject "No AUTH Test" \
  --body "Should fail without auth"

# Expected: 530 authentication required
```

### Test 1.5: Multiple AUTH Attempts

```bash
# Test rapid sequential AUTH attempts to check token refresh

for i in {1..5}; do
  echo "AUTH attempt $i at $(date)"
  swaks \
    --server 127.0.0.1:2525 \
    --auth-user account1@gmail.com \
    --auth-password placeholder \
    --auth-method PLAIN \
    --from "test$i@example.com" \
    --to "verify$i@example.com" \
    --h-Subject "Attempt $i" \
    --body "Auth test $i" \
    --quiet
  sleep 1
done

# Check token refresh in logs
grep "Token refreshed" /var/log/xoauth2_proxy.log | wc -l

# Expected: Should see at most 1-2 token refreshes (cached)
```

---

## PMTA Routing Tests

### Test 2.1: Verify PMTA Routes

```bash
# List all configured routes
sudo pmta show route

# Expected output should show all user1-gmail through user20-gmail routes

# Show specific route
sudo pmta show route user1-gmail

# Expected output:
# route name: user1-gmail
# virtual-mta: vmta-user1
# domain: gmail.com
# smtp-host: 127.0.0.1:2525
# auth-username: account1@gmail.com
```

### Test 2.2: Route Selection by Account

```bash
# Submit message from account1 perspective
swaks \
  --server 127.0.0.1:25 \
  --auth-user account1@gmail.com \
  --auth-password placeholder \
  --auth-method PLAIN \
  --from "sender1@senderdomain.com" \
  --to "test@gmail.com" \
  --h-Subject "Route Test User1" \
  --body "This should use vmta-user1"

# Check which route was used
sudo pmta show queue | grep "user1-gmail"

# Alternative: check PMTA logs
grep "route.*user1-gmail" /var/log/pmta/pmta.log | tail -5
```

### Test 2.3: Verify All 20 Routes Work

```bash
# Script to test all accounts
for i in {1..20}; do
  EMAIL="account$i@gmail.com"
  ROUTE="user$i-gmail"

  echo "Testing route: $ROUTE ($EMAIL)"

  swaks \
    --server 127.0.0.1:25 \
    --auth-user "$EMAIL" \
    --auth-password placeholder \
    --auth-method PLAIN \
    --from "test$i@example.com" \
    --to "verify$i@gmail.com" \
    --h-Subject "Route Test $i" \
    --body "Route test for user $i" \
    --quiet \
    2>&1 | grep -i "ok\|error"

  sleep 2
done

# Verify all routes accepted messages
sudo pmta show stats | grep "Messages Received"
```

### Test 2.4: Domain Matching

```bash
# Test that gmail.com messages use gmail routes

# Gmail message
swaks \
  --server 127.0.0.1:25 \
  --auth-user account1@gmail.com \
  --auth-password placeholder \
  --auth-method PLAIN \
  --from "test@example.com" \
  --to "test@gmail.com" \
  --h-Subject "Gmail Domain Test" \
  --body "Should use gmail route"

# Non-gmail message (should use default route)
swaks \
  --server 127.0.0.1:25 \
  --auth-user account1@gmail.com \
  --auth-password placeholder \
  --auth-method PLAIN \
  --from "test@example.com" \
  --to "test@yahoo.com" \
  --h-Subject "Non-Gmail Domain Test" \
  --body "Should use default route"

# Check which routes handled messages
grep "Message.*accepted" /var/log/pmta/pmta.log | tail -10
```

---

## VMTA IP Binding Tests

### Test 3.1: Verify VMTA IP Bindings

```bash
# Show all virtual-mtas and their bindings
sudo pmta show vmta

# Expected output for each:
# vmta name: vmta-user1
# outbound-ip: 192.168.1.100
# etc.
```

### Test 3.2: Verify Source IPs in SMTP

```bash
# Use swaks with source IP specification
# For each account, verify it uses the correct source IP

# Test vmta-user1 (should use 192.168.1.100)
swaks \
  --server 127.0.0.1:25 \
  --auth-user account1@gmail.com \
  --auth-password placeholder \
  --auth-method PLAIN \
  --from "test@example.com" \
  --to "test@gmail.com" \
  --h-Subject "VMTA IP Binding Test 1" \
  --body "Check source IP"

# To verify actual source IP, use tcpdump on the proxy side
sudo tcpdump -i lo -n "tcp port 2525" -A 2>&1 | grep -i "mail from" | head -5
```

### Test 3.3: Verify IP Binding Persistence

```bash
# Send multiple messages through same vmta
for i in {1..5}; do
  swaks \
    --server 127.0.0.1:25 \
    --auth-user account1@gmail.com \
    --auth-password placeholder \
    --auth-method PLAIN \
    --from "test$i@example.com" \
    --to "verify$i@gmail.com" \
    --h-Subject "IP Binding Test $i" \
    --body "Message $i from vmta-user1" \
    --quiet
  sleep 1
done

# Check that all messages used the same vmta
sudo pmta show queue | grep -c "vmta-user1"
```

### Test 3.4: Verify Load Distribution

```bash
# Send messages to different accounts to verify load distribution

# Submit messages to all 20 accounts
for i in {1..20}; do
  EMAIL="account$i@gmail.com"
  VMTA="vmta-user$i"

  swaks \
    --server 127.0.0.1:25 \
    --auth-user "$EMAIL" \
    --auth-password placeholder \
    --auth-method PLAIN \
    --from "test$i@example.com" \
    --to "verify$i@gmail.com" \
    --h-Subject "Load Dist Test $i" \
    --body "Message for $VMTA" \
    --quiet

  sleep 1
done

# Check distribution across VMTAs
sudo pmta show queue | grep "vmta-user" | awk '{print $2}' | sort | uniq -c
```

---

## End-to-End Message Flow Tests

### Test 4.1: Simple Message Delivery

```bash
# Send a simple test message
swaks \
  --server 127.0.0.1:25 \
  --auth-user account1@gmail.com \
  --auth-password placeholder \
  --auth-method PLAIN \
  --from "sender@example.com" \
  --to "recipient@gmail.com" \
  --h-Subject "Simple Message Test" \
  --h-Date: "$(date -R)" \
  --body "This is a simple test message"

# Expected SMTP response: 250 2.0.0 OK

# Check proxy logs
echo "=== Proxy logs ==="
tail -20 /var/log/xoauth2_proxy.log | grep -E "MAIL|RCPT|DATA|Connection"

# Check PMTA logs
echo "=== PMTA logs ==="
tail -20 /var/log/pmta/pmta.log
```

### Test 4.2: Message with Multiple Recipients

```bash
# Create multi-recipient message
cat > /tmp/multirecip.txt << 'EOF'
RCPT TO:<user1@gmail.com>
RCPT TO:<user2@gmail.com>
RCPT TO:<user3@gmail.com>
EOF

swaks \
  --server 127.0.0.1:25 \
  --auth-user account1@gmail.com \
  --auth-password placeholder \
  --auth-method PLAIN \
  --from "sender@example.com" \
  --to "user1@gmail.com" \
  --to "user2@gmail.com" \
  --to "user3@gmail.com" \
  --h-Subject "Multi-Recipient Test" \
  --body "Message to 3 recipients"

# Verify in logs
grep "RCPT TO" /var/log/xoauth2_proxy.log | tail -10
```

### Test 4.3: Large Message

```bash
# Create a larger message body (1MB)
LARGE_BODY=$(python3 -c "print('x' * 1000000)")

swaks \
  --server 127.0.0.1:25 \
  --auth-user account1@gmail.com \
  --auth-password placeholder \
  --auth-method PLAIN \
  --from "sender@example.com" \
  --to "recipient@gmail.com" \
  --h-Subject "Large Message Test (1MB)" \
  --body "$LARGE_BODY"

# Check message size limits
grep "SIZE" /var/log/xoauth2_proxy.log | tail -5
```

### Test 4.4: Message with Attachments

```bash
# Create test file with content
echo "This is test attachment content" > /tmp/test_attachment.txt

# Send message with attachment using swaks
swaks \
  --server 127.0.0.1:25 \
  --auth-user account1@gmail.com \
  --auth-password placeholder \
  --auth-method PLAIN \
  --from "sender@example.com" \
  --to "recipient@gmail.com" \
  --h-Subject "Message with Attachment" \
  --attach-type "text/plain" \
  --attach "/tmp/test_attachment.txt" \
  --body "See attached file"
```

---

## SPF/DKIM Validation

### Test 5.1: Verify DKIM Configuration

```bash
# Check if DKIM key exists
ls -la /etc/pmta/dkim/

# Expected: gmail.key should exist

# Verify DKIM key is loaded in PMTA
sudo pmta show config | grep -i "dkim"

# Check PMTA DKIM signer configuration
grep -r "dkim" /etc/pmta/ | grep -v "^#"
```

### Test 5.2: SPF Record Validation

```bash
# Check SPF records for test domains
dig +short TXT example.com | grep -i spf

# Example SPF record for PMTA:
# "v=spf1 ip4:192.168.1.100 ip4:192.168.1.101 ... ip4:192.168.1.119 ~all"

# Validate SPF with online tool
nslookup -type=TXT example.com

# Check SPF policy for gmail.com
dig +short TXT gmail.com | grep -i spf
```

### Test 5.3: DKIM Signature Validation

```bash
# Send message and extract DKIM-Signature header
swaks \
  --server 127.0.0.1:25 \
  --auth-user account1@gmail.com \
  --auth-password placeholder \
  --auth-method PLAIN \
  --from "sender@example.com" \
  --to "recipient@gmail.com" \
  --h-Subject "DKIM Test" \
  --body "Test message" \
  -o /tmp/dkim_test.msg

# Check for DKIM-Signature header
grep -i "DKIM-Signature" /tmp/dkim_test.msg

# Verify signature algorithm
grep "a=" /tmp/dkim_test.msg | grep -i "rsa"
```

### Test 5.4: Return-Path Validation

```bash
# Send message and check Return-Path
swaks \
  --server 127.0.0.1:25 \
  --auth-user account1@gmail.com \
  --auth-password placeholder \
  --auth-method PLAIN \
  --from "sender@example.com" \
  --to "recipient@gmail.com" \
  --h-Subject "Return-Path Test" \
  --body "Test" \
  -o /tmp/returnpath_test.msg

# Check Return-Path header
grep -i "^Return-Path:" /tmp/returnpath_test.msg

# Should be: Return-Path: <sender@example.com>
```

---

## Gmail-Specific Tests

### Test 6.1: Gmail Authentication

```bash
# Test XOAUTH2 token verification
swaks \
  --server 127.0.0.1:2525 \
  --auth-user account1@gmail.com \
  --auth-password placeholder \
  --auth-method PLAIN \
  --from "test@example.com" \
  --to "test@gmail.com" \
  --h-Subject "XOAUTH2 Test" \
  --body "Testing XOAUTH2 authentication"

# Check for XOAUTH2 verification in logs
grep "XOAUTH2 verification" /var/log/xoauth2_proxy.log | tail -5
grep "upstream_auth_total" /var/log/xoauth2_proxy.log | tail -5
```

### Test 6.2: Gmail Rate Limiting Response

```bash
# Simulate Gmail rate limit response
# Note: In production, Gmail will rate limit if you exceed limits

# Monitor for rate limit errors
grep -i "452\|429\|quota" /var/log/xoauth2_proxy.log

# Check PMTA retry logic
grep -i "retry\|attempt" /var/log/pmta/pmta.log | tail -10
```

### Test 6.3: Gmail Quota Exceeded

```bash
# Monitor for quota exceeded responses
grep -i "552\|quota\|exceeded" /var/log/xoauth2_proxy.log

# In test logs, look for:
# - 552 5.1.3 Your message was not delivered
# - Reason: Domain policy violation
```

### Test 6.4: Gmail SMTP Port 465 (TLS)

```bash
# Note: Current setup uses port 587, but Gmail supports 465

# If configuring for port 465 (SMTPS):
swaks \
  --server smtp.gmail.com:465 \
  --auth-user account1@gmail.com \
  --auth-password placeholder \
  --auth-method XOAUTH2 \
  --auth-optional \
  --tls-required \
  --from "test@example.com" \
  --to "verify@gmail.com" \
  --h-Subject "Gmail TLS Test" \
  --body "Testing TLS"

# Expected: Connection via TLS
```

---

## Concurrency & Rate Limiting Tests

### Test 7.1: Concurrent Messages per Account

```bash
# Test max_concurrent_messages limit (set to 10 in accounts.json)

# Send 15 messages rapidly and monitor which ones queue
bash << 'SCRIPT'
for i in {1..15}; do
  (
    swaks \
      --server 127.0.0.1:25 \
      --auth-user account1@gmail.com \
      --auth-password placeholder \
      --auth-method PLAIN \
      --from "test$i@example.com" \
      --to "recipient$i@gmail.com" \
      --h-Subject "Concurrency Test $i" \
      --body "Message $i" \
      --quiet
  ) &
done
wait

echo "All 15 messages submitted"
SCRIPT

# Check queue
sudo pmta show queue | grep "account1\|vmta-user1"

# Expected: Some messages will be queued, not all sent immediately
```

### Test 7.2: Global Concurrency Limit

```bash
# Test global concurrency limit (100 in proxy)

# Submit many messages across all accounts
bash << 'SCRIPT'
for account_num in {1..20}; do
  for msg_num in {1..10}; do
    EMAIL="account$account_num@gmail.com"
    (
      swaks \
        --server 127.0.0.1:25 \
        --auth-user "$EMAIL" \
        --auth-password placeholder \
        --auth-method PLAIN \
        --from "test$msg_num@example.com" \
        --to "recipient$msg_num@gmail.com" \
        --h-Subject "Global Concurrency Test" \
        --body "Global test" \
        --quiet
    ) &
  done
done
wait

echo "All 200 messages submitted"
SCRIPT

# Monitor metrics
curl -s http://127.0.0.1:9090/metrics | grep "concurrent_messages\|concurrent_limit"
```

### Test 7.3: Rate Limiting per Account

```bash
# Test max_messages_per_hour limit (10000 in accounts.json)

# Monitor rate limit in metrics
watch -n 5 'curl -s http://127.0.0.1:9090/metrics | grep "messages_total\|messages_per"'

# Alternative: Check logs
grep "rate_limit\|quota\|exceeded" /var/log/xoauth2_proxy.log
```

---

## Prometheus Metrics Validation

### Test 8.1: Metrics Endpoint Availability

```bash
# Check metrics endpoint
curl -v http://127.0.0.1:9090/metrics

# Expected: 200 OK with Prometheus format

# Check health endpoint
curl -v http://127.0.0.1:9090/health

# Expected: 200 OK with {"status": "healthy"}
```

### Test 8.2: Connection Metrics

```bash
# Query specific metrics
curl -s http://127.0.0.1:9090/metrics | grep "smtp_connections"

# Expected output:
# smtp_connections_total{account="account1@gmail.com",result="success"} 1.0
# smtp_connections_active{account="account1@gmail.com"} 0
```

### Test 8.3: Authentication Metrics

```bash
# Check AUTH metrics
curl -s http://127.0.0.1:9090/metrics | grep "auth_"

# Expected:
# auth_attempts_total{account="account1@gmail.com",result="success"} X
# auth_duration_seconds_sum{account="account1@gmail.com"} Y
# auth_duration_seconds_count{account="account1@gmail.com"} Z
```

### Test 8.4: Message Metrics

```bash
# Check message metrics
curl -s http://127.0.0.1:9090/metrics | grep "messages_total\|messages_duration"

# Expected:
# messages_total{account="account1@gmail.com",result="success"} X
# messages_duration_seconds_sum{account="account1@gmail.com"} Y
```

### Test 8.5: Token Refresh Metrics

```bash
# Check token refresh metrics
curl -s http://127.0.0.1:9090/metrics | grep "token_refresh"

# Expected:
# token_refresh_total{account="account1@gmail.com",result="success"} X
# token_refresh_duration_seconds_sum{account="account1@gmail.com"} Y
# token_age_seconds{account="account1@gmail.com"} Z (seconds since token was issued)
```

### Test 8.6: Upstream XOAUTH2 Metrics

```bash
# Check upstream auth metrics
curl -s http://127.0.0.1:9090/metrics | grep "upstream_auth"

# Expected:
# upstream_auth_total{account="account1@gmail.com",result="success"} X
# upstream_auth_duration_seconds_sum{account="account1@gmail.com"} Y
```

### Test 8.7: Export Metrics for Prometheus

```bash
# Collect metrics for Prometheus scraping
curl -s http://127.0.0.1:9090/metrics > /tmp/metrics_$(date +%s).txt

# Parse specific metric
grep "smtp_connections_total" /tmp/metrics_*.txt

# Create Prometheus scrape job:
cat >> /etc/prometheus/prometheus.yml << 'EOF'
  - job_name: 'xoauth2-proxy'
    static_configs:
      - targets: ['127.0.0.1:9090']
    scrape_interval: 15s
EOF
```

---

## Logging & Troubleshooting

### Log Locations

```bash
# XOAUTH2 Proxy logs
/var/log/xoauth2_proxy.log

# PMTA logs
/var/log/pmta/pmta.log

# PMTA bounce logs
/var/log/pmta/bounces.log

# PMTA failure logs
/var/log/pmta/failures.log

# System logs
/var/log/syslog
journalctl -u pmta -f
journalctl -u xoauth2-proxy -f
```

### Test Log Analysis

```bash
# Extract AUTH attempts
grep "AUTH attempt\|AUTH successful\|AUTH failed" /var/log/xoauth2_proxy.log

# Extract token operations
grep -i "token\|refresh\|expire" /var/log/xoauth2_proxy.log

# Extract message flow
grep -E "Connection made|MAIL FROM|RCPT TO|DATA" /var/log/xoauth2_proxy.log

# Extract errors
grep -i "error\|exception\|traceback" /var/log/xoauth2_proxy.log

# Count events
echo "=== Connection Summary ==="
grep "Connection made" /var/log/xoauth2_proxy.log | wc -l

echo "=== AUTH Summary ==="
grep "AUTH successful" /var/log/xoauth2_proxy.log | wc -l
grep "AUTH failed" /var/log/xoauth2_proxy.log | wc -l

echo "=== Message Summary ==="
grep "messages_total" /var/log/xoauth2_proxy.log | wc -l
```

### Dry-Run Mode Testing

```bash
# Start proxy in dry-run mode
python3 xoauth2_proxy.py \
  --config /etc/xoauth2/accounts.json \
  --dry-run \
  --host 127.0.0.1 \
  --port 2525 \
  --metrics-port 9090

# Send test message
swaks \
  --server 127.0.0.1:2525 \
  --auth-user account1@gmail.com \
  --auth-password placeholder \
  --auth-method PLAIN \
  --from "test@example.com" \
  --to "recipient@gmail.com" \
  --h-Subject "Dry-Run Test" \
  --body "This should NOT be sent upstream"

# Check logs for dry-run message
grep "DRY-RUN\|Would send" /var/log/xoauth2_proxy.log

# Check metrics
curl -s http://127.0.0.1:9090/metrics | grep "dry_run_messages"
```

---

## Common Issues & Solutions

### Issue 1: Proxy Connection Refused

```
Error: Connection refused
```

**Diagnosis:**
```bash
# Check if proxy is running
ps aux | grep xoauth2_proxy

# Check listening ports
netstat -tlnp | grep 2525

# Check firewall
sudo ufw status
sudo iptables -L -n | grep 2525
```

**Solution:**
```bash
# Start proxy
python3 xoauth2_proxy.py --config /etc/xoauth2/accounts.json &

# Or systemd service
sudo systemctl start xoauth2-proxy
sudo systemctl status xoauth2-proxy
```

### Issue 2: AUTH Fails with "not found"

```
535 authentication failed: account X not found
```

**Diagnosis:**
```bash
# Check accounts.json
cat /etc/xoauth2/accounts.json | jq '.accounts[].email'

# Verify email matches exactly
grep "account1@gmail.com" /etc/xoauth2/accounts.json
```

**Solution:**
```bash
# Ensure email is in accounts.json
# Reload proxy
kill -HUP <proxy-pid>

# Or restart
python3 xoauth2_proxy.py --config /etc/xoauth2/accounts.json --reload
```

### Issue 3: PMTA Can't Connect to Proxy

```
Permanent failure for recipient <X>: 451 Temporary authentication failure
```

**Diagnosis:**
```bash
# Check PMTA route config
sudo pmta show route user1-gmail

# Test connectivity from PMTA host
telnet 127.0.0.1 2525

# Check PMTA logs
tail -50 /var/log/pmta/pmta.log
```

**Solution:**
```bash
# Verify proxy is listening
netstat -tlnp | grep 2525

# Check firewall between PMTA and proxy
sudo iptables -L -n | grep 2525

# Increase PMTA debug logging
sudo pmta show log-level
```

### Issue 4: Token Refresh Fails

```
token refresh failed
```

**Diagnosis:**
```bash
# Check accounts.json for valid tokens
cat /etc/xoauth2/accounts.json | jq '.accounts[0]'

# Check token age
curl -s http://127.0.0.1:9090/metrics | grep "token_age_seconds"

# Check OAuth endpoint
echo | openssl s_client -connect smtp.gmail.com:587
```

**Solution:**
```bash
# Regenerate OAuth tokens for account
# Use Google OAuth 2.0 Playground
# https://developers.google.com/oauthplayground

# Update accounts.json with new refresh_token
# Kill -HUP proxy to reload

kill -HUP <proxy-pid>
```

### Issue 5: Messages Queue But Don't Send

```
Messages stuck in PMTA queue
```

**Diagnosis:**
```bash
# Check queue
sudo pmta show queue

# Check if route is active
sudo pmta show route user1-gmail

# Check connection stats
sudo pmta show connections

# Check delivery attempts
grep "delivery attempt" /var/log/pmta/pmta.log | tail -20
```

**Solution:**
```bash
# Clear and retry queue
sudo pmta delete queue

# Check PMTA logs for specific error
grep -i "error\|failed" /var/log/pmta/pmta.log | tail -50

# Verify proxy is responding
echo "EHLO test" | nc -w 5 127.0.0.1 2525
```

---

## Post-Delivery Verification

### Verify Message Delivery

```bash
# Send test message with tracking
TEST_ID="msg_$(date +%s)"

swaks \
  --server 127.0.0.1:25 \
  --auth-user account1@gmail.com \
  --auth-password placeholder \
  --auth-method PLAIN \
  --from "sender@example.com" \
  --to "recipient@gmail.com" \
  --h-Subject "Test Message [$TEST_ID]" \
  --body "Message ID: $TEST_ID

Please confirm receipt."

# Check PMTA delivery logs
grep "$TEST_ID" /var/log/pmta/pmta.log

# Check bounce logs (if delivery failed)
grep "$TEST_ID" /var/log/pmta/bounces.log
```

### Verify Email Headers

```bash
# Request message headers from recipient
# In Gmail: Show original

# Key headers to verify:
# - From: sender@example.com
# - Received: from proxy (127.0.0.1)
# - Received: from pmta
# - Authentication-Results: dkim=pass
# - DKIM-Signature: present
# - Return-Path: <sender@example.com>
```

---

## Prometheus Alerting Rules

```yaml
# /etc/prometheus/rules/xoauth2_proxy.yml

groups:
  - name: xoauth2_proxy
    rules:
      - alert: ProxyHighErrorRate
        expr: rate(errors_total[5m]) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate on {{ $labels.account }}"

      - alert: TokenRefreshFailure
        expr: rate(token_refresh_total{result="failure"}[5m]) > 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Token refresh failing for {{ $labels.account }}"

      - alert: ConcurrencyLimitExceeded
        expr: concurrent_limit_exceeded > 0
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Concurrency limit exceeded for {{ $labels.account }}"

      - alert: ProxyDown
        expr: up{job="xoauth2-proxy"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "XOAUTH2 proxy is down"
```

---

## Success Criteria

Test is successful when:

✅ All 20 accounts authenticate successfully
✅ All 20 routes receive and queue messages
✅ Messages use correct VMTA (IP) for each account
✅ SPF/DKIM validation passes
✅ Prometheus metrics are collected and exported
✅ Logs show successful auth, token refresh, and delivery
✅ Concurrency limits are enforced
✅ Dry-run mode accepts but doesn't send messages
✅ SIGHUP reload works without dropping connections
✅ Health endpoint returns 200 OK

---

## Test Summary Template

```
Test Run: _______________________
Date: _________________________
Tester: _______________________

PASSED TESTS:
- [ ] Proxy connectivity
- [ ] AUTH PLAIN successful
- [ ] AUTH with invalid account
- [ ] All 20 routes functional
- [ ] VMTA IP binding correct
- [ ] Messages delivered end-to-end
- [ ] SPF/DKIM validation passes
- [ ] Prometheus metrics exported
- [ ] Concurrency limits enforced
- [ ] Token refresh working
- [ ] Dry-run mode functional
- [ ] SIGHUP reload working

FAILED TESTS:
(list any failures)

NOTES:
_________________________________
_________________________________
_________________________________
```

---

**End of Test Plan**
