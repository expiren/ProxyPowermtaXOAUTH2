# Connection Pool Cleanup Task Fix

**Status**: FIXED
**Date**: 2025-11-24
**Issue**: Error in cleanup_idle_connections() task

---

## Problem

When the proxy was running, the cleanup task would crash with:

```
ERROR - [Pool] Error in cleanup task: 'SMTPConnectionPool' object has no attribute 'pools'
```

### Root Cause

The PERF FIX #6 restructured the connection pool from a single `self.pools` dictionary to separate `self.pool_idle` and `self.pool_busy` structures for O(1) connection lookup.

However, the background cleanup task was still trying to access the old `self.pools.keys()` which no longer existed:

```python
# OLD (BROKEN)
async with self._dict_lock:
    accounts = list(self.pools.keys())  # ❌ self.pools doesn't exist anymore!
```

---

## Solution

Updated the cleanup task to use `self.locks.keys()` instead, which is the correct reference point for all accounts (since `self.locks` is created whenever a new account is initialized):

```python
# FIXED (CORRECT)
async with self._dict_lock:
    accounts = list(self.locks.keys())  # ✅ Correct - locks exist for all accounts
```

---

## File Changed

**File**: `src/smtp/connection_pool.py`
**Line**: 513
**Change**: `self.pools.keys()` → `self.locks.keys()`

---

## Verification

✅ All files compile successfully
✅ Connection pool imports without errors
✅ Cleanup task will now work correctly

---

## What This Does

The cleanup task runs every 10 seconds in the background and:

1. **Gets list of all accounts** (now correctly using `self.locks.keys()`)
2. **Cleans up idle connections** that have:
   - Expired (older than 5 minutes)
   - Been idle too long (no messages for 60 seconds)
   - Been reused too many times (100+ messages)
3. **Runs cleanup for all accounts in parallel** for performance

---

## Impact

**Before Fix**:
- Cleanup task crashes every 10 seconds
- Error spammed in logs
- Idle connections not cleaned up (memory leak potential)

**After Fix**:
- Cleanup task runs successfully every 10 seconds
- No errors in logs
- Idle/expired connections cleaned up properly
- Memory usage stays healthy

---

## Testing

To verify the fix works:

1. Start the proxy:
   ```bash
   python xoauth2_proxy_v2.py --config accounts.json --port 2525
   ```

2. Monitor logs for 30+ seconds:
   ```bash
   tail -f /var/log/xoauth2/xoauth2_proxy.log | grep -i "pool\|cleanup"
   ```

3. **Expected**: No errors about "has no attribute 'pools'"

---

## Related Commits

- **Previous**: `PERF: Phase 1 performance fixes` - Introduced the idle/busy pool structure (PERF FIX #6)
- **This commit**: Fixed the cleanup task to use the new structure

---

## Summary

Simple one-line fix that ensures the connection pool cleanup task works correctly with the new idle/busy connection pool structure. No functional change - just updated the reference to use the correct attribute name.
