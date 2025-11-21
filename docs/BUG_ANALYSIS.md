# Deep Code Analysis - Bugs and Performance Issues

**Date**: 2025-11-21
**Target**: High-volume SMTP proxy (70k msg/min)
**Focus**: Critical bugs, race conditions, memory leaks, performance bottlenecks

---

## CRITICAL BUGS

### 🔴 BUG #1: Race Condition in connection_lost() Counter Decrement

**File**: `src/smtp/handler.py:96`
**Severity**: CRITICAL - Causes counter corruption at high concurrency

```python
# CURRENT CODE (BUGGY):
def connection_lost(self, exc):
    if self.current_account:
        if self.state == 'DATA_RECEIVING' and self.current_account.concurrent_messages > 0:
            self.current_account.concurrent_messages -= 1  # ❌ NO LOCK!
```

**Problem**:
- Decrements `concurrent_messages` WITHOUT acquiring `account.lock`
- At 1,166 msg/sec, multiple threads can read/write the counter simultaneously
- Causes counter corruption: can become negative or miss decrements

**Impact**:
- Counter becomes inaccurate
- Can lead to account getting stuck (counter too high, blocks new messages)
- Or counter goes negative (allows too many concurrent messages)

**Fix**:
```python
def connection_lost(self, exc):
    if self.current_account:
        if self.state == 'DATA_RECEIVING':
            # ✅ Must use asyncio.create_task() because connection_lost() is NOT async
            asyncio.create_task(self._cleanup_on_disconnect())

async def _cleanup_on_disconnect(self):
    """Cleanup helper that can use async locks"""
    if self.current_account:
        async with self.current_account.lock:
            if self.current_account.concurrent_messages > 0:
                self.current_account.concurrent_messages -= 1
```

---

### 🔴 BUG #2: Counter Leak on Exception Before Semaphore Release

**File**: `src/smtp/handler.py:398-419`
**Severity**: CRITICAL - Leaks counter on exception

```python
async def handle_message_data(self, data: bytes):
    try:
        # Increment counter happens at line 386 BEFORE this try block!

        if self.global_semaphore:
            async with self.global_semaphore:  # ❌ If exception HERE...
                success, smtp_code, smtp_message = await self.upstream_relay.send_message(...)

        # Counter decrement at line 419
        async with self.current_account.lock:
            self.current_account.concurrent_messages -= 1  # ❌ Never reached!
```

**Problem**:
- Counter incremented at line 386 in `handle_data()`
- If exception occurs during semaphore acquisition or message sending (lines 398-416)
- Counter decrement at line 419 is NEVER executed
- Counter leaks by 1 for each failed message

**Impact**:
- At 70k msg/min with 1% error rate: 700 leaked counters/minute
- After 10 minutes: 7,000 leaked counters
- Accounts become permanently stuck (counter at max limit)

**Fix**:
```python
async def handle_message_data(self, data: bytes):
    # Counter is incremented in handle_data() before this is called
    try:
        # ... message processing ...
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        # ✅ ALWAYS decrement counter, even on exception
        try:
            async with self.current_account.lock:
                self.current_account.concurrent_messages -= 1
        except Exception as counter_error:
            logger.error(f"Counter decrement error: {counter_error}")
```

---

### 🟠 BUG #3: Memory Leak in line_queue on Connection Loss

**File**: `src/smtp/handler.py:68, 83-90`
**Severity**: MEDIUM - Memory leak with high connection churn

```python
def __init__(...):
    self.line_queue = asyncio.Queue(maxsize=backpressure_queue_size)  # 1000 items

def connection_lost(self, exc):
    if self.processing_task and not self.processing_task.done():
        self.processing_task.cancel()  # ❌ Queue NOT cleared!
```

**Problem**:
- If connection is lost with 500 pending commands in queue
- Queue objects remain in memory until garbage collected
- At 10,000 connections/hour with abrupt disconnects: significant memory waste

**Impact**:
- Memory usage grows over time
- Not critical (GC will clean up), but wastes memory

