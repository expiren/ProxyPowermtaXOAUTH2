# SMTP Load Testing Guide

**Purpose**: Benchmark the proxy's performance with realistic email load and measure:
- Requests processed per second
- Requests processed per minute
- Latency distribution (min, max, p50, p95, p99)
- Success/failure rates
- Throughput before and after optimizations

---

## Quick Start

### 1. Start the Proxy

```bash
# Terminal 1: Start the proxy
python xoauth2_proxy_v2.py --config accounts.json --port 2525
```

Make sure:
- ✅ Proxy is listening on port 2525
- ✅ At least one valid account is configured in `accounts.json`
- ✅ Account has valid OAuth2 credentials

**Check proxy is running**:
```bash
curl http://127.0.0.1:9090/health
# Expected: {"status": "healthy", "service": "xoauth2-proxy-admin"}
```

### 2. Run Load Test

```bash
# Terminal 2: Run the load test
python test_smtp_load.py --num-emails 100 --concurrent 10

# Or with custom parameters
python test_smtp_load.py --num-emails 1000 --concurrent 50 --from sales@gmail.com --to recipient@outlook.com
```

---

## Command-Line Options

```
--num-emails INTEGER
    Total number of emails to send
    Default: 100
    Recommended: 100 (quick), 500 (moderate), 1000+ (stress test)

--concurrent INTEGER
    Number of concurrent SMTP connections
    Default: 10
    Recommended: 5-100 depending on test intensity

--host STRING
    Proxy hostname or IP
    Default: 127.0.0.1
    For remote testing: 192.168.1.100 or proxy.example.com

--port INTEGER
    Proxy SMTP port
    Default: 2525
    Must match --port in xoauth2_proxy_v2.py

--from STRING
    From email address (must be configured account)
    Default: test@example.com
    IMPORTANT: Must be an account in accounts.json

--to STRING
    To email address (can be any email)
    Default: recipient@outlook.com
    Can use invalid password - proxy handles OAuth2, not SMTP auth
```

---

## Usage Examples

### Example 1: Quick Baseline Test (5 minutes)
```bash
python test_smtp_load.py --num-emails 100 --concurrent 10
```
- Sends 100 emails with 10 concurrent connections
- Quick test to verify proxy is working
- Expected: 10-20 requests/sec

### Example 2: Moderate Load Test (15 minutes)
```bash
python test_smtp_load.py --num-emails 500 --concurrent 25
```
- Sends 500 emails with 25 concurrent connections
- Good for stability testing
- Expected: 20-50 requests/sec

### Example 3: Stress Test (30+ minutes)
```bash
python test_smtp_load.py --num-emails 2000 --concurrent 100
```
- Sends 2000 emails with 100 concurrent connections
- Heavy load for capacity testing
- Expected: 50-200+ requests/sec (depending on Phase 1 fixes)

### Example 4: Before vs After Optimization
```bash
# Test 1: Before Phase 1 fixes (baseline)
python test_smtp_load.py --num-emails 1000 --concurrent 50 > results_before.txt

# Apply Phase 1 fixes, restart proxy

# Test 2: After Phase 1 fixes
python test_smtp_load.py --num-emails 1000 --concurrent 50 > results_after.txt

# Compare results
# Expected improvement: 2-5x throughput, 50-80% latency reduction
```

### Example 5: Remote Server Test
```bash
# Test against remote proxy server
python test_smtp_load.py \
    --num-emails 1000 \
    --concurrent 50 \
    --host 192.168.1.100 \
    --port 2525 \
    --from sales@company.com \
    --to test@outlook.com
```

---

## Understanding the Output

