# Quick Test Reference

**TL;DR - How to test the proxy performance in 5 minutes**

---

## Setup (One-time)

```bash
# 1. Make sure you have test accounts configured
cat accounts.json
# Should show at least one account with valid OAuth2 credentials

# 2. Verify dependencies
pip install aiosmtplib
```

---

## Quick Test (2 minutes)

**Terminal 1 - Start Proxy**:
```bash
python xoauth2_proxy_v2.py --config accounts.json --port 2525
```

**Terminal 2 - Verify Proxy is Running**:
```bash
curl http://127.0.0.1:9090/health
# Expected: {"status": "healthy", "service": "xoauth2-proxy-admin"}
```

**Terminal 3 - Run Quick Load Test**:
```bash
python test_smtp_load.py --num-emails 100 --concurrent 10
```

**Result**: You'll see throughput in requests/sec (expected 10-20 req/s)

---

## Test Different Scenarios

**Quick Test (2 min)**:
```bash
python test_smtp_scenarios.py --scenario quick
```

**Baseline Before Optimizations (10 min)**:
```bash
python test_smtp_scenarios.py --scenario baseline
```

**Heavy Stress Test (30 min)**:
```bash
python test_smtp_scenarios.py --scenario stress --verbose
```

**Before/After Comparison**:
```bash
python test_smtp_scenarios.py --scenario compare
```

---

## Key Metrics to Watch

| Metric | Meaning | Good Value |
|--------|---------|-----------|
| `Throughput` | Emails per second | 20-100+ req/s |
| `Per minute` | Emails per minute | 1200+ req/min |
| `Success rate` | % successful | 100% |
| `P95 Latency` | 95th percentile latency | < 0.5 seconds |
| `Average latency` | Mean latency per email | 0.3-0.8s |

---

## Example Output

```
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
```

---

## Common Issues & Fixes

**Connection Refused**:
```bash
# Check if proxy is running
curl http://127.0.0.1:9090/health
# If not, start it
```

**All Requests Failed**:
```bash
# Check configured accounts
curl http://127.0.0.1:9090/admin/accounts

# Make sure from_email is configured
python test_smtp_load.py --from <configured-email> --num-emails 10
```

**Expected Throughput Not Achieved**:
```bash
# Increase concurrent connections
python test_smtp_load.py --num-emails 1000 --concurrent 50

# Check proxy logs for errors
tail -f /var/log/xoauth2/xoauth2_proxy.log
```

---

## Before/After Optimization Comparison

**Step 1: Baseline Test**
```bash
# Terminal 1: Start proxy
python xoauth2_proxy_v2.py --config accounts.json --port 2525

# Terminal 2: Run baseline
python test_smtp_load.py --num-emails 500 --concurrent 25 | tee baseline.txt

# Note the "Overall:" throughput (e.g., 25 req/s)
```

**Step 2: Apply Optimizations**
- Phase 1 fixes are already in place
- Just verify: `git log --oneline | grep "Phase 1"`

**Step 3: Optimized Test**
```bash
# Restart proxy
# Then run same test again
python test_smtp_load.py --num-emails 500 --concurrent 25 | tee optimized.txt

# Compare the throughput
# Expected: 2-5x improvement (25 req/s → 50-125 req/s)
```

**Step 4: Calculate Improvement**
```bash
# Grep the throughput lines
grep "Overall:" baseline.txt optimized.txt

# Example:
# baseline.txt:   Overall: 25.0 requests/sec
# optimized.txt:  Overall: 75.0 requests/sec
# Improvement: 3x faster (200%)
```

---

## Full Test Scripts

### Test 1: Quick Validation
```bash
#!/bin/bash
echo "=== QUICK VALIDATION TEST ==="
python test_smtp_load.py --num-emails 100 --concurrent 10
```

### Test 2: Performance Comparison
```bash
#!/bin/bash
echo "=== BASELINE TEST ==="
python test_smtp_load.py --num-emails 500 --concurrent 25 | tee results_before.txt

echo ""
echo "Make optimizations, then continue"
read -p "Press ENTER when ready..."

echo ""
echo "=== OPTIMIZED TEST ==="
python test_smtp_load.py --num-emails 500 --concurrent 25 | tee results_after.txt

echo ""
echo "=== COMPARISON ==="
grep "Overall:" results_before.txt results_after.txt
```

### Test 3: Stress Test
```bash
#!/bin/bash
echo "=== STRESS TEST ==="
python test_smtp_scenarios.py --scenario stress --verbose
```

---

## Understanding Results

### Throughput Interpretation

| Throughput | Performance Level | What it means |
|-----------|------------------|--------------|
| < 10 req/s | Poor | Bottleneck exists, needs investigation |
| 10-30 req/s | Baseline | Normal before optimizations |
| 30-100 req/s | Good | After Phase 1 optimizations |
| 100+ req/s | Excellent | After Phase 2 optimizations |

### Expected Improvement from Phase 1

```
Before Phase 1: 15-30 req/s
After Phase 1:  45-150 req/s  (3-5x faster)

For 100 emails:
  Before: ~6-7 seconds
  After:  ~1-2 seconds
```

---

## Advanced Usage

**Test with Custom Account**:
```bash
python test_smtp_load.py \
    --num-emails 500 \
    --concurrent 25 \
    --from sales@company.com \
    --to test@outlook.com
```

**Test Remote Proxy**:
```bash
python test_smtp_load.py \
    --host 192.168.1.100 \
    --port 2525 \
    --num-emails 1000 \
    --concurrent 50
```

**Run Multiple Tests**:
```bash
for i in 1 2 3; do
    echo "Test run $i"
    python test_smtp_load.py --num-emails 100 --concurrent 10
    sleep 10
done
```

---

## Next Steps

1. **Run baseline test** → Document throughput
2. **Verify Phase 1 fixes** → Already applied (`git log`)
3. **Restart proxy** → New process with optimizations
4. **Run optimized test** → Compare results
5. **Calculate improvement** → Should see 2-5x faster
6. **Move to Phase 2** → If needed for even more performance

---

## Useful Commands

```bash
# Check if proxy is running
curl http://127.0.0.1:9090/health

# List configured accounts
curl http://127.0.0.1:9090/admin/accounts

# Monitor proxy logs in real-time
tail -f /var/log/xoauth2/xoauth2_proxy.log

# Watch system resources during test
watch -n 1 'ps aux | grep python | grep xoauth2'

# Kill proxy if needed
pkill -f "xoauth2_proxy"

# Find load test result files
ls -lh load_test_results_*.json
```

---

## Summary

**Quick Start**:
```bash
# Terminal 1
python xoauth2_proxy_v2.py --config accounts.json --port 2525

# Terminal 2
python test_smtp_load.py --num-emails 100 --concurrent 10
```

**That's it!** You'll see:
- Total requests
- Success rate
- Throughput (requests/sec and per minute)
- Latency distribution

**For comparison tests**:
```bash
python test_smtp_scenarios.py --scenario compare
```

This will guide you through a before/after test and show the improvement percentage.
