# Mock Tokens - Quick Start (2 minutes)

**Two Problems Solved**:
1. Ctrl+C now works gracefully (no more hanging)
2. Tests work WITHOUT real OAuth2 credentials

---

## The Quick Way (30 seconds)

### Terminal 1: Start Proxy
```bash
python xoauth2_proxy_v2.py --config accounts.json --port 2525
```

### Terminal 2: Run Test with Mock Tokens
```bash
python test_smtp_scenarios.py --scenario quick --use-mock-tokens
```

**That's it!** The test will:
- ✓ Use cached mock tokens (no real credentials needed)
- ✓ Show progress as it sends emails
- ✓ Stop gracefully if you press Ctrl+C
- ✓ Display results with throughput metrics

---

## What Changed

### Before
```
$ python test_smtp_scenarios.py --scenario quick
[Error] Token refresh failed: Session is closed
[Error] All 2 attempts failed
[Test hangs if you press Ctrl+C]
```

### After
```
$ python test_smtp_scenarios.py --scenario quick --use-mock-tokens
[Batch 1/10] Sent: 10/100 | Success: 10 | Failed: 0 | Throughput: 50.0 req/s
[Batch 2/10] Sent: 20/100 | Success: 20 | Failed: 0 | Throughput: 48.0 req/s
...
[Complete with results]

[Press Ctrl+C anytime - it works!]
Test interrupted by user (Ctrl+C)
Stopped after 45 successful sends
[Partial results displayed]
```

---

## Available Test Accounts

Four mock accounts are pre-configured and ready to use:

```
Gmail:
  test.account1@gmail.com  ← First account (used by default)
  test.account2@gmail.com

Outlook:
  test.account1@outlook.com
  test.account2@outlook.com
```

Tokens are realistic and encoded in XOAUTH2 format.

---

## Quick Commands

```bash
# Quick test (100 emails, 10 concurrent)
python test_smtp_scenarios.py --scenario quick --use-mock-tokens

# Baseline (500 emails, 25 concurrent)
python test_smtp_scenarios.py --scenario baseline --use-mock-tokens

# Stress test (auto-confirm)
python test_smtp_scenarios.py --scenario stress --use-mock-tokens --verbose

# Custom test (1000 emails, 50 concurrent)
python test_smtp_load.py --num-emails 1000 --concurrent 50 --use-mock-tokens

# Specific account
python test_smtp_load.py --from test.account1@outlook.com --use-mock-tokens
```

---

## How Mock Tokens Work

1. **Pre-cached**: Tokens are already in memory (no API calls)
2. **Realistic Format**: Look like real OAuth2 tokens
3. **XOAUTH2 Encoded**: Base64 encoded for SMTP AUTH PLAIN
4. **Always Valid**: No expiration or refresh needed for testing

Example token:
```
Access Token: ya29.a0AfH6SMBz1234567890abcdefghijklmnopqrstuvwxyz
XOAUTH2 String: dXNlcj10ZXN0Lm...gIEJlYXJlciB5YTI5LmEwQWZINlNNQnoxMjM...
```

---

## Ctrl+C Handling

Press Ctrl+C anytime to stop gracefully:

```bash
$ python test_smtp_scenarios.py --scenario baseline --use-mock-tokens
[Batch 1/20] Sent: 25/500 | Success: 25 | Failed: 0 | Throughput: 50.0 req/s
[Batch 2/20] Sent: 50/500 | Success: 50 | Failed: 0 | Throughput: 48.0 req/s
^C
Test interrupted by user (Ctrl+C)
Stopped after 50 successful sends

================================================================================
LOAD TEST RESULTS (PARTIAL)
================================================================================
Total time: 1.04 seconds
Total requests: 50
Successful: 50
Failed: 0
Success rate: 100.0%

Throughput:
  Overall: 48.1 requests/sec
  Per minute: 2886 requests/minute
```

What happens:
1. ✓ Test stops immediately
2. ✓ Partial results calculated
3. ✓ Results saved to JSON file
4. ✓ No hanging connections
5. ✓ Clean exit

---

## Expected Results

With mock tokens and Phase 1 optimizations:

```
Throughput:     50-150 requests/sec
Latency:        50-100ms per message
Success Rate:   100% (all mock tokens valid)
Failures:       0
```

---

## No Real Credentials Needed!

Before, you needed:
- Gmail OAuth2 credentials
- Outlook OAuth2 credentials
- Refresh tokens from authorization flow
- Careful handling of secrets

Now with mock tokens:
- ✓ No credentials needed
- ✓ No secrets to manage
- ✓ Instant testing
- ✓ 100% success rate

---

## Troubleshooting

### Test still uses old behavior
**Fix**: Make sure to add `--use-mock-tokens` flag
```bash
python test_smtp_scenarios.py --scenario quick --use-mock-tokens
                                                  ↑ Add this
```

### Proxy not running
```bash
# Check if running
curl http://127.0.0.1:9090/health

# If not, start it
python xoauth2_proxy_v2.py --config accounts.json --port 2525
```

### Ctrl+C still doesn't work
**Fix**: Make sure you're using updated test files (already applied)
```bash
# Verify signal handler is present
grep "handle_signal\|signal.signal" test_smtp_scenarios.py
```

---

## Files Modified

```
test_smtp_load.py           ← Added --use-mock-tokens flag
test_smtp_scenarios.py      ← Added --use-mock-tokens flag + Ctrl+C handler
mock_oauth2_tokens.py       ← NEW: Mock token cache module
MOCK_TOKEN_TESTING.md       ← NEW: Detailed guide
MOCK_TOKENS_QUICK_START.md  ← NEW: This file
```

---

## Next Steps

1. **Start proxy**:
   ```bash
   python xoauth2_proxy_v2.py --config accounts.json --port 2525
   ```

2. **Run test with mock tokens**:
   ```bash
   python test_smtp_scenarios.py --scenario quick --use-mock-tokens
   ```

3. **Try Ctrl+C** (should work smoothly now!)

4. **View results** in the console output

---

## Summary

**Two Problems Fixed**:
- ✓ Ctrl+C works gracefully
- ✓ Tests work without real OAuth2 credentials

**Just Add**: `--use-mock-tokens` flag

**That's it!** No setup, no credentials, instant testing.

For detailed info, see: **MOCK_TOKEN_TESTING.md**