**Fix**:
```python
def connection_lost(self, exc):
    # Cancel task
    if self.processing_task and not self.processing_task.done():
        self.processing_task.cancel()

    # ✅ Clear queue to free memory immediately
    while not self.line_queue.empty():
        try:
            self.line_queue.get_nowait()
            self.line_queue.task_done()
        except asyncio.QueueEmpty:
            break
```

---

### 🟠 BUG #4: Unused start_time Variable After Log Removal

**File**: `src/smtp/upstream.py:87`
**Severity**: LOW - Wasted CPU cycles

```python
async def send_message(...):
    start_time = time.time()  # ❌ Calculated but never used after log removal!

    try:
        # ... 100 lines of code ...

        # Line 195-198 was REMOVED (log with duration)
        # logger.info(f"Message relayed successfully ({duration:.3f}s)")

        return (True, 250, "2.0.0 OK")
```

**Problem**:
- `time.time()` system call on EVERY message (1,166 calls/sec)
- Value never used after log removal
- Wasted CPU cycles

**Impact**:
- Minor CPU overhead (microseconds per call)
- At 1,166 msg/sec: ~1ms wasted CPU per second

**Fix**:
```python
async def send_message(...):
    # ✅ Remove unused variable
    # start_time = time.time()

    try:
        # ... message processing ...
```

---

### 🟠 BUG #5: Redundant global_semaphore Check

**File**: `src/smtp/handler.py:397-415`
**Severity**: LOW - Duplicate code

```python
if self.global_semaphore:
    async with self.global_semaphore:
        success, smtp_code, smtp_message = await self.upstream_relay.send_message(...)
else:
    # ❌ EXACT SAME CODE - redundant!
    success, smtp_code, smtp_message = await self.upstream_relay.send_message(...)
```

**Problem**:
- Duplicate code in both branches
- If semaphore exists, use it; otherwise, proceed without it
- Can be simplified

**Fix**:
```python
# ✅ Simplified with conditional context manager
if self.global_semaphore:
    async with self.global_semaphore:
        success, smtp_code, smtp_message = await self.upstream_relay.send_message(...)
else:
    success, smtp_code, smtp_message = await self.upstream_relay.send_message(...)

# OR use nullcontext:
from contextlib import nullcontext

async with (self.global_semaphore if self.global_semaphore else nullcontext()):
    success, smtp_code, smtp_message = await self.upstream_relay.send_message(...)
```

---

## PERFORMANCE ISSUES

### ⚡ PERF #1: Per-Email Lock Creation on Token Cache Hot Path

**File**: `src/oauth2/manager.py:97-100`
**Severity**: MEDIUM - Lock acquisition on every cache lookup

```python
async def _get_cached_token(self, email: str) -> Optional[TokenCache]:
    # Get or create per-email lock
    if email not in self.cache_locks:  # ❌ Dict lookup on hot path
        async with self._dict_lock:    # ❌ Lock acquisition on hot path
            if email not in self.cache_locks:
                self.cache_locks[email] = asyncio.Lock()
```

**Problem**:
- EVERY token cache lookup checks if lock exists
- If lock doesn't exist, acquires global `_dict_lock`
- At high volume, this is executed 1,166+ times/second

**Impact**:
- Lock contention on `_dict_lock`
- Adds latency to token cache lookups

**Optimization**:
```python
# ✅ Pre-create locks during account loading
async def initialize_locks_for_accounts(self, accounts):
    """Pre-create locks for all accounts during initialization"""
    async with self._dict_lock:
        for email in accounts.keys():
            if email not in self.cache_locks:
                self.cache_locks[email] = asyncio.Lock()
```

---

### ⚡ PERF #2: Regex .search() Instead of .match() in SMTP Parser

**File**: `src/smtp/handler.py:27-28`
**Severity**: LOW - Inefficient regex usage

```python
_MAIL_FROM_PATTERN = re.compile(r'FROM:<(.*?)>', re.IGNORECASE)
_RCPT_TO_PATTERN = re.compile(r'TO:<(.+?)>', re.IGNORECASE)

# Usage in handle_mail():
match = _MAIL_FROM_PATTERN.search(args)  # ❌ Scans entire string
```

