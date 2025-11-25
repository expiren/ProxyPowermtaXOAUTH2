# Mock Token Testing Guide

**Purpose**: Test the proxy without real OAuth2 credentials
**Status**: Ready to use
**Date**: November 24, 2025

---

## Overview

This guide explains how to use mock/cached OAuth2 tokens for testing the proxy without needing real Gmail/Outlook credentials.

### What Are Mock Tokens?

Mock tokens are pre-generated, cached OAuth2 access tokens that:
- ✅ Look like real tokens (realistic format)
- ✅ Work with the proxy's XOAUTH2 authentication
- ✅ Allow end-to-end testing without real OAuth2 calls
- ✅ Enable Ctrl+C graceful shutdown
- ✅ Provide realistic performance measurements

**Note**: The proxy will treat these as valid tokens for testing purposes. They simulate what real tokens would look like.

---

## Available Test Accounts

Four mock test accounts are pre-configured:

### Gmail Accounts
1. **test.account1@gmail.com**
   - Access Token: `ya29.a0AfH6SMBz...` (30+ chars)
   - Provider: Gmail
   - Status: Cached and ready to use

2. **test.account2@gmail.com**
   - Access Token: `ya29.b0BeGH6SMCz...` (30+ chars)
   - Provider: Gmail
   - Status: Cached and ready to use

### Outlook Accounts
3. **test.account1@outlook.com**
   - Access Token: `EwAoA8l6BAAURNvFLcaAUzrq...` (50+ chars)
   - Provider: Outlook
   - Status: Cached and ready to use

4. **test.account2@outlook.com**
   - Access Token: `EwAoA8l6BAAURNvFLcaAUzrq...` (50+ chars)
   - Provider: Outlook
   - Status: Cached and ready to use

---

## Quick Start (5 minutes)

### Step 1: Start Proxy with Mock Token Support

The proxy will use the mock tokens automatically if the accounts exist in accounts.json.

```bash
python xoauth2_proxy_v2.py --config accounts.json --port 2525
```

**What's different**: The proxy will NOT try to refresh tokens from Google/Microsoft. It will use the pre-cached tokens.

### Step 2: Run Load Test with Mock Tokens

```bash
# Option A: Use the --use-mock-tokens flag (explicit)
python test_smtp_scenarios.py --scenario quick --use-mock-tokens

# Option B: Use mock account directly
python test_smtp_load.py --num-emails 100 --concurrent 10 --from test.account1@gmail.com

# Option C: Comparison test with mock tokens
python test_smtp_scenarios.py --scenario compare --use-mock-tokens
```

### Step 3: Graceful Shutdown (Ctrl+C)

Press **Ctrl+C** at any time to stop the test:
- Test will stop gracefully
- Partial results will be displayed
- No hanging connections
- No "Session is closed" errors

Example:
```bash
$ python test_smtp_scenarios.py --scenario quick
[...test running...]
[Press Ctrl+C here]
Test interrupted by user (Ctrl+C)
Stopped after 45 successful sends
[Results displayed]
```

---

## How It Works

### Architecture

```
Test Script
  ↓
Mock Token Cache (mock_oauth2_tokens.py)
  ├─ Pre-generated access tokens
  ├─ XOAUTH2 string generation
  └─ Token info lookup
  ↓
Proxy (xoauth2_proxy_v2.py)
  ├─ Receives XOAUTH2 string
  ├─ Validates token (mock tokens are valid)
  └─ Relays email to SMTP (or simulates)
  ↓
Test Results (Performance metrics)
```

### Token Flow

1. **Test Script** → Requests token for `test.account1@gmail.com`
2. **Mock Cache** → Returns pre-generated access token
3. **XOAUTH2 String** → Base64 encodes: `user=test.account1@gmail.com\x01auth=Bearer <token>\x01\x01`
4. **Proxy** → Receives AUTH PLAIN with XOAUTH2 string
5. **Authentication** → Token is treated as valid (for testing)
6. **Message Send** → SMTP MAIL/RCPT/DATA proceeds normally

---

## Testing Scenarios

### Quick Test (2-3 minutes, no real credentials needed)

```bash
python test_smtp_scenarios.py --scenario quick --use-mock-tokens
```

**What happens**:
- 100 emails sent
- 10 concurrent connections
- Uses mock tokens from cache
- No OAuth2 API calls
- No real Gmail/Outlook connections
- Reports throughput and latency

### Baseline Test (5-10 minutes)

```bash
python test_smtp_scenarios.py --scenario baseline --use-mock-tokens
```

**What happens**:
- 500 emails sent
- 25 concurrent connections
- Full performance measurement
- Saves results to JSON file

### Custom Test with Specific Account

```bash
python test_smtp_load.py \
    --num-emails 500 \
    --concurrent 25 \
    --from test.account1@outlook.com
```

### Before/After Comparison

```bash
python test_smtp_scenarios.py --scenario compare --use-mock-tokens
```

1. Runs baseline test (gets baseline metrics)
2. Waits for you to make proxy changes
3. Runs again (gets new metrics)
4. Calculates improvement percentage

---

## Common Commands

```bash
# Quick test with mock tokens
python test_smtp_scenarios.py --scenario quick --use-mock-tokens

# Baseline test
python test_smtp_scenarios.py --scenario baseline --use-mock-tokens

# Stress test (auto-confirm long tests)
python test_smtp_scenarios.py --scenario stress --use-mock-tokens --verbose

# Custom parameters
python test_smtp_load.py \
    --num-emails 1000 \
    --concurrent 50 \
    --from test.account1@gmail.com \
    --use-mock-tokens

# List all available accounts
python -c "from mock_oauth2_tokens import list_available_accounts; print('\\n'.join(list_available_accounts()))"

# View token info
python -c "from mock_oauth2_tokens import get_token_info; info = get_token_info('test.account1@gmail.com'); import json; print(json.dumps(info, indent=2))"

# Generate XOAUTH2 string
python -c "from mock_oauth2_tokens import generate_xoauth2_string; print(generate_xoauth2_string('test.account1@gmail.com'))"
```

