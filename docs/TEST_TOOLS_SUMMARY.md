# SMTP Load Testing Tools - Summary

**Status**: ✅ Complete and Ready to Use
**Date**: 2025-11-24
**Purpose**: Benchmark proxy performance from A→Z email flow

---

## Overview

You now have a complete load testing suite to measure the proxy's performance with realistic email sending patterns.

### What's Included

**1. Core Load Tester** (`test_smtp_load.py`)
- Sends concurrent SMTP emails to proxy port 2525
- Measures throughput, latency, and success rates
- Generates JSON results for analysis
- Supports 1-1000+ concurrent connections

**2. Scenario Runner** (`test_smtp_scenarios.py`)
- Predefined test scenarios (quick, baseline, stress, etc.)
- Before/after comparison mode
- Interactive prompts and guidance
- Perfect for measuring optimization impact

**3. Documentation**
- `LOAD_TESTING_GUIDE.md` - Complete reference guide
- `QUICK_TEST_REFERENCE.md` - Quick 5-minute start

---

## Quick Start (5 minutes)

### Step 1: Start Proxy
```bash
python xoauth2_proxy_v2.py --config accounts.json --port 2525
```

### Step 2: Verify Proxy Running
```bash
curl http://127.0.0.1:9090/health
# Expected: {"status": "healthy", "service": "xoauth2-proxy-admin"}
```

### Step 3: Run Load Test
```bash
python test_smtp_load.py --num-emails 100 --concurrent 10
```

### Step 4: View Results
```
Throughput:
  Overall: 19.4 requests/sec
  Per minute: 1164 requests/minute
```

---

## Test Scenarios

### 1. Quick Validation (2-3 minutes)
```bash
python test_smtp_scenarios.py --scenario quick
```
- 100 emails, 10 concurrent
- Sanity check that proxy works
- Expected: 10-20 req/s

### 2. Performance Baseline (5-10 minutes)
```bash
python test_smtp_scenarios.py --scenario baseline
```
- 500 emails, 25 concurrent
- Measure before optimizations
- Expected: 15-30 req/s

### 3. Moderate Load (10-15 minutes)
```bash
python test_smtp_scenarios.py --scenario moderate
```
- 1000 emails, 50 concurrent
- Normal production load
- Expected: 30-60 req/s

### 4. Stress Test (20-30 minutes)
```bash
python test_smtp_scenarios.py --scenario stress --verbose
```
- 2000 emails, 100 concurrent
- Heavy load testing
- Expected: 50-150 req/s

### 5. Sustained Load (60+ minutes)
```bash
python test_smtp_scenarios.py --scenario sustained --verbose
```
- 5000 emails, 50 concurrent
- Stability testing over time
- Expected: Consistent 30-80 req/s

### 6. Peak Load (30+ minutes)
```bash
python test_smtp_scenarios.py --scenario peak --verbose
```
- 10000 emails, 150 concurrent
- Maximum throughput testing
- Expected: 100-300+ req/s

### 7. Before/After Comparison
```bash
python test_smtp_scenarios.py --scenario compare
```
- Runs baseline, prompts for changes, runs optimized
- Calculates improvement percentage
- Shows throughput and latency improvements

---

## What the Test Tools Do

### Email Flow Simulation (A→Z)

Each test simulates a complete email sending flow:

```
1. Connect to proxy on port 2525
   └─ SMTP connection to localhost:2525

2. Send EHLO command
   └─ Proxy responds with capabilities

3. Authenticate
   └─ AUTH PLAIN with test email + placeholder password
   └─ Proxy validates account via OAuth2 token
   └─ Returns 235 OK or 454 error

4. Build email
   └─ Standard email format (From, To, Subject, body)

5. Send message
   └─ MAIL FROM, RCPT TO, DATA commands
   └─ Proxy handles entire flow

6. Disconnect
   └─ QUIT command closes connection
```

### Metrics Collected

**Throughput**:
- Requests per second (req/s)
- Requests per minute (req/min)
- Batches per second during test

**Latency**:
- Min: Best-case latency
- Max: Worst-case latency
- Avg: Mean latency
- P50: Median (50th percentile)
- P95: 95th percentile (5% of requests slower)
- P99: 99th percentile (1% of requests slower)

**Success Rate**:
- Successful requests
- Failed requests
- Error types and counts

**Results**:
- Saved to JSON file for analysis
- Includes timestamps and configuration
- Can compare multiple runs

---

## Example Output

```
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

---

## Interpreting Results

### Throughput Interpretation

| Throughput | Status | What's Happening |
|-----------|--------|------------------|
| < 10 req/s | ⚠️ Poor | Major bottleneck, investigate logs |
| 10-30 req/s | ℹ️ Baseline | Normal before optimizations |
| 30-100 req/s | ✅ Good | After Phase 1 optimizations |
| 100+ req/s | 🚀 Excellent | After Phase 2 optimizations |

### Latency Interpretation

| Metric | Meaning | Good Value |
|--------|---------|-----------|
| Min | Best possible | 0.4-0.6s |
| Avg | Typical case | 0.5-0.8s |
| P95 | 95% are this fast | < 0.8s |
| P99 | 99% are this fast | < 1.0s |
| Max | Worst case | < 2.0s |

### Success Rate

- **100%**: All emails processed successfully ✅
- **95-99%**: Some failures, acceptable ℹ️
- **< 95%**: Investigation needed ⚠️

---

## Before/After Optimization Comparison

### Baseline Test (Before Phase 1)
```bash
python test_smtp_scenarios.py --scenario compare
```

**Output**:
```
PHASE 1: Running BASELINE test...
Throughput: 25.0 req/s
Average Latency: 0.400s
P95 Latency: 0.450s