**Problem**:
- `.search()` scans the entire string looking for pattern
- SMTP commands have predictable format: `FROM:<email>` at start
- `.match()` only checks from beginning, faster

**Impact**:
- Minimal (microseconds), but at 1,166 msg/sec: small cumulative overhead

**Optimization**:
```python
# ✅ Use anchored pattern with .match()
_MAIL_FROM_PATTERN = re.compile(r'^FROM:<(.*?)>', re.IGNORECASE)
_RCPT_TO_PATTERN = re.compile(r'^TO:<(.+?)>', re.IGNORECASE)

# Use .match() instead of .search()
match = _MAIL_FROM_PATTERN.match(args)
```

---

### ⚡ PERF #3: F-String Encoding in send_response() Slow Path

**File**: `src/smtp/handler.py:486`
**Severity**: LOW - String formatting overhead

```python
# Slow path for uncommon responses
separator = '-' if continue_response else ' '
response = f"{code}{separator}{message}\r\n".encode('utf-8')  # ❌ F-string + encode
```

**Problem**:
- F-strings are convenient but slower than % formatting or .format()
- Extra overhead for string interpolation

**Impact**:
- Minor (only for uncommon responses)

**Optimization**:
```python
# ✅ Faster: direct string concatenation as bytes
response = str(code).encode('ascii') + separator.encode('ascii') + message.encode('utf-8') + b'\r\n'

# OR pre-format as bytes template
response = b'%d%s%s\r\n' % (code, separator.encode('ascii'), message.encode('utf-8'))
```

---

### ⚡ PERF #4: Empty Exception Handler Hides Potential Issues

**File**: `src/smtp/connection_pool.py:494`
**Severity**: LOW - Silent error swallowing

```python
async def _close_connection(self, pooled: PooledConnection):
    try:
        await pooled.connection.quit()
        self.stats['connections_closed'] += 1
    except Exception as e:
        pass  # ❌ Silently ignores ALL exceptions
```

**Problem**:
- All exceptions during connection close are swallowed
- Could hide bugs (e.g., AttributeError, logic errors)
- Only network errors should be ignored

**Fix**:
```python
except (OSError, ConnectionError, asyncio.TimeoutError) as e:
    # ✅ Only ignore expected network errors
    logger.debug(f"Network error closing connection: {e}")
except Exception as e:
    # ✅ Log unexpected errors
    logger.warning(f"Unexpected error closing connection for {pooled.account_email}: {e}")
```

---

## SUMMARY

### Critical Bugs (Must Fix):
1. ✅ **Race condition in connection_lost()** - Counter corruption
2. ✅ **Counter leak on exception** - Accounts get stuck

### Medium Priority:
3. 🟠 Memory leak in line_queue - Minor memory waste
4. 🟠 Per-email lock creation overhead - Lock contention

### Low Priority:
5. 🟢 Unused start_time variable - Wasted CPU cycles
6. 🟢 Redundant if/else branches - Code smell
7. 🟢 Inefficient regex usage - Minor performance
8. 🟢 Silent exception swallowing - Debugging difficulty

---

## Recommendations

### Immediate Actions (Critical):
1. Fix race condition in `connection_lost()` by using async task with lock
2. Add `finally` block in `handle_message_data()` to always decrement counter
3. Test under high load (1000+ concurrent connections) to verify fixes

### Short-term (Medium Priority):
4. Pre-create locks for all accounts during initialization
5. Clear line_queue on connection loss to free memory
6. Remove unused `start_time` variable

### Optional (Low Priority):
7. Simplify redundant if/else with contextlib.nullcontext
8. Use .match() instead of .search() for SMTP patterns
9. Improve exception handling in connection close

---

**Performance Impact Estimate**:
- Critical bugs fixed: Prevents counter corruption and account lockups
- Medium optimizations: 5-10% reduction in lock contention
- Low optimizations: 1-2% CPU/memory savings

**Testing Required**:
- Load test with 1000 concurrent connections
- Simulate connection loss during message processing
- Monitor counter accuracy over 1-hour test at 70k msg/min
