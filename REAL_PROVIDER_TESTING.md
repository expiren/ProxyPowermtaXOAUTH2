# Real Provider Testing Guide

**Purpose**: Test the proxy with REAL OAuth2 credentials and provider endpoints
**Date**: November 24, 2025
**Tools**: test_provider_throughput.py + test_ultra_high_throughput.py

---

## Overview

This guide explains how to test the proxy against **real Gmail/Outlook SMTP servers** with **real OAuth2 tokens**.

### What's Different from Mock Tokens

| Aspect | Mock Tokens | Real Provider |
|--------|------------|---------------|
| Credentials | Pre-cached, no setup | Your real Gmail/Outlook account |
| Token Refresh | Simulated | Real OAuth2 API calls |
| Provider Connection | Fake | Real SMTP servers |
| Failures | None | Real auth/connection failures |
| Performance | Predictable | Real-world metrics |
| Test Type | Unit test | Integration test |

---

## Getting Real OAuth2 Credentials

### For Gmail

1. **Go to Google Cloud Console**
   ```
   https://console.cloud.google.com
   ```

2. **Create OAuth2 Credentials**
   - Create new project
   - Enable Gmail API
   - Create OAuth2 credentials (Desktop app)
   - Download credentials.json

3. **Get Access Token**
   - Use Google OAuth2 flow
   - Get refresh token
   - Use refresh token to get access token

4. **Access Token Format**
   ```
   ya29.a0AfH6SMBz1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOP...
   ```

### For Outlook

1. **Go to Azure Portal**
   ```
   https://portal.azure.com
   ```

2. **Register Application**
   - Create new application registration
   - Add API permissions (Mail.Send, Mail.ReadWrite)
   - Create client secret

3. **Get Access Token**
   - Use OAuth2 flow
   - Get refresh token
   - Use to get access token

4. **Access Token Format**
   ```
   EwAoA8l6BAAURNvFLcaAUzrq1234567890zyxwvutsrqponmlkjihgfedcbaZYXWVUTSRQPONMLKJIH...
   ```

---

## Test 1: Direct Provider Connection

**Tool**: `test_provider_throughput.py`

This test connects DIRECTLY to Gmail/Outlook SMTP servers and measures:
- Real OAuth2 token refresh
- Real SMTP protocol latency
- Real authentication failures
- Real-world performance

### Quick Start

```bash
# Gmail with real credentials
python test_provider_throughput.py \
    --from your-email@gmail.com \
    --password YOUR_ACCESS_TOKEN \
    --num-emails 1000 \
    --concurrent 50

# Outlook
python test_provider_throughput.py \
    --from your-email@outlook.com \
    --password YOUR_ACCESS_TOKEN \
    --num-emails 1000 \
    --concurrent 50
```

### What Happens

1. **Connects to provider SMTP**
   ```
   smtp.gmail.com:587 (for Gmail)
   smtp.office365.com:587 (for Outlook)
   ```

2. **Real authentication**
   - EHLO
   - STARTTLS
   - LOGIN with access token
   - Real OAuth2 validation

3. **Sends real messages** (or fails authentically)

4. **Measures real performance**

### Expected Results

**With Valid Credentials**:
```
Success Rate: 95-100%
Throughput: 20-100 req/s (depends on provider rate limits)
Latency: 200-500ms per message
```

**With Invalid Credentials**:
```
Success Rate: 0%
Auth Failed: 100%
Error: "535 5.7.8 Username and password not accepted"
```

### Common Commands

```bash
# Basic test (100 emails)
python test_provider_throughput.py --from email@gmail.com --password TOKEN

# High volume (1000 emails, 50 concurrent)
python test_provider_throughput.py \
    --from email@gmail.com \
    --password TOKEN \
    --num-emails 1000 \
    --concurrent 50

# Stress test (5000 emails, 100 concurrent)
python test_provider_throughput.py \
    --from email@gmail.com \
    --password TOKEN \
    --num-emails 5000 \
    --concurrent 100 \
    --verbose

# Outlook
python test_provider_throughput.py \
    --from email@outlook.com \
    --password TOKEN \
    --num-emails 1000 \
    --concurrent 50 \
    --provider outlook
```