### Sample Output:
```
================================================================================
SMTP Load Test Starting
================================================================================
Target: 127.0.0.1:2525
Total emails: 100
Concurrent connections: 10
From: test@example.com
To: recipient@outlook.com
================================================================================
Will send in 10 batches of 10

[Batch 1/10] Sent: 10/100 | Success: 10 | Failed: 0 | Batch time: 0.52s | Throughput: 19.2 req/s
[Batch 2/10] Sent: 20/100 | Success: 20 | Failed: 0 | Batch time: 0.48s | Throughput: 20.8 req/s
[Batch 3/10] Sent: 30/100 | Success: 30 | Failed: 0 | Batch time: 0.51s | Throughput: 19.6 req/s
...
================================================================================
LOAD TEST RESULTS
================================================================================
Total time: 5.15 seconds
Total requests: 100
Successful: 100
Failed: 0
Success rate: 100.0%

Throughput:
  Overall: 19.4 requests/sec
  Per minute: 1164 requests/minute

Latency (seconds):
  Min: 0.480s
  Max: 0.620s
  Average: 0.530s
  P50 (median): 0.520s
  P95: 0.600s
  P99: 0.620s

Results saved to: load_test_results_1732382456.json
================================================================================
```

### Key Metrics to Watch:

**Throughput** (requests per second and minute)
- This is the main performance metric
- Should improve with Phase 1 fixes
- More concurrent = higher throughput (up to a limit)

**Success Rate** (% of emails processed)
- Should be 100% for valid accounts
- < 100% indicates proxy or auth issues

**Latency** (time per email)
- Min: Best case scenario
- Max: Worst case (queue delay + processing)
- P50/P95/P99: Distribution (most requests fall here)
- Should decrease with Phase 1 fixes

**Batch Throughput** (req/s per batch)
- Shows if proxy handles sustained load
- Should be consistent batch-to-batch

---

## Expected Results

### Before Phase 1 Fixes (Baseline)
```
Throughput: 10-30 requests/sec
Per minute: 600-1800 requests/minute
P95 Latency: 0.5-2.0 seconds
Issue: Connection pool O(n) search, batch delays
```

### After Phase 1 Fixes (Optimized)
```
Throughput: 50-200+ requests/sec (2-7x improvement)
Per minute: 3000-12000+ requests/minute
P95 Latency: 0.1-0.5 seconds (50-80% reduction)
Improvements: O(1) pool lookup, no batch delays, IP caching
```

### With Phase 1 + Phase 2 (Full Optimization)
```
Throughput: 200+ requests/sec (10x+ improvement)
Per minute: 12000+ requests/minute
P95 Latency: <0.1 seconds
Result: Production-ready for high-volume scenarios
```

---

## Important Notes

