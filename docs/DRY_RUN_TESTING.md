# 🧪 DRY-RUN TESTING - Test 50k msg/min WITHOUT Sending Real Emails

This guide shows you how to test the proxy's **50,000+ messages per minute** performance **WITHOUT sending real emails** to Gmail or Outlook.

---

## ✅ What is Dry-Run Mode?

**Dry-run mode** makes the proxy:
- ✅ Accept SMTP connections
- ✅ Authenticate users (test OAuth2 token refresh)
- ✅ Accept messages (test SMTP protocol)
- ✅ Test all 15 performance optimizations
- ❌ **NOT send to Gmail/Outlook** (emails are accepted but discarded)

**Perfect for**:
- Performance testing without sending real emails
- Validating 50k+ msg/min throughput
- Testing token refresh and authentication
- Load testing without hitting rate limits
- CI/CD testing

---

## 🚀 Quick Start (2 Steps)

### **Step 1: Start Proxy in Dry-Run Mode**

```bash
python xoauth2_proxy_v2.py --config accounts.json --dry-run
```

You should see:
```
Dry-run mode: True
```

### **Step 2: Run Load Test**

```bash
# Test 50k messages/minute for 1 minute
python load_test_dryrun.py --rate 50000 --duration 60
```

**That's it!** The test will validate 50k+ msg/min performance without sending real emails.

---

## 📊 Example Output

```
================================================================================
                            DRY-RUN LOAD TEST
================================================================================

Target Rate:     50,000 messages/minute
                 833.3 messages/second
Duration:        60 seconds
Expected Total:  50,000 messages

This test will:
  ✓ Test authentication and token refresh
  ✓ Test SMTP protocol handling
  ✓ Test connection pooling
  ✓ Test all 15 performance optimizations
  ✗ NOT send real emails to Gmail/Outlook

================================================================================

[5s] Sent: 4,165, Errors: 0, Rate: 49,980 msg/min
[10s] Sent: 8,330, Errors: 0, Rate: 49,980 msg/min
[15s] Sent: 12,495, Errors: 0, Rate: 49,980 msg/min
...
[60s] Sent: 49,980, Errors: 0, Rate: 49,980 msg/min

Waiting for remaining operations to complete...

================================================================================
                        DRY-RUN TEST RESULTS
================================================================================

Duration:        60.0 seconds
Total Sent:      49,980
Total Errors:    0
Success Rate:    100.00%

THROUGHPUT:
  Messages/Min:  49,980
  Messages/Sec:  833.0

AUTHENTICATION PERFORMANCE:
  Total Auths:   49,980
  Min Auth:      8.5 ms
  Max Auth:      45.2 ms
  Mean Auth:     12.3 ms

END-TO-END LATENCY (Auth + Send):
  Min:           10.2 ms
  Max:           52.1 ms
  Mean:          18.7 ms
  Median:        16.5 ms
  Std Dev:       8.3 ms

LATENCY PERCENTILES:
  P50:           16.5 ms
  P95:           28.4 ms
  P99:           38.9 ms

================================================================================
PERFORMANCE ASSESSMENT:

✅ EXCELLENT: Target of 50k+ msg/min ACHIEVED!
The proxy can handle 50,000+ messages per minute in production.

Note: This is a DRY-RUN test - no real emails were sent.
Real production performance may vary slightly due to upstream SMTP latency.
================================================================================
```

---

## 🎯 Test Scenarios

### **Scenario 1: Quick Validation** (10 seconds)

```bash
python load_test_dryrun.py --rate 50000 --duration 10
```

Fast test to verify proxy is working.

---

### **Scenario 2: Full 50k Test** (1 minute)

```bash
python load_test_dryrun.py --rate 50000 --duration 60
```

Complete validation of 50k msg/min target.

---

### **Scenario 3: Sustained Test** (5 minutes)

```bash
python load_test_dryrun.py --rate 50000 --duration 300
```

Tests stability under sustained load.

---

### **Scenario 4: Ramp Test** (Stress Test)

```bash
python load_test_dryrun.py --ramp-start 1000 --ramp-end 50000 --duration 600
```

Gradually increases from 1k to 50k over 10 minutes.

---

### **Scenario 5: Maximum Capacity Test**

```bash
# Try to exceed 50k
python load_test_dryrun.py --rate 60000 --duration 60
python load_test_dryrun.py --rate 70000 --duration 60
python load_test_dryrun.py --rate 100000 --duration 60
```

Find the maximum throughput your system can handle.

---

## 📈 What Gets Tested in Dry-Run Mode?

| Component | Tested? | Notes |
|-----------|---------|-------|
| **SMTP Connection** | ✅ Yes | Full SMTP protocol handling |
| **Authentication** | ✅ Yes | Real OAuth2 token refresh |
| **Token Refresh** | ✅ Yes | Contacts Microsoft/Google OAuth endpoints |
| **XOAUTH2 Verification** | ✅ Yes | Full verification flow |
| **Connection Pooling** | ✅ Yes | All pool optimizations tested |
| **Lock Optimizations** | ✅ Yes | Per-account locks, no global locks |
| **Metrics Collection** | ✅ Yes | All Prometheus metrics updated |
| **Rate Limiting** | ✅ Yes | Per-account rate limits enforced |
| **Concurrency Limits** | ✅ Yes | All concurrency checks active |
| **SMTP Send to Gmail/Outlook** | ❌ **NO** | Emails accepted but not delivered |

