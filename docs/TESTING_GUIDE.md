# 🧪 XOAUTH2 Proxy - Load Testing Guide

This guide shows you how to test the proxy performance and validate the **50,000+ messages per minute** target.

---

## 📋 Prerequisites

1. **Proxy running**:
   ```bash
   python xoauth2_proxy_v2.py --config accounts.json --host 0.0.0.0 --port 2525
   ```

2. **Dependencies installed**:
   ```bash
   pip install requests aiosmtplib
   ```

3. **Account configured** in `accounts.json` with valid OAuth2 credentials

---

## 🎯 Testing Strategies

### **Option 1: Quick Functionality Test** (Recommended First)

Test that the proxy works with a single email:

```bash
python test_single_email.py
```

**What it does**:
- Sends 1 test email through the proxy
- Verifies authentication works
- Confirms message delivery

**Expected output**:
```
✓ Connected to proxy
✓ Authentication successful
✓ Email sent successfully in 0.45 seconds
✓ Connection closed
✓ TEST PASSED - Proxy is working correctly!
```

---

### **Option 2: Gradual Load Test** (Recommended for Validation)

Start with low rates and gradually increase:

#### **Step 1: 1,000 messages/minute** (warm-up)
```bash
python load_test.py --rate 1000 --duration 60
```

#### **Step 2: 10,000 messages/minute**
```bash
python load_test.py --rate 10000 --duration 60
```

#### **Step 3: 25,000 messages/minute**
```bash
python load_test.py --rate 25000 --duration 60
```

#### **Step 4: 50,000 messages/minute** (TARGET)
```bash
python load_test.py --rate 50000 --duration 60
```

**Expected output**:
```
Starting load test: 50000 msg/min for 60 seconds
Target: 833.3 msg/sec

[10s] Sent: 8330, Errors: 0, Rate: 49980 msg/min
[20s] Sent: 16660, Errors: 0, Rate: 49980 msg/min
...

======================================================================
LOAD TEST RESULTS
======================================================================

Duration:        60.1 seconds
Total Sent:      50000
Total Errors:    0
Success Rate:    100.0%

Actual Rate:     49900 messages/minute
                 831.7 messages/second

Latency Statistics:
  Min:           15.2 ms
  Max:           120.5 ms
  Mean:          35.4 ms
  Median:        32.1 ms
  P95:           58.3 ms
  P99:           85.7 ms

======================================================================
✓ EXCELLENT: Target of 50k+ msg/min ACHIEVED!
======================================================================
```

---

### **Option 3: Ramp Test** (Stress Test)

Gradually increase from 1k to 50k over time:

```bash
python load_test.py --ramp-start 1000 --ramp-end 50000 --duration 600
```

**What it does**:
- Starts at 1,000 msg/min
- Gradually increases to 50,000 msg/min
- Takes 10 minutes (600 seconds)
- Tests proxy stability under increasing load

---

### **Option 4: Sustained High-Volume Test**

Run at 50k msg/min for extended period:

```bash
# 5 minutes at 50k msg/min
python load_test.py --rate 50000 --duration 300

# 10 minutes at 50k msg/min
python load_test.py --rate 50000 --duration 600
```

**Purpose**: Validate sustained performance and stability

---

## 📊 Real-Time Monitoring

While running load tests, monitor metrics in a separate terminal:

```bash
python monitor_metrics.py
```

**What you'll see**:
```
================================================================================
                         XOAUTH2 PROXY - LIVE METRICS
================================================================================

📨 MESSAGE METRICS
--------------------------------------------------------------------------------
  Total Messages:        125000
  Current Rate:          50100 messages/minute (835.0 msg/sec)
  Concurrent Messages:   150

🔐 AUTHENTICATION METRICS
--------------------------------------------------------------------------------
  Total Auth Attempts:   1000
  Current Auth Rate:     60 auth/minute
  Active Connections:    50
  Total Connections:     1000

🔄 TOKEN METRICS
--------------------------------------------------------------------------------
  Token Refreshes:       5
  Upstream Auth:         1000

⚠️  ERROR METRICS
--------------------------------------------------------------------------------
  Total Errors:          0
  Concurrent Limit Hit:  0

================================================================================
 ✅ EXCELLENT: Target of 50k+ msg/min ACHIEVED!
================================================================================
```

---

## 🎚️ Performance Tuning

### **If you're NOT reaching 50k msg/min:**

#### 1. **Check System Resources**

**Windows** (PowerShell):
```powershell
# Check CPU usage
Get-Counter '\Processor(_Total)\% Processor Time'

# Check memory
Get-Counter '\Memory\Available MBytes'
```

**Linux**:
```bash
# Monitor resources
top
htop
```

#### 2. **Increase Concurrency**

Edit your proxy startup to allow more concurrent connections:

