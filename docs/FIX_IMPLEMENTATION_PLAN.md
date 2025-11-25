# Code Logic Fixes - Implementation Plan

**Date**: 2025-11-23
**Status**: READY FOR IMPLEMENTATION
**Goal**: Achieve 1000+ msg/sec throughput (5-10x improvement)

---

## Summary of Fixes Required

| Priority | Fix | File | Lines | Effort | Impact |
|----------|-----|------|-------|--------|--------|
| **CRITICAL** | Remove/restructure global semaphore | `handler.py` | 434-452 | 30 min | 5-10x throughput |
| **HIGH** | Minimize pool lock scope | `connection_pool.py` | 186-320 | 1-2 hours | +20-30% throughput |
| **MEDIUM** | Fix rate limiter double-lock | `rate_limiter.py` | 28-65 | 30 min | +5-10% throughput |
| **LOW** | Add timing instrumentation | `handler.py`, `upstream.py` | Various | 1 hour | Measurement only |

---

## FIX #1: CRITICAL - Global Semaphore Restructuring

### Current Problem

```python
# src/smtp/handler.py, lines 434-443
    async with self.global_semaphore:  # Holds for ENTIRE relay (500ms!)
        success, smtp_code, smtp_message = await self.upstream_relay.send_message(...)
```

**Issue**: Semaphore held for entire message relay operation (200-700ms), bottlenecking throughput to ~200 msg/sec.

### Recommended Solution: Option A - Remove Semaphore Entirely

**Rationale**: Concurrency is already limited by:
1. Connection pool (max 50/account)
2. Per-account limits (max 150 concurrent messages)
3. OAuth2 token refresh rate
4. Upstream SMTP provider rate limits

Semaphore is redundant triple-limiting.

### Implementation

**File**: `src/smtp/handler.py`

**Changes**:
```python
# BEFORE (lines 433-452)
try:
    if self.global_semaphore:
        async with self.global_semaphore:
            success, smtp_code, smtp_message = await self.upstream_relay.send_message(
                account=self.current_account,
                message_data=self.message_data,
                mail_from=self.mail_from,
                rcpt_tos=self.rcpt_tos,
                dry_run=self.dry_run
            )
    else:
        success, smtp_code, smtp_message = await self.upstream_relay.send_message(
            account=self.current_account,
            message_data=self.message_data,
            mail_from=self.mail_from,
            rcpt_tos=self.rcpt_tos,
            dry_run=self.dry_run
        )

# AFTER (simplified)
try:
    # ✅ FIX #1: Remove global semaphore - concurrency already limited by:
    # 1. Connection pool size (max_connections_per_account: 50)
    # 2. Per-account concurrency limit (max_concurrent_messages: 150)
    # 3. Upstream SMTP provider rate limits
    # Semaphore was triple-limiting, causing bottleneck
    success, smtp_code, smtp_message = await self.upstream_relay.send_message(
        account=self.current_account,
        message_data=self.message_data,
        mail_from=self.mail_from,
        rcpt_tos=self.rcpt_tos,
        dry_run=self.dry_run
    )
```

**Also Remove**:
- Remove `self.global_semaphore` initialization from `__init__()` (around line 60-70)
- Remove semaphore creation from `SMTPProxyServer.initialize()` in `proxy.py`
- Remove semaphore parameter from handler initialization

**Expected Impact**:
- Throughput: 200 msg/sec → 1000+ msg/sec (5x improvement)
- Latency: Reduced head-of-line blocking
- Resource usage: More concurrent operations in flight

---

## FIX #2: HIGH - Minimize Connection Pool Lock Scope

### Current Problem

```python
# src/smtp/connection_pool.py, lines 186-320 (in acquire() method)
async with self.locks[account_email]:
    for pooled in pool:
        # ... check connections (quick, O(n) where n<=50) ...

    # CREATE NEW CONNECTION (200ms!) WHILE HOLDING LOCK
    connection = await self._create_connection(...)

    # Add to pool while still holding lock
    pool.append(connection)
    return connection  # Finally release lock
```

**Issue**: Lock held for 200ms during connection creation, blocking other messages.

### Implementation

**File**: `src/smtp/connection_pool.py`

**Changes** (restructure acquire() method):