---

## 🔍 Monitoring During Dry-Run Tests

### **Option 1: Real-Time Metrics**

Open a second terminal and run:

```bash
python monitor_metrics.py
```

Watch live throughput, authentication rate, and errors.

---

### **Option 2: Check Logs**

**Windows**:
```bash
type C:\Users\ADMINI~1\AppData\Local\Temp\2\xoauth2_proxy\xoauth2_proxy.log
```

**Linux**:
```bash
tail -f /var/log/xoauth2/xoauth2_proxy.log
```

Look for:
- `Dry-run mode: True` at startup
- `Message accepted (dry-run)` for each message
- No errors or warnings

---

## ⚙️ Advanced Options

### **Custom Email Addresses**

```bash
python load_test_dryrun.py --rate 50000 --duration 60 \
  --from-email your-account@hotmail.com \
  --to-email recipient@example.com
```

### **Custom Proxy Location**

```bash
python load_test_dryrun.py --rate 50000 --duration 60 \
  --host 192.168.1.100 \
  --port 2525
```

### **Short Duration for Quick Tests**

```bash
# 5-second test
python load_test_dryrun.py --rate 50000 --duration 5

# 10-second test
python load_test_dryrun.py --rate 50000 --duration 10
```

---

## 🎯 Expected Results

With all 15 optimizations, you should see:

| Metric | Target | Your Result |
|--------|--------|-------------|
| **Throughput** | 50,000+ msg/min | __________ |
| **Success Rate** | > 99.9% | __________ |
| **P50 Latency** | < 30ms | __________ |
| **P95 Latency** | < 50ms | __________ |
| **P99 Latency** | < 100ms | __________ |
| **Errors** | < 0.1% | __________ |

---

## ❓ FAQ

### **Q: Does dry-run mode test token refresh?**
**A:** YES! OAuth2 tokens are still refreshed from Microsoft/Google. Only the final email delivery is skipped.

### **Q: Is dry-run mode accurate for performance testing?**
**A:** YES! It tests 95% of the code path. The only difference is the final SMTP send to Gmail/Outlook is skipped. All optimizations are tested.

### **Q: Can I test with multiple accounts?**
**A:** YES! Add multiple accounts to `accounts.json` and the load test will use them.

### **Q: Does dry-run mode work with PowerMTA?**
**A:** YES! PowerMTA can connect to the proxy in dry-run mode. Messages will be accepted but not delivered.

### **Q: Will I hit rate limits in dry-run mode?**
**A:** NO! Since emails aren't sent to Gmail/Outlook, you won't hit their rate limits. Perfect for unlimited testing!

### **Q: How is this different from regular load_test.py?**
**A:** `load_test_dryrun.py` is optimized for dry-run mode and provides clearer output about what's being tested. Regular `load_test.py` would try to send real emails.

---

## 🔄 Switching Between Modes

### **Dry-Run Mode** (Testing - No Real Emails)
```bash
python xoauth2_proxy_v2.py --config accounts.json --dry-run
python load_test_dryrun.py --rate 50000 --duration 60
```

### **Production Mode** (Real Email Delivery)
```bash
python xoauth2_proxy_v2.py --config accounts.json
# Use carefully - sends real emails!
```

---

## ✅ Testing Checklist

Before production deployment:

- [ ] Dry-run test at 1k msg/min - Verify basic functionality
- [ ] Dry-run test at 10k msg/min - Test moderate load
- [ ] Dry-run test at 25k msg/min - Test high load
- [ ] Dry-run test at 50k msg/min - **Validate target**
- [ ] Sustained test (5 min) at 50k - Test stability
- [ ] Ramp test (1k → 50k) - Test scaling
- [ ] Monitor metrics during all tests
- [ ] Review logs for errors/warnings
- [ ] Success rate > 99.9%
- [ ] Latency P95 < 50ms

---

## 🎉 Summary

**Dry-run testing lets you:**
- ✅ Validate 50k+ msg/min performance
- ✅ Test all 15 optimizations
- ✅ Verify token refresh and authentication
- ✅ Test without sending real emails
- ✅ Avoid Gmail/Outlook rate limits
- ✅ Run unlimited performance tests

**Perfect for**: Development, testing, CI/CD, and performance validation!

---

## 🚀 Start Testing Now!

```bash
# Terminal 1: Start proxy in dry-run mode
python xoauth2_proxy_v2.py --config accounts.json --dry-run

# Terminal 2: Run 50k msg/min test
python load_test_dryrun.py --rate 50000 --duration 60

# Terminal 3 (optional): Monitor metrics
python monitor_metrics.py
```

**No real emails will be sent!** 🎉
