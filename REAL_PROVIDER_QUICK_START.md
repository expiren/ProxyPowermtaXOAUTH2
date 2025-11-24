# Real Provider Testing - Quick Start

**Goal**: Test proxy with 5000+ msg/sec against real Gmail/Outlook servers
**Time**: 5 minutes to get started

---

## Two Tools Available

### 1. Direct Provider Test
```bash
python test_provider_throughput.py --from EMAIL --password TOKEN
```
- Connects directly to Gmail/Outlook SMTP
- Real OAuth2 authentication
- Measures real-world performance
- Shows real failures (rate limits, auth errors)

### 2. Ultra-High Throughput Test (5000+ msg/sec)
```bash
python test_ultra_high_throughput.py --num-emails 5000 --concurrent 100
```
- Tests proxy at extreme scale
- 5000-50000+ messages per second
- Stresses connection pools
- Shows peak performance limits

---

## Getting OAuth2 Credentials

### Gmail (Fastest)
1. Go: https://console.cloud.google.com
2. Create OAuth2 credentials (Desktop app)
3. Authorize to get access token
4. Token format: `ya29.a0AfH6SMBz...` (100+ chars)

### Outlook
1. Go: https://portal.azure.com
2. Register application
3. Add Mail.Send permission
4. Authorize to get access token
5. Token format: `EwAoA8l6BAAURNvFLcaAUzrq...` (200+ chars)

---

## Quick Commands

### Test 1: Validate Credentials (10 emails)
```bash
python test_provider_throughput.py \
    --from your-email@gmail.com \
    --password YOUR_ACCESS_TOKEN \
    --num-emails 10 \
    --concurrent 1
```

Expected:
```
Success: 10/10 (100%)
OR
Auth Failed: 10/10 (if token invalid)
```

### Test 2: Normal Load (100 emails, 10 concurrent)
```bash
python test_provider_throughput.py \
    --from your-email@gmail.com \
    --password YOUR_ACCESS_TOKEN \
    --num-emails 100 \
    --concurrent 10
```

Expected:
```
Success: 90-100
Failed: 0-10
Throughput: 20-50 req/sec
Latency: 200-500ms
```

### Test 3: High Load (1000 emails, 50 concurrent)
```bash
python test_provider_throughput.py \
    --from your-email@gmail.com \
    --password YOUR_ACCESS_TOKEN \
    --num-emails 1000 \
    --concurrent 50
```

Expected:
```
Success: 500-900
Failed: 100-500 (rate limits)
Throughput: 20-100 req/sec
Latency: 200-1000ms
```

### Test 4: EXTREME Load (5000 msg/sec)
```bash
python test_ultra_high_throughput.py \
    --num-emails 5000 \
    --concurrent 100 \
    --use-real-provider \
    --from your-email@gmail.com \
    --password YOUR_ACCESS_TOKEN
```

Expected:
```
Throughput: 5000+ msg/sec (proxy mode)
Throughput: 20-100 req/sec (real provider)
Latency under load: 200-2000ms
Provider rate limits kick in
```

---

## What You'll See

### Successful Auth
```
[Batch 1/10] Sent: 10/100 | Success: 10 | Failed: 0 | Throughput: 50.0 req/s
[Batch 2/10] Sent: 20/100 | Success: 20 | Failed: 0 | Throughput: 48.0 req/s
```

### Rate Limited
```
[Batch 3/10] Sent: 30/100 | Success: 20 | Failed: 10 | Throughput: 30.0 req/s
[Error Types]:
  "430 4.7.0": 5
  "421 4.7.0": 5
```

### Invalid Credentials
```
[Batch 1/10] Sent: 10/100 | Success: 0 | Failed: 10 | Throughput: 0.0 req/s
[Failure Analysis]:
  Authentication failures: 10
[Error Types]:
  "535 5.7.8": 10  ← Invalid credentials
```

---

## Key Metrics

### Success Rate Interpretation
| Rate | Meaning | Action |
|------|---------|--------|
| 100% | Working perfectly | ✓ Good |
| 90-99% | Minor issues | ✓ Normal |
| 50-90% | Rate limited | ⚠️ Reduce load |
| <50% | Major issues | ❌ Check credentials |
| 0% | Failed | ❌ Invalid token |

### Throughput Expected
| Test | Proxy | Provider |
|------|-------|----------|
| 100 emails | 50-150 | 20-50 |
| 1000 emails | 50-150 | 20-100 |
| 5000 emails | 500-1000+ | 20-100 |

### Latency Expected
| Test | Minimum | Average | P95 |
|------|---------|---------|-----|
| Light | 50ms | 100ms | 150ms |
| Moderate | 100ms | 200-300ms | 500ms |
| Heavy | 200ms | 500-1000ms | 1000-2000ms |
| Provider | 200ms | 200-500ms | 500-1000ms |

---

## Common Errors

### "535 5.7.8 Username and password not accepted"
- Invalid credentials
- **Fix**: Verify access token is correct
- Get fresh token from OAuth2 flow

### "430 4.7.0 Temporary service unavailable"
- Gmail rate limit
- **Fix**: Reduce concurrent connections
- Wait before retrying

### "421 4.7.0 Service not available"
- Outlook rate limit
- **Fix**: Reduce concurrent connections
- Use different account

### "Connection timeout"
- Network issue
- **Fix**: Check firewall
- Verify provider host reachable

---

## Workflow

### Step 1: Get Credentials
Get real OAuth2 access token from Gmail or Outlook (5 min)

### Step 2: Validate
Test with 10 emails to verify token works (1 min)
```bash
python test_provider_throughput.py --from EMAIL --password TOKEN --num-emails 10 --concurrent 1
```

### Step 3: Test Normal Load
Send 100 emails to measure baseline (2 min)
```bash
python test_provider_throughput.py --from EMAIL --password TOKEN --num-emails 100 --concurrent 10
```

### Step 4: Test High Load
Send 1000 emails to find limits (5 min)
```bash
python test_provider_throughput.py --from EMAIL --password TOKEN --num-emails 1000 --concurrent 50
```

### Step 5: Test Extreme Load
Test 5000 msg/sec (10 min)
```bash
python test_ultra_high_throughput.py --num-emails 5000 --concurrent 100 --use-real-provider --from EMAIL --password TOKEN
```

---

## Files

| File | Purpose |
|------|---------|
| test_provider_throughput.py | Direct provider testing |
| test_ultra_high_throughput.py | 5000+ msg/sec testing |
| REAL_PROVIDER_TESTING.md | Complete guide (800+ lines) |
| REAL_PROVIDER_QUICK_START.md | This quick start |

---

## Next Steps

1. **Get Access Token** (Gmail or Outlook OAuth2)
2. **Run Quick Test**: `python test_provider_throughput.py --from EMAIL --password TOKEN`
3. **Check Results**: Look for Success Rate
4. **Test Higher Load**: Increase --num-emails and --concurrent
5. **Read REAL_PROVIDER_TESTING.md** for detailed info

---

## Summary

**Two Tools for 5000+ msg/sec Testing**:

1. **test_provider_throughput.py**
   - Real provider connections
   - Real OAuth2 auth
   - Realistic metrics

2. **test_ultra_high_throughput.py**
   - 5000-50000+ msg/sec
   - Extreme stress testing
   - Peak performance

**Just need**: Real OAuth2 access token

**Takes**: 5 minutes to get started

**Result**: Real-world performance data with actual provider failures and rate limits!