---

## Test 2: Ultra-High Throughput (5000+ msg/sec)

**Tool**: `test_ultra_high_throughput.py`

This test pushes the proxy/provider to maximum throughput:
- 5000-50000+ messages per second
- Extreme concurrency
- Stress testing
- Peak performance measurement

### Quick Start

```bash
# 5000 msg/sec (proxy test)
python test_ultra_high_throughput.py --num-emails 5000 --concurrent 100

# 5000 msg/sec (real provider)
python test_ultra_high_throughput.py \
    --num-emails 5000 \
    --concurrent 100 \
    --use-real-provider \
    --from email@gmail.com \
    --password TOKEN

# 10000 msg/sec (extreme)
python test_ultra_high_throughput.py \
    --num-emails 10000 \
    --concurrent 200 \
    --use-real-provider \
    --from email@gmail.com \
    --password TOKEN

# 50000 msg/sec (max stress)
python test_ultra_high_throughput.py \
    --num-emails 50000 \
    --concurrent 500 \
    --verbose
```

### What Gets Tested

1. **Connection Pool Limits**
   - How many concurrent connections?
   - Connection reuse efficiency
   - Connection exhaustion behavior

2. **Message Queue**
   - How fast can messages be queued?
   - Queue backpressure handling
   - Memory usage under load

3. **Latency Distribution**
   - How does latency increase with load?
   - P95/P99 latencies at peak
   - Tail latency characteristics

4. **Failure Modes**
   - What fails first?
   - How does proxy handle overload?
   - Error rate escalation

### Expected Results

**Proxy Mode (5000 msg/sec)**:
```
Throughput: 500-1000+ req/sec (depends on phase 1 fixes)
Latency: 50-100ms average
P95 Latency: 100-200ms
Success Rate: 95-100% (with mock tokens)
```

**Real Provider Mode (5000 msg/sec)**:
```
Throughput: 20-100 req/sec (limited by provider)
Latency: 200-500ms average
P95 Latency: 500-1000ms
Success Rate: 50-80% (real-world issues)
```

---

## Comparing Tests

### Mock Token Test (Fast, Reliable)
```bash
python test_smtp_scenarios.py --scenario quick --use-mock-tokens
```
- ✓ No credentials needed
- ✓ 100% success
- ✓ Fast (50-150 req/s)
- ✗ Not realistic
- ✗ No provider connection

### Direct Provider Test (Real, Complete)
```bash
python test_provider_throughput.py --from email@gmail.com --password TOKEN
```
- ✓ Real credentials
- ✓ Real provider connection
- ✓ Real OAuth2 refresh
- ✓ Real failure modes
- ✗ Requires setup
- ✗ Rate limited by provider

### Ultra-High Throughput Test (Stress, Extremes)
```bash
python test_ultra_high_throughput.py --num-emails 5000 --concurrent 100
```
- ✓ Measures peak performance
- ✓ Tests connection limits
- ✓ Shows failure modes
- ✗ Pushes to extremes
- ✗ May trigger provider limits

---

## Handling Provider Failures

### Gmail Rate Limits
- Default: ~500 auth attempts/minute
- If exceeded: 430 4.7.0 "Temporary service unavailable"

### Outlook Rate Limits
- Default: ~60 auth attempts/minute
- If exceeded: 421 4.7.0 "Service not available"

### How Tests Handle Failures

```python
# Graceful failure handling
try:
    await smtp.login(email, password)
except Exception as e:
    # Track error
    stats['auth_failed'] += 1
    # Continue with next email
    continue
```

### Interpreting Error Rates

| Success Rate | Meaning | Action |
|-------------|---------|--------|
| 100% | Working perfectly | ✓ Success |
| 95-99% | Normal operation | ✓ Good |
| 90-95% | Some issues | ⚠️ Check logs |
| 50-90% | Rate limited | ⚠️ Slow down |
| <50% | Major issues | ❌ Check credentials |
| 0% | Complete failure | ❌ Invalid credentials |

---

## Real World Testing Workflow

### Step 1: Validate Credentials
```bash
# Test with small batch
python test_provider_throughput.py \
    --from email@gmail.com \
    --password TOKEN \
    --num-emails 10 \
    --concurrent 1
```