```python
async def acquire(self, account_email: str, smtp_host: str, smtp_port: int,
                 xoauth2_string: str, account) -> 'SMTPConnection':
    """Acquire connection from pool with minimized lock scope"""

    pool = self.pools[account_email]

    # ===== FIRST: Check for available connection (QUICK, WITH LOCK)
    async with self.locks[account_email]:
        for pooled in pool:
            if pooled.is_busy:
                continue
            if pooled.is_expired(self.connection_max_age, self.idle_timeout):
                # Don't remove here, just skip
                continue
            # Found available connection - return immediately
            pooled.is_busy = True
            pooled.message_count += 1
            return pooled

    # ===== SECOND: Need to create new connection (SLOW, WITHOUT LOCK)
    # Create connection outside lock (can take 200ms)
    connection = await self._create_connection(
        account_email=account_email,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        xoauth2_string=xoauth2_string,
        account=account
    )

    # ===== THIRD: Add to pool (QUICK, WITH LOCK)
    async with self.locks[account_email]:
        # Double-check another coroutine didn't add while we were creating
        for pooled in self.pools[account_email]:
            if pooled.is_busy:
                continue
            if not pooled.is_expired(self.connection_max_age, self.idle_timeout):
                # Another thread added one, use that instead
                await connection.close()  # Close the one we created
                pooled.is_busy = True
                pooled.message_count += 1
                return pooled

        # Still need ours, add and return it
        pooled = PooledConnection(
            connection=connection,
            created_at=datetime.now(UTC),
            last_used=datetime.now(UTC),
            message_count=1
        )
        pooled.is_busy = True
        self.pools[account_email].append(pooled)
        return pooled
```

**Benefits**:
- Lock held for ~10-50ms (quick iteration) instead of 200ms
- Connection creation happens in parallel
- Other accounts don't block waiting for pool lock

**Expected Impact**:
- Throughput: +20-30% improvement (less lock contention)
- Latency: Reduced variance, smoother throughput
- CPU: Better utilization (less lock spinning)

---

## FIX #3: MEDIUM - Fix Rate Limiter Double-Lock

### Current Problem

```python
# src/utils/rate_limiter.py
async def acquire(self, tokens: float) -> bool:
    new_tokens = await self._calculate_refill()  # Acquires lock internally

    async with self.lock:  # Re-acquires lock!
        self.tokens = min(capacity, self.tokens + new_tokens)
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
    return False

async def _calculate_refill(self) -> float:
    async with self.lock:  # First lock here
        now = datetime.now(UTC)
        elapsed = (now - self.last_refill).total_seconds()
        self.last_refill = now  # Update timestamp
    return elapsed * self.refill_rate  # Calculate outside lock
```

**Issue**: Two separate lock acquisitions when one would suffice.

### Implementation

**File**: `src/utils/rate_limiter.py`

**Changes** (consolidate into single lock):

```python
async def acquire(self, tokens: float = 1.0) -> bool:
    """
    Acquire tokens from the bucket (rate limiting).

    Uses single lock acquisition for efficiency.
    ✅ FIX #3: Removed double-lock pattern
    """
    async with self.lock:
        # Calculate refill amount (all inside single lock)
        now: datetime = datetime.now(UTC)
        elapsed = (now - self.last_refill).total_seconds()
        self.last_refill = now

        # Refill tokens based on elapsed time
        new_tokens = elapsed * self.refill_rate
        self.tokens = min(float(self.capacity), self.tokens + new_tokens)

        # Try to acquire requested tokens
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True

        return False
```

**Remove**: The `_calculate_refill()` method entirely (now inline in `acquire()`)

**Also Remove**: The separate `_refill()` method if it exists (duplicate functionality)

**Expected Impact**:
- Lock operations: Reduced from 2000/sec (1000 msg/sec × 2 locks) to 1000/sec
- Per-account throughput: +5-10% improvement
- CPU: Slightly lower lock contention

---

## FIX #4: LOW - Add Instrumentation for Monitoring

### Purpose

Add timing measurements to identify remaining bottlenecks after fixes #1-3.

### Implementation

**File**: `src/smtp/upstream.py` - `send_message()` method

```python
async def send_message(self, account, message_data, mail_from, rcpt_tos, dry_run=False):
    """Send message with timing instrumentation"""
    import time

    t_start = time.perf_counter()
    t_rate_limit = t_oauth = t_conn_acquire = t_relay = t_end = 0

    try:
        # Rate limiting
        t = time.perf_counter()
        if self.rate_limiter:
            await self.rate_limiter.acquire(account.email, account=account)
        t_rate_limit = time.perf_counter() - t

        # OAuth2 token refresh
        t = time.perf_counter()
        token = await self.oauth_manager.get_or_refresh_token(account)
        t_oauth = time.perf_counter() - t
        if not token:
            return (False, 454, "Token refresh failed")

        # Connection pool acquire
        t = time.perf_counter()
        connection = await self.connection_pool.acquire(...)
        t_conn_acquire = time.perf_counter() - t

        # Message relay
        t = time.perf_counter()
        # ... actual SMTP relay ...
        t_relay = time.perf_counter() - t

        t_end = time.perf_counter() - t_start

        # Log timing summary
        if t_end > 1.0:  # Log slow messages
            logger.warning(
                f"[{account.email}] Slow message relay ({t_end*1000:.0f}ms): "
                f"rate_limit={t_rate_limit*1000:.0f}ms, "
                f"oauth={t_oauth*1000:.0f}ms, "
                f"acquire={t_conn_acquire*1000:.0f}ms, "
                f"relay={t_relay*1000:.0f}ms"
            )

        return (success, code, msg)
```

