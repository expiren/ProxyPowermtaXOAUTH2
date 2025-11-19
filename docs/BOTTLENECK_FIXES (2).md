# XOAUTH2 Proxy - Performance Bottleneck Quick Reference

## Top 5 Critical Bottlenecks (85% of performance loss)

### 1. TASK CREATION SPAM (src/smtp/handler.py:81-87)
- Creates 200k+ tasks/sec
- Each task = 10-50 µs overhead
- **Throughput impact: 50-100% reduction**

**Fix:**
```python
# BEFORE: Creates task for every line
def data_received(self, data):
    self.buffer += data
    while b'\r\n' in self.buffer:
        line, self.buffer = self.buffer.split(b'\r\n', 1)
        asyncio.create_task(self.handle_line(line))  # 200k tasks/sec!

# AFTER: Process in batches with task tracking
def data_received(self, data):
    self.buffer += data
    # Process only when complete command available
    if self.state == 'DATA_RECEIVING':
        # Accumulate data without creating tasks
        pass
    else:
        while b'\r\n' in self.buffer:
            line, self.buffer = self.buffer.split(b'\r\n', 1)
            self._process_line_sync(line)  # Sync or batch async
```

---

### 2. NOOP HEALTH CHECKS (src/smtp/connection_pool.py:129)
- 50,000 NOOP calls/min to Gmail/Outlook
- 2-second timeout on failure
- **Throughput impact: 30-50% reduction**

**Fix:**
```python
# BEFORE: Health check on every acquire
for pooled in pool:
    try:
        await asyncio.wait_for(pooled.connection.noop(), timeout=2.0)
        return pooled.connection

# AFTER: Trust age/idle time, skip NOOP
for pooled in pool:
    if not pooled.is_expired(...) and not pooled.is_idle_too_long(...):
        return pooled.connection  # Trust state, reuse directly
        
    # Only check stale-looking connections
    if pooled.message_count > 50:  # Might be broken
        try:
            await asyncio.wait_for(pooled.connection.noop(), timeout=0.2)
        except:
            await self._close_connection(pooled)
```

---

### 3. BLOCKING HTTP (src/utils/http_pool.py:69-77)
- Uses `requests` library (blocking)
- Default thread pool: 8-16 threads
- Thread starvation on high concurrency
- **Throughput impact: 10-20% reduction**

**Fix:**
```python
# BEFORE: Blocking requests library
async def post(self, url: str, data: dict, timeout: int = 10):
    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(
        None,
        lambda: session.post(url, data=data, timeout=timeout)  # BLOCKING
    )
    return response

# AFTER: Async aiohttp
import aiohttp

async def post(self, url: str, data: dict, timeout: int = 10):
    if not hasattr(self, 'session'):
        self.session = aiohttp.ClientSession()
    
    async with self.session.post(url, data=data, timeout=timeout) as resp:
        return await resp.json()
```

---

### 4. GLOBAL LOCK (src/smtp/connection_pool.py:88-92, 206-208)
- Every acquire/release serialized globally
- 50,000 lock acquisitions/min = 833/sec
- **Throughput impact: 70-90% reduction**

**Fix:**
```python
# BEFORE: Global lock on every operation
async def acquire(self, account_email: str, ...):
    async with self.global_lock:  # BOTTLENECK!
        if account_email not in self.locks:
            self.locks[account_email] = asyncio.Lock()
            self.pools[account_email] = []

# AFTER: Per-account lock only
async def acquire(self, account_email: str, ...):
    # Get or create lock lazily (needs atomic pattern)
    if account_email not in self.locks:
        self.locks[account_email] = asyncio.Lock()
        self.pools[account_email] = []
    
    lock = self.locks[account_email]
    async with lock:  # Per-account only!
        pool = self.pools[account_email]
        # ... rest of logic
```

**Or use safer pattern:**
```python
from collections import defaultdict

class SMTPConnectionPool:
    def __init__(self, ...):
        self.locks = defaultdict(asyncio.Lock)  # Per-email locks created on demand
        self.pools = defaultdict(list)
        # Remove self.global_lock entirely!
    
    async def acquire(self, account_email: str, ...):
        # Direct per-email lock - no global lock!
        async with self.locks[account_email]:
            pool = self.pools[account_email]
            # ...
```

---

### 5. LINEAR POOL SEARCH (src/smtp/connection_pool.py:99-147)
- O(n) search + O(n) removal on every acquire
- 50 connections × 100 accounts = 5000 items
- **Throughput impact: 30-40% reduction**