```bash
# Default: 100 global concurrency
python xoauth2_proxy_v2.py --config accounts.json --global-concurrency 200
```

#### 3. **Check Network Bandwidth**

```bash
# Monitor network in real-time (Linux)
iftop
nload

# Windows: Use Task Manager > Performance > Network
```

#### 4. **Review Proxy Logs**

```bash
# Windows
type C:\Users\ADMINI~1\AppData\Local\Temp\2\xoauth2_proxy\xoauth2_proxy.log

# Linux
tail -f /var/log/xoauth2/xoauth2_proxy.log
```

Look for:
- Lock contention warnings
- Timeout errors
- OAuth2 refresh failures

---

## 📈 Understanding Results

### **Latency Targets**

| Metric | Target | Good | Needs Work |
|--------|--------|------|------------|
| P50 (Median) | < 30ms | < 50ms | > 100ms |
| P95 | < 50ms | < 100ms | > 200ms |
| P99 | < 100ms | < 200ms | > 500ms |

### **Throughput Targets**

| Messages/Minute | Status |
|----------------|--------|
| 50,000+ | ✅ **EXCELLENT** - Target achieved! |
| 40,000-50,000 | ✅ **GOOD** - Close to target |
| 25,000-40,000 | ⚠️ **MODERATE** - Needs optimization |
| < 25,000 | ❌ **BELOW TARGET** - Check configuration |

### **Success Rate Targets**

| Success Rate | Status |
|-------------|--------|
| > 99.9% | ✅ **EXCELLENT** |
| 99-99.9% | ✅ **GOOD** |
| 95-99% | ⚠️ **NEEDS WORK** |
| < 95% | ❌ **PROBLEMS** - Check errors |

---

## 🔍 Troubleshooting

### **Problem: Low throughput (< 25k msg/min)**

**Possible causes**:
1. CPU bottleneck - upgrade hardware or reduce other processes
2. Network bottleneck - check bandwidth
3. Lock contention - check logs for warnings
4. Insufficient concurrency - increase `--global-concurrency`

### **Problem: High error rate (> 1%)**

**Possible causes**:
1. OAuth2 token issues - check token refresh in logs
2. Upstream SMTP errors - Gmail/Outlook rate limiting
3. Network timeouts - increase timeout values
4. Account limits exceeded - add more accounts

### **Problem: High latency (P95 > 200ms)**

**Possible causes**:
1. Network latency to Gmail/Outlook
2. Token refresh delays
3. System overload - check CPU/memory
4. Too many concurrent connections - reduce concurrency

---

## 🎪 Production Testing

### **Before Production**

1. ✅ Test single email works
2. ✅ Test at 1k msg/min (baseline)
3. ✅ Test at 10k msg/min
4. ✅ Test at 25k msg/min
5. ✅ Test at 50k msg/min (target)
6. ✅ Sustained test (5-10 minutes at 50k)
7. ✅ Monitor for errors and warnings

### **Production Load Test Plan**

**Week 1**: Start at 10% of target (5k msg/min)
**Week 2**: Increase to 25% (12.5k msg/min)
**Week 3**: Increase to 50% (25k msg/min)
**Week 4**: Increase to 75% (37.5k msg/min)
**Week 5**: Full load (50k msg/min)

**Monitor closely**:
- Error rates
- Latency percentiles
- Resource usage (CPU, memory, network)
- OAuth2 token refresh success rate

---

## 📞 Getting Help

If you encounter issues:

1. **Check logs**: Look for errors or warnings
2. **Monitor metrics**: Use `monitor_metrics.py` to see live stats
3. **Reduce load**: Test at lower rates to isolate issues
4. **Review configuration**: Verify `accounts.json` is correct

---

## 🎯 Quick Reference

| Test Type | Command | Duration | Purpose |
|-----------|---------|----------|---------|
| Single email | `python test_single_email.py` | 1 second | Verify basic functionality |
| Light load | `python load_test.py --rate 1000 --duration 60` | 1 minute | Warm-up test |
| Medium load | `python load_test.py --rate 10000 --duration 60` | 1 minute | Baseline test |
| Heavy load | `python load_test.py --rate 25000 --duration 60` | 1 minute | Pre-target test |
| **TARGET** | `python load_test.py --rate 50000 --duration 60` | 1 minute | **50k msg/min validation** |
| Ramp test | `python load_test.py --ramp-start 1000 --ramp-end 50000 --duration 600` | 10 minutes | Stress test |
| Sustained | `python load_test.py --rate 50000 --duration 300` | 5 minutes | Stability test |
| Monitor | `python monitor_metrics.py` | Continuous | Live metrics |

---

**Good luck with your testing! 🚀**

**Expected Result**: The proxy should easily handle **50,000+ messages per minute** with low latency and minimal errors, thanks to all 15 performance optimizations implemented!