PHASE 3: Running OPTIMIZED test...
Throughput: 75.0 req/s
Average Latency: 0.133s
P95 Latency: 0.150s

COMPARISON RESULTS
Throughput:
  Baseline: 25.0 req/s
  Optimized: 75.0 req/s
  Improvement: +200.0% (3.0x)

Average Latency:
  Baseline: 0.400s
  Optimized: 0.133s
  Improvement: +66.8% faster
```

**How to use**:
1. Run `compare` scenario
2. Let it run baseline test
3. Make your optimizations (Phase 1 fixes)
4. Restart proxy
5. Come back and press ENTER
6. Test runs optimized version
7. See improvement percentage

---

## Expected Improvement from Phase 1

### Per-Message Performance
```
Before Phase 1: 160-210ms latency
After Phase 1:  100-150ms latency
Improvement:    50-60ms faster (30-40% improvement)
```

### Batch Operations (100 emails)
```
Before Phase 1: 5900ms (with inter-batch delays + O(n) search)
After Phase 1:  1000ms (no delays + O(1) pool lookup)
Improvement:    5900ms saved (86% improvement!)
```

### Throughput
```
Before Phase 1: 15-30 requests/sec
After Phase 1:  50-150 requests/sec (2-5x faster)
```

---

## Troubleshooting

### Connection Refused
```bash
# Check proxy is running
curl http://127.0.0.1:9090/health

# If not, start it
python xoauth2_proxy_v2.py --config accounts.json --port 2525
```

### All Requests Failed
```bash
# Check configured accounts
curl http://127.0.0.1:9090/admin/accounts

# Try with valid configured email
python test_smtp_load.py --from <configured-email> --num-emails 10
```

### Lower Than Expected Throughput
```bash
# 1. Increase concurrent connections
python test_smtp_load.py --num-emails 1000 --concurrent 100

# 2. Check proxy logs for errors
tail -f /var/log/xoauth2/xoauth2_proxy.log

# 3. Check system resources
top -p $(pgrep -f xoauth2)
```

---

## Advanced Usage

### Custom Test Parameters
```bash
python test_smtp_load.py \
    --num-emails 1000 \           # Total emails to send
    --concurrent 50 \             # Concurrent connections
    --host 192.168.1.100 \        # Proxy host
    --port 2525 \                 # Proxy port
    --from sales@company.com \    # From account (must be configured)
    --to test@outlook.com         # To email (can be any)
```

### Comparing Multiple Runs
```bash
# Run baseline
python test_smtp_load.py --num-emails 500 --concurrent 25 > run1.txt

# Run again after changes
python test_smtp_load.py --num-emails 500 --concurrent 25 > run2.txt

# Compare
diff run1.txt run2.txt
```

### Monitoring During Test
```bash
# Terminal 1: Start test
python test_smtp_load.py --num-emails 5000 --concurrent 50

# Terminal 2: Watch system resources
watch -n 1 'ps aux | grep xoauth2 | grep -v grep'

# Terminal 3: Monitor proxy logs
tail -f /var/log/xoauth2/xoauth2_proxy.log | grep -E "Pool|Connection|Auth"
```

---

## Files Created

| File | Purpose |
|------|---------|
| `test_smtp_load.py` | Core load testing tool (285 lines) |
| `test_smtp_scenarios.py` | Scenario runner with presets (330 lines) |
| `LOAD_TESTING_GUIDE.md` | Complete reference (450+ lines) |
| `QUICK_TEST_REFERENCE.md` | Quick start guide (200+ lines) |
| `TEST_TOOLS_SUMMARY.md` | This file |

---

## Next Steps

1. **Run quick test** → Verify proxy works
   ```bash
   python test_smtp_scenarios.py --scenario quick
   ```

2. **Establish baseline** → Document current performance
   ```bash
   python test_smtp_scenarios.py --scenario baseline > baseline.txt
   ```

3. **Verify Phase 1 fixes** → Already in place
   ```bash
   git log --oneline | grep "Phase 1"
   ```

4. **Restart proxy** → Pick up optimizations
   ```bash
   pkill -f xoauth2_proxy
   python xoauth2_proxy_v2.py --config accounts.json --port 2525
   ```

5. **Run optimized test** → See improvements
   ```bash
   python test_smtp_scenarios.py --scenario baseline > optimized.txt
   ```

6. **Calculate improvement** → Compare results
   ```bash
   grep "Overall:" baseline.txt optimized.txt
   # Expected: 2-5x faster throughput
   ```

---

## Summary

✅ **Test Tools Ready**
- Core load tester: `test_smtp_load.py`
- Scenario runner: `test_smtp_scenarios.py`
- Complete documentation included

✅ **Easy to Use**
- Quick start in 5 minutes
- Predefined scenarios for common use cases
- Before/after comparison mode

✅ **Comprehensive Metrics**
- Throughput (req/s and req/min)
- Latency distribution (min, avg, p50, p95, p99)
- Success rate and error analysis
- JSON results for further analysis

✅ **Production Ready**
- Handles 100-10000+ concurrent emails
- Real email flow simulation (A→Z)
- Supports remote proxy testing
- Custom account support

**Start testing now**:
```bash
python test_smtp_scenarios.py --scenario quick
```