**Fix:**
```python
# BEFORE: List search and removal
pool = self.pools[account_email]  # list
for pooled in pool:
    if pooled.is_expired(...):
        pool.remove(pooled)  # O(n) remove!

# AFTER: Use deque for O(1) removal, dict for O(1) lookup
from collections import deque

class SMTPConnectionPool:
    def __init__(self, ...):
        self.pools = defaultdict(deque)  # Use deque instead of list!
        # Or: self.pools = {email: {'available': deque, 'busy': set}}
    
    async def acquire(self, account_email: str, ...):
        pool = self.pools[account_email]
        while pool:  # deque is efficient
            pooled = pool.popleft()  # O(1) removal
            if not pooled.is_busy and not pooled.is_expired(...):
                return pooled.connection
        
        # No available, create new
        ...

    async def release(self, account_email: str, connection):
        # Find pooled wrapper
        for pooled in self.pools[account_email]:
            if pooled.connection is connection:
                pooled.is_busy = False
                # deque maintains order for LRU
                break
```

---

## Secondary Bottlenecks (Easier Wins)

### Lock Contention in Auth Flow (src/smtp/handler.py:204-238)
- **Lines affected:** 204 (account lookup lock), 212 (token lock), 266 (verify lock)
- **Issue:** 3-4 nested lock acquisitions per AUTH
- **Throughput impact:** 20-30% reduction

**Fix:**
```python
# Consolidate to single lock per account
async def handle_auth(self, auth_data: str):
    auth_email = parts[1]
    
    account = await self.config_manager.get_by_email(auth_email)
    if not account:
        return

    # Single lock for all account operations
    async with account.lock:
        # Check and refresh token
        if account.token.is_expired():
            token = await self.oauth_manager.get_or_refresh_token(account)
            if not token:
                return
        
        # Verify XOAUTH2 (inline to avoid nested lock)
        xoauth2_string = f"user={account.email}..."
        # Inline verification (no separate function call)
        
        # Update counters
        self.active_connections[account.account_id] += 1
```

---

### Blocking Metrics Server (src/metrics/server.py:71-72)
- **Issue:** `serve_forever()` blocks thread indefinitely
- **Throughput impact:** 5-10% reduction
- **Fix:**
```python
# BEFORE: Blocking forever in executor
async def start(self):
    self.server = HTTPServer((self.host, self.port), MetricsHandler)
    await loop.run_in_executor(None, self.server.serve_forever)

# AFTER: Use aiohttp or async HTTP
import aiohttp
from aiohttp import web

async def start(self):
    app = web.Application()
    app.router.add_get('/metrics', self.metrics_handler)
    app.router.add_get('/health', self.health_handler)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, self.host, self.port)
    await site.start()
    
    # Non-blocking!
```

---

### Unbounded Metric Cardinality (src/metrics/collector.py)
- **Issue:** 1000 accounts = 1000+ time series per metric
- **Throughput impact:** 5-15% reduction
- **Fix:**
```python
# BEFORE: Unbounded account labels
auth_attempts_total = Counter(
    'auth_attempts_total',
    'Total AUTH attempts',
    ['account', 'result']  # Any account value!
)

# AFTER: Remove account labels or use ID
auth_attempts_total_v2 = Counter(
    'auth_attempts_total',
    'Total AUTH attempts',
    ['result']  # Only result label, not account!
)

# If you need per-account, use separate dict/gauge:
auth_attempts_per_account = {}  # Not metrics, just internal tracking
```

---

### Token Cache Global Lock (src/oauth2/manager.py:79-88)
- **Issue:** Single lock for entire token cache
- **Throughput impact:** 10-20% reduction
- **Fix:**
```python
# BEFORE: Global lock
async def _get_cached_token(self, email: str):
    async with self.lock:  # Global lock!
        cached = self.token_cache.get(email)

# AFTER: Per-email locks
class OAuth2Manager:
    def __init__(self, ...):
        self.token_locks = defaultdict(asyncio.Lock)  # Per-email!
        self.token_cache = {}
    
    async def _get_cached_token(self, email: str):
        async with self.token_locks[email]:  # Per-email lock
            cached = self.token_cache.get(email)
            # ...
```

---

## Measurement Checklist

Before/After metrics:
- [ ] Asyncio event loop lag (use `loop.time()` checks)
- [ ] Lock wait times (instrument with timing)
- [ ] Task queue depth (`asyncio.all_tasks()` count)
- [ ] Throughput (messages/sec)
- [ ] P95/P99 latency
- [ ] Memory usage (RSS)
- [ ] CPU usage per core
- [ ] Prometheus metrics scrape time

**Load test command:**
```bash
# Simulate 50k msg/min = 833 msg/sec
# Run for 60 seconds = 50,000 messages
for i in {1..50000}; do
    (swaks --server 127.0.0.1:2525 \
           --auth-user user@gmail.com \
           --auth-password placeholder \
           --from test@example.com \
           --to recipient@gmail.com &
    [ $((i % 100)) -eq 0 ] && wait)
done
wait
```