**Expected Output**:
```
[account@outlook.com] Slow message relay (450ms): rate_limit=5ms, oauth=20ms, acquire=150ms, relay=275ms
[account@gmail.com] Slow message relay (520ms): rate_limit=10ms, oauth=50ms, acquire=200ms, relay=260ms
```

This reveals which component is slowest.

---

## Testing Plan

### Test 1: Basic Functionality

After each fix, run a basic test:

```bash
python xoauth2_proxy_v2.py --config config.json

# In another terminal, send 10 test messages
for i in {1..10}; do
    swaks --server 127.0.0.1:2525 \
      --auth-user account@outlook.com \
      --auth-password placeholder \
      --from test@example.com \
      --to recipient@gmail.com
done

# Check: All 10 should be accepted, no errors
```

### Test 2: Throughput Benchmark

After all fixes, measure throughput:

```bash
# Send 1000 messages to one account
time for i in {1..1000}; do
    echo "Message $i" | swaks --server 127.0.0.1:2525 \
      --auth-user high-volume@outlook.com \
      --auth-password placeholder \
      --from test@example.com \
      --to recipient$((RANDOM))@gmail.com
done

# Expected: <1 second for 1000 messages = 1000 msg/sec throughput
# Current: ~5 seconds = 200 msg/sec
```

### Test 3: Multi-Account Throughput

Test with 10 accounts sending simultaneously:

```bash
for account in {1..10}; do
    (
        for i in {1..100}; do
            echo "Message from account $account message $i" | \
            swaks --server 127.0.0.1:2525 \
              --auth-user account$account@outlook.com \
              --auth-password placeholder \
              --from test@example.com \
              --to recipient@gmail.com
        done
    ) &
done

wait

# Expected: All 1000 messages (10 accounts × 100) should complete quickly
# Current: Would take ~50 seconds
# After fix: Should take <5 seconds
```

---

## Implementation Order

1. **Fix #3** (5 min): Rate limiter - lowest risk, small change
2. **Fix #2** (2 hours): Pool lock - medium risk, medium effort
3. **Fix #1** (30 min): Semaphore - high impact, moderate risk
4. **Fix #4** (1 hour): Instrumentation - zero risk, informational

**Estimated Total Time**: 3.5 hours implementation + testing

---

## Validation Checklist

After implementing all fixes:

- [ ] JSON syntax valid (`python -m json.tool config.json`)
- [ ] Code compiles (`python -m py_compile src/**/*.py`)
- [ ] Proxy starts without errors
- [ ] Basic functionality works (10 message test)
- [ ] No messages rejected due to concurrency limits
- [ ] Single-account throughput: >500 msg/sec
- [ ] Multi-account throughput: >1000 msg/sec
- [ ] Timing instrumentation shows where time is spent
- [ ] Memory usage reasonable
- [ ] CPU usage <80%

---

## Expected Results

| Metric | Before Fixes | After Fixes | Target |
|--------|-------------|------------|--------|
| Throughput (single account) | 150-200 msg/sec | 500-800 msg/sec | 1000+ |
| Throughput (500 accounts) | 50-100 msg/sec | 500-1000 msg/sec | 1000+ |
| Startup time | <30 sec | <30 sec | <30 sec |
| Per-message latency | 500ms | 200-300ms | <200ms |
| Lock contention | High | Low | Minimal |
| Memory usage | Reasonable | Slightly higher | Acceptable |

---

## Risk Assessment

### Fix #1 Risk: MEDIUM
- **Risk**: Removing semaphore could cause connection exhaustion
- **Mitigation**: Connection pool already limits connections per account
- **Rollback**: Quick - add semaphore back if issues arise

### Fix #2 Risk: HIGH
- **Risk**: Race condition in double-check acquire pattern
- **Mitigation**: Carefully test with concurrent message bursts
- **Rollback**: Revert connection_pool.py to original

### Fix #3 Risk: LOW
- **Risk**: Logic error in token bucket calculation
- **Mitigation**: Same logic, just consolidated
- **Rollback**: Revert rate_limiter.py to original

### Fix #4 Risk: NONE
- **Risk**: Instrumentation only, no logic changes
- **Mitigation**: N/A
- **Rollback**: Remove instrumentation if noisy

---

## Next Steps

1. ✅ **DONE**: Analysis complete
2. **NEXT**: Implement fixes in order
3. **THEN**: Run comprehensive tests
4. **FINALLY**: Deploy to production with monitoring

---

**Status**: Ready for implementation
**Date**: 2025-11-23