Expected: "Success: 10/10" or "AUTH failed" (clear error)

### Step 2: Test Moderate Load
```bash
python test_provider_throughput.py \
    --from email@gmail.com \
    --password TOKEN \
    --num-emails 100 \
    --concurrent 10
```

Expected: 90-100% success, 200-500ms latency

### Step 3: Test High Load
```bash
python test_provider_throughput.py \
    --from email@gmail.com \
    --password TOKEN \
    --num-emails 1000 \
    --concurrent 50
```

Expected: 50-90% success (may hit rate limits), 500-1000ms latency

### Step 4: Test Extreme Load
```bash
python test_ultra_high_throughput.py \
    --num-emails 5000 \
    --concurrent 100 \
    --use-real-provider \
    --from email@gmail.com \
    --password TOKEN
```

Expected: Measure limits, see failure modes

---

## Command Reference

### Provider Throughput Test
```bash
# Basic
python test_provider_throughput.py --from EMAIL --password TOKEN

# With options
python test_provider_throughput.py \
    --from EMAIL \
    --password TOKEN \
    --num-emails 1000 \
    --concurrent 50 \
    --provider gmail \
    --verbose

# Outlook
python test_provider_throughput.py \
    --from EMAIL@outlook.com \
    --password TOKEN \
    --provider outlook
```

### Ultra-High Throughput Test
```bash
# Proxy mode (5000 msg/sec)
python test_ultra_high_throughput.py --num-emails 5000 --concurrent 100

# Real provider (5000 msg/sec)
python test_ultra_high_throughput.py \
    --num-emails 5000 \
    --concurrent 100 \
    --use-real-provider \
    --from EMAIL \
    --password TOKEN

# Extreme (50000 msg/sec)
python test_ultra_high_throughput.py \
    --num-emails 50000 \
    --concurrent 500 \
    --verbose
```

---

## Files Created

| File | Purpose | Size |
|------|---------|------|
| test_provider_throughput.py | Direct provider testing | 400+ lines |
| test_ultra_high_throughput.py | Ultra-high throughput | 500+ lines |
| REAL_PROVIDER_TESTING.md | This guide | 800+ lines |

---

## Key Metrics to Watch

### Throughput
```
Proxy (mock tokens): 50-150 req/sec
Provider (real): 20-100 req/sec
Ultra-high: 500-1000+ req/sec
```

### Latency
```
Proxy: 50-100ms
Provider: 200-500ms
Under load: 500-2000ms+
```

### Success Rate
```
Mock tokens: 100%
Real provider: 50-99%
Rate limited: <50%
```

### Error Types
```
AUTH failures: Invalid credentials
Connection failures: Network issues
Send failures: Provider rejections
Timeout failures: Slow responses
```

---

## Troubleshooting

### "AUTH failed: 535 5.7.8"
- Invalid Gmail/Outlook credentials
- **Fix**: Verify access token is correct
- Try with fresh token from OAuth2 flow

### "Connection timeout"
- Network connectivity issue
- **Fix**: Check firewall, proxy settings
- Verify provider host is reachable

### "Service not available"
- Rate limited by provider
- **Fix**: Reduce concurrent connections
- Add delays between attempts
- Use multiple accounts (load balancing)

### "Success rate < 50%"
- Something is seriously wrong
- **Fix**: Check:
  - Credentials are correct
  - Network is stable
  - Provider is not down
  - Not rate limited

---

## Summary

**Two Tools for Real Provider Testing**:

1. **test_provider_throughput.py**
   - Direct provider connections
   - Real OAuth2 validation
   - Realistic performance metrics
   - Good for integration testing

2. **test_ultra_high_throughput.py**
   - Extreme stress testing
   - 5000-50000+ msg/sec
   - Peak performance measurement
   - Tests connection limits

**Next Steps**:
1. Get real OAuth2 credentials
2. Start with small test (10 emails)
3. Gradually increase load
4. Monitor error rates and latency
5. Compare with mock token results

**Remember**: Real provider testing shows actual performance, including all the limitations, rate limits, and failures of real-world systems!