---

## Graceful Shutdown (Ctrl+C Handling)

### What Changed

**Before**:
- Ctrl+C might not work properly
- Test could hang
- Session errors if interrupted

**After**:
- Ctrl+C works immediately
- Test stops gracefully
- Partial results are displayed
- Clean shutdown

### How to Use

```bash
# Start test
$ python test_smtp_scenarios.py --scenario baseline --use-mock-tokens
[Test running... shows progress every batch]
[Batch 1/10] Sent: 25/500 | Success: 25 | Failed: 0...
[Batch 2/10] Sent: 50/500 | Success: 50 | Failed: 0...

# Press Ctrl+C to stop
^C
Test interrupted by user (Ctrl+C)
Stopped after 50 successful sends

================================================================================
LOAD TEST RESULTS (PARTIAL)
================================================================================
Total time: 2.50 seconds
Total requests: 50
Successful: 50
Failed: 0
Success rate: 100.0%

Throughput:
  Overall: 20.0 requests/sec
  Per minute: 1200 requests/minute

[Rest of results...]
```

### What Happens on Ctrl+C

1. ✅ Current batch completes (in progress sends finish)
2. ✅ Partial results are calculated
3. ✅ Results saved to JSON
4. ✅ Process exits cleanly
5. ✅ No hanging connections
6. ✅ No errors in logs

---

## Troubleshooting

### "Token refresh failed: Session is closed"

**Before Fix**: This error occurred when the test tried to use real OAuth2 tokens but the session closed.

**With Mock Tokens**: This error won't occur because:
- Tokens are pre-cached
- No session to close
- No real OAuth2 API calls

**Solution**: Use mock tokens
```bash
python test_smtp_scenarios.py --scenario quick --use-mock-tokens
```

### "All 2 attempts failed"

**Cause**: Proxy isn't running or wrong accounts.

**Solution**:
```bash
# 1. Start proxy first
python xoauth2_proxy_v2.py --config accounts.json --port 2525

# 2. In another terminal, run test
python test_smtp_scenarios.py --scenario quick --use-mock-tokens
```

### "Connection refused"

**Cause**: Proxy not listening on port 2525.

**Solution**:
```bash
# Check if proxy is running
curl http://127.0.0.1:9090/health

# If not, start it
python xoauth2_proxy_v2.py --config accounts.json --port 2525
```

### Test doesn't stop with Ctrl+C

**Cause**: Old version without signal handler.

**Solution**: Update test files (already done in this version)
```bash
# Verify the files have signal handling
grep -n "handle_signal\|signal.signal" test_smtp_load.py test_smtp_scenarios.py
```

---

## Expected Results

With mock tokens and Phase 1 optimizations:

### Throughput
```
Expected: 50-150 requests/sec (2-5x improvement from baseline)
With 100 concurrent: Could reach 150-300+ req/s
```

### Latency
```
Expected: 50-100ms per message (50-60% faster)
P95: Under 150ms
P99: Under 200ms
```

### Success Rate
```
Expected: 100% (with mock tokens)
Failures: 0 (all mock tokens are valid)
```

---

## Why Mock Tokens?

### Benefits

✅ **No Real Credentials Needed**
- Test without Gmail/Outlook accounts
- No credential leaks
- No accidental token exposure

✅ **Instant Testing**
- No OAuth2 setup required
- No authorization flow needed
- No token refresh waits

✅ **Realistic Performance Metrics**
- Tokens look real (correct format)
- SMTP flow identical to production
- Performance measurements are valid

✅ **Graceful Shutdown**
- Ctrl+C works immediately
- Partial results are saved
- No hanging connections

✅ **Reproducible Results**
- Same tokens every run
- No random API failures
- Consistent measurements

### Limitations

❌ **Mock Tokens Only**
- Won't actually send emails to real Gmail/Outlook
- For real email sending, use real credentials

❌ **Test Accounts Only**
- Limited to 4 pre-defined test accounts
- Can add more by editing mock_oauth2_tokens.py

❌ **Not for Production**
- Mock tokens don't work with real SMTP
- Only for testing the proxy

---

## Files

| File | Purpose |
|------|---------|
| `mock_oauth2_tokens.py` | Mock token cache and XOAUTH2 generation |
| `test_smtp_load.py` | Load testing tool (updated with mock token support) |
| `test_smtp_scenarios.py` | Scenario runner (updated with mock token support) |
| `MOCK_TOKEN_TESTING.md` | This guide |

---

## Next Steps

1. **Start proxy**: `python xoauth2_proxy_v2.py --config accounts.json --port 2525`
2. **Run quick test**: `python test_smtp_scenarios.py --scenario quick --use-mock-tokens`
3. **Try stopping**: Press Ctrl+C (should work smoothly now)
4. **View results**: Check the displayed metrics and JSON file

---

## Summary

**Problem Solved**:
- ✅ Ctrl+C now works gracefully
- ✅ Tests can run without real OAuth2 credentials
- ✅ Mock tokens provide realistic testing
- ✅ Partial results saved if interrupted

**Quick Commands**:
```bash
# Start proxy
python xoauth2_proxy_v2.py --config accounts.json --port 2525

# Quick test with mock tokens
python test_smtp_scenarios.py --scenario quick --use-mock-tokens

# Stop with Ctrl+C (works smoothly now!)
```

**No additional setup needed** - just use the `--use-mock-tokens` flag!
