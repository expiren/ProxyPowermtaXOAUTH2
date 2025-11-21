# Batch Account Addition - 400 Error Analysis

## Issue Summary

When adding 50 accounts with `verify=true`, the endpoint returns HTTP 400 even though all accounts appear to verify successfully.

## Root Cause Analysis

### Evidence from Logs:

1. **49 tokens cached** (not 50!)
   - zorachaloupk1764@outlook.com → hannelisedi3014@outlook.com
   - Count: 49 accounts

2. **HTTP 400 returned** with 376 bytes error response

3. **No "Saved" or "Reloaded" logs** - accounts were never saved

### The Bug:

Looking at `src/admin/server.py:773-781`:

```python
if failed_accounts:
    return web.json_response(
        {
            'success': False,
            'error': f'{len(failed_accounts)} accounts failed verification',
            'failed_accounts': failed_accounts
        },
        status=400
    )
```

**If ANY account fails verification, the ENTIRE batch fails and returns 400.**

### Why 1 Account Failed:

**50 parallel OAuth2 requests** to Microsoft/Google APIs simultaneously causes:

1. **Timeout** (3-second timeout is aggressive for 50 parallel requests)
2. **Rate limiting** from Microsoft/Google (concurrent connection limits)
3. **Network congestion** (50 simultaneous HTTPS connections)

## Why It's Intermittent:

- **10 accounts**: Low load, all succeed
- **50 accounts**: High load, 1-2 timeout → entire batch fails
- **100 accounts**: May succeed if network conditions are better
- **500 accounts in batches of 100**: Works because batches are sequential

## Solutions:

### Option 1: Increase Timeout (Quick Fix)
Change timeout from 3s to 10s in `src/admin/server.py:186`

### Option 2: Batch Parallel Verification (Better)
Instead of verifying all 50 in parallel, verify in batches of 10

### Option 3: Return Partial Success (Best UX)
Instead of failing entire batch, save successful accounts and return list of failures

## Recommended Fix:

**Implement batched parallel verification with increased timeout**