### About Email Credentials
- **From email MUST be configured** in `accounts.json`
- **To email can be ANY email** (doesn't need to be real)
- **Password is ignored** - proxy validates via OAuth2 token
- The proxy receives the AUTH command, validates the account, and returns 235 OK

### About Test Accounts
For testing, you need at least one valid account with:
- ✅ Valid Gmail or Outlook account
- ✅ Valid OAuth2 credentials (client_id, refresh_token, etc.)
- ✅ Already added to accounts.json
- ✅ Successfully authorized once

Example accounts.json:
```json
[
  {
    "email": "test@gmail.com",
    "provider": "gmail",
    "client_id": "xxx.apps.googleusercontent.com",
    "client_secret": "xxx",
    "refresh_token": "1//xxx",
    "oauth_endpoint": "smtp.gmail.com:587"
  }
]
```

### About Authentication
The test tool:
1. Connects to proxy on port 2525
2. Sends EHLO command
3. Sends AUTH PLAIN with test email + placeholder password
4. Proxy validates with OAuth2 (ignores password)
5. If account valid: Returns 235 OK
6. If account invalid: Returns 454 error

Even if OAuth2 credentials are wrong, the proxy will attempt token refresh and handle appropriately.

---

## Interpreting Results

### Success Rate < 100%
**Likely causes**:
- Account not found in proxy
- OAuth2 credentials invalid
- Network connectivity issues
- Proxy crashed during test

**Debug steps**:
```bash
# 1. Check proxy logs
tail -f /var/log/xoauth2/xoauth2_proxy.log

# 2. Verify account exists
curl http://127.0.0.1:9090/admin/accounts

# 3. Check proxy health
curl http://127.0.0.1:9090/health

# 4. Test manually
telnet 127.0.0.1 2525
EHLO test
AUTH PLAIN <base64(null + email + null + password)>
```

### High Latency
**Likely causes**:
- Concurrent value too high (thread pool exhaustion)
- OAuth2 provider slow response
- Network latency to proxy
- Phase 1 optimizations not applied

**Debug steps**:
```bash
# 1. Check proxy resource usage
top -p $(pgrep -f "python xoauth2")

# 2. Reduce concurrent to isolate issue
python test_smtp_load.py --num-emails 100 --concurrent 5

# 3. Monitor proxy logs for errors
grep -i "error\|timeout\|exception" /var/log/xoauth2/xoauth2_proxy.log
```

### Throughput Lower Than Expected
**Likely causes**:
- Phase 1 fixes not yet applied
- Connection pool not pre-warmed
- OAuth2 token refresh overhead
- Network bandwidth limitation

**Optimization steps**:
```bash
# 1. Verify Phase 1 fixes are in place
grep -A 5 "PERF FIX #6" src/smtp/connection_pool.py

# 2. Increase concurrent connections
python test_smtp_load.py --num-emails 1000 --concurrent 100

# 3. Pre-warm pool (if available)
# Proxy automatically pre-warms on startup

# 4. Check for rate limiting
grep -i "rate\|limit\|semaphore" /var/log/xoauth2/xoauth2_proxy.log
```

---

## Comparing Before and After Phase 1

**Step 1: Create baseline (before optimizations)**
```bash
# Start proxy (old code)
python xoauth2_proxy_v2.py --config accounts.json --port 2525

# Run test
python test_smtp_load.py --num-emails 500 --concurrent 25 > baseline_results.txt

# Capture metrics
grep -E "Overall|Per minute|Average|P95" baseline_results.txt
```

**Step 2: Apply Phase 1 fixes**
```bash
# Phase 1 fixes are already committed
# Just verify they're in place
git log --oneline | grep "Phase 1"
```

**Step 3: Create optimized results (after Phase 1)**
```bash
# Restart proxy (with Phase 1 fixes)
python xoauth2_proxy_v2.py --config accounts.json --port 2525

# Run same test
python test_smtp_load.py --num-emails 500 --concurrent 25 > optimized_results.txt

# Compare
diff -u baseline_results.txt optimized_results.txt
```

**Expected improvements**:
- Throughput: 2-5x higher
- Latency: 50-80% lower
- Success rate: 100% (same)

---

## Performance Tuning Tips

### 1. Optimal Concurrent Connections
```bash
# Start with default (10)
python test_smtp_load.py --num-emails 100 --concurrent 10

# Increase gradually until throughput peaks
python test_smtp_load.py --num-emails 100 --concurrent 25
python test_smtp_load.py --num-emails 100 --concurrent 50
python test_smtp_load.py --num-emails 100 --concurrent 100

# Sweet spot: Usually 25-50 for most scenarios
# Too high: Causes queueing and latency
# Too low: Doesn't saturate proxy capacity
```

### 2. Test Duration
- Quick test: 100 emails (30 seconds)
- Stability test: 500-1000 emails (2-5 minutes)
- Stress test: 2000+ emails (10+ minutes)
- Watch for performance degradation over time

### 3. Watch System Resources
```bash
# Terminal 3: Monitor proxy CPU/memory
watch -n 1 'ps aux | grep python | grep xoauth2'

# Terminal 4: Monitor network
iftop -i eth0  # Or your network interface
```

### 4. Multiple Accounts
If you have multiple configured accounts:
```bash
# Test each account separately
python test_smtp_load.py --num-emails 100 --from account1@gmail.com --concurrent 10
python test_smtp_load.py --num-emails 100 --from account2@outlook.com --concurrent 10

# Compare per-account performance
```

---

## Troubleshooting

### Connection Refused
```
Error: Connection refused to 127.0.0.1:2525
```
**Solution**:
```bash
# Check if proxy is running
curl http://127.0.0.1:9090/health

# If not, start it
python xoauth2_proxy_v2.py --config accounts.json --port 2525

# Verify port
netstat -an | grep 2525
```

### All Requests Failed
```
Failed: 100
Success rate: 0.0%
```
**Solution**:
```bash
# Check configured accounts
curl http://127.0.0.1:9090/admin/accounts

# Verify from_email matches
python test_smtp_load.py --from <configured-email> --num-emails 10 --concurrent 1

# Check proxy logs for auth errors
tail -f /var/log/xoauth2/xoauth2_proxy.log | grep -i "auth\|error"
```

### High Latency on First Batch Only
```
[Batch 1/10] Throughput: 5.0 req/s  <- Slow
[Batch 2/10] Throughput: 20.0 req/s <- Normal
```
**Solution**:
- This is normal (token refresh on first request)
- Proxy warms up on second batch
- Run test with more batches to get accurate average

### Memory Leak / Increasing Latency
```
[Batch 1/10] Throughput: 20 req/s
[Batch 2/10] Throughput: 19 req/s
[Batch 3/10] Throughput: 18 req/s  <- Degrading
```
**Solution**:
```bash
# Check for connection pool leaks
tail -f /var/log/xoauth2/xoauth2_proxy.log | grep -i "pool\|connection"

# Restart proxy
# Verify connection cleanup happens
```

---

## Sample Test Scenarios

### Scenario 1: Production Load (1000 emails/minute)
```bash
# 1000 emails/min = 16.67 emails/sec
# Use 50 concurrent connections

python test_smtp_load.py --num-emails 1000 --concurrent 50
# Expected: ~20 req/sec = 1200 emails/min ✅
```

### Scenario 2: Peak Load (5000 emails/minute)
```bash
# 5000 emails/min = 83.33 emails/sec
# Use 100 concurrent connections

python test_smtp_load.py --num-emails 5000 --concurrent 100
# Expected: ~80-100 req/sec = 4800-6000 emails/min ✅
```

### Scenario 3: Stability over Time
```bash
# Run continuous test for 1 hour
python test_smtp_load.py --num-emails 10000 --concurrent 50
# Monitor for throughput degradation or latency creep
# Expected: Consistent 20-50 req/sec throughout
```

---

## Saving and Analyzing Results

The test tool automatically saves results to JSON:
```
load_test_results_1732382456.json
```

**Example results file**:
```json
{
  "timestamp": "2025-11-24T10:30:00",
  "target": "127.0.0.1:2525",
  "config": {
    "num_emails": 100,
    "concurrent": 10
  },
  "results": {
    "total_requests": 100,
    "successful": 100,
    "failed": 0,
    "success_rate": 1.0,
    "throughput_rps": 19.4,
    "throughput_rpm": 1164,
    "latency": {
      "min_seconds": 0.48,
      "max_seconds": 0.62,
      "avg_seconds": 0.53,
      "p50_seconds": 0.52,
      "p95_seconds": 0.60,
      "p99_seconds": 0.62
    }
  }
}
```

**Compare multiple tests**:
```bash
# Run multiple tests and save
for i in {1..3}; do
    echo "Test run $i"
    python test_smtp_load.py --num-emails 500 --concurrent 50
    sleep 5
done

# Analyze results
ls -lh load_test_results_*.json
```

---

## Next Steps

After running the load test:

1. **Document baseline** (before Phase 1 optimizations)
2. **Document optimized results** (after Phase 1)
3. **Calculate improvement %**
4. **Adjust concurrent connections** for your workload
5. **Run longer tests** (1+ hour) for stability
6. **Monitor in production** to validate improvements

---

## Summary

The load test tool provides:
- ✅ Realistic email sending simulation (A→Z flow)
- ✅ Concurrent request handling
- ✅ Comprehensive metrics (throughput, latency, success rate)
- ✅ Per-batch throughput tracking
- ✅ Latency distribution (P50, P95, P99)
- ✅ JSON results for analysis
- ✅ Before/after comparison capability

Use it to validate the Phase 1 performance improvements and measure your proxy's maximum throughput!
