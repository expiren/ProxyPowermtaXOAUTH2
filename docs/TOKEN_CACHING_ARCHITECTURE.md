# Token Caching & XOAUTH2 Preparation Architecture

**Date**: 2025-11-24
**Status**: Analysis Complete - Current flow and proposed enhancement
**Goal**: Pre-cache tokens and prepare XOAUTH2 strings on startup so relay has instant access

---

## Current Flow (How It Works Now)

### Step 1: Proxy Starts

```
proxy.start()
  ↓
proxy.initialize()
  ├─ Load accounts (accounts.json)
  ├─ Initialize OAuth2Manager (HTTP pool)
  ├─ Prewarm connections (to Gmail/Outlook SMTP)
  └─ Return (accounts loaded, connections ready)
```

### Step 2: Message Arrives

```
PowerMTA → Proxy (MAIL FROM, RCPT TO, DATA)
  ↓
handle_mail() / handle_rcpt()
  ↓
handle_message_data() → _relay_message_background()
  ├─ Get account from email
  └─ Send message to relay
```

### Step 3: Relay to Gmail/Outlook

```
upstream.send_message()
  ├─ ✅ Get/refresh token: await self.oauth_manager.get_or_refresh_token(account)
  │   ├─ Check token cache (200μs if cached)
  │   └─ Or refresh from OAuth provider (200-500ms if expired)
  │
  ├─ Build XOAUTH2 string: f"user={mail_from}\1auth=Bearer {token.access_token}\1\1"
  │
  ├─ Acquire connection from pool
  │
  └─ Send MAIL FROM, RCPT TO, DATA
```

### Bottleneck Identified

**Current flow**:
```
Message arrives → Relay waits for token → Refresh from OAuth provider (200-500ms!)
```

**If token expired**:
- Client waits 200-500ms for OAuth2 provider to respond
- This blocks relay even though connection is ready
- Multiple messages with expired token = multiple refreshes

---

## Proposed Enhancement: Pre-Cache Tokens on Startup

### New Flow

**Step 1: Proxy Starts (ENHANCED)**

```
proxy.start()
  ↓
proxy.initialize()
  ├─ Load accounts (accounts.json)
  ├─ Initialize OAuth2Manager (HTTP pool)
  ├─ Prewarm connections (to Gmail/Outlook SMTP)
  │
  └─ ✅ NEW: Pre-cache all tokens immediately
      ├─ For each account: await oauth_manager.get_or_refresh_token(account)
      ├─ This forces one refresh per account on startup
      ├─ All tokens now cached (3600 second TTL)
      └─ Next message won't need to refresh!
```

**Step 2: Message Arrives (SAME)**

```
PowerMTA → Proxy (MAIL FROM, RCPT TO, DATA)
  ↓
handle_mail() / handle_rcpt()
  ↓
handle_message_data() → _relay_message_background()
  └─ Send message to relay
```

**Step 3: Relay to Gmail/Outlook (FASTER)**

```
upstream.send_message()
  ├─ Get token: await self.oauth_manager.get_or_refresh_token(account)
  │   ├─ ✅ CACHE HIT! (200μs - token still valid)
  │   └─ No refresh needed (token expires in 3600 seconds)
  │
  ├─ Build XOAUTH2 string (instant)
  │
  ├─ Acquire connection (instant)
  │
  └─ Send MAIL FROM, RCPT TO, DATA (instant)
```

---

## Token Lifetime and Cache Behavior

### Token Properties

```python
OAuthToken:
  ├─ access_token: str (the actual OAuth2 token)
  ├─ expires_at: datetime (when token expires)
  ├─ refresh_token: str (for refreshing when expired)
  └─ scope: str (what the token grants access to)

TokenCache:
  ├─ token: OAuthToken
  └─ is_valid(): bool (checks if expires_at > now() + 300s buffer)
```

### Token Refresh Logic

```python
# In oauth_manager.get_or_refresh_token()

if not force_refresh:
    cached = await self._get_cached_token(account.email)
    if cached:
        return cached.token  # ✅ CACHE HIT - instant return

# Token expired or not cached - refresh from OAuth provider
token = await self._refresh_token_internal(account)  # Network call (200-500ms)
await self._cache_token(account.email, token)
return token
```

### 300-Second Buffer

```python
# In TokenCache.is_valid()
def is_valid(self) -> bool:
    # Token is valid if expires_at > now() + 300 seconds
    buffer = timedelta(seconds=300)
    return self.token.expires_at > datetime.now(UTC) + buffer
```

This prevents using tokens that are about to expire.

---

## Current Pre-Caching (Partial)

The proxy **ALREADY** pre-caches tokens after reload (line 166-177 in proxy.py):

```python
# ✅ FIX Issue #5: Refresh and cache tokens for all accounts after reload
logger.info("[SMTPProxyServer] Pre-populating OAuth2 token cache after reload...")
for account in accounts:
    try:
        await self.oauth_manager.get_or_refresh_token(account)
    except Exception as e:
        logger.warning(f"Failed to cache token for {account.email}: {e}")
logger.info("[SMTPProxyServer] OAuth2 token cache pre-populated")
```

**But this only happens on RELOAD, not on INITIAL STARTUP!**

---

## Proposed Solution: Pre-Cache on Startup

### Add Pre-Caching to Initial Initialize()

**Current code (proxy.py lines 90-121)**:

```python
async def initialize(self) -> int:
    """Initialize all components"""
    # Load accounts
    num_accounts = await self.account_manager.load()

    # Initialize OAuth2 manager
    await self.oauth_manager.initialize()

    # Initialize upstream relay with connection pool
    await self.upstream_relay.initialize()

    # Prewarm connections
    if num_accounts > 0:
        accounts = await self.account_manager.get_all()
        await self.upstream_relay.connection_pool.prewarm_adaptive(
            accounts,
            oauth_manager=self.oauth_manager
        )

    logger.info(f"[SMTPProxyServer] Initialized with {num_accounts} accounts")
    return num_accounts
```

**Enhanced code**:

```python
async def initialize(self) -> int:
    """Initialize all components"""
    # Load accounts
    num_accounts = await self.account_manager.load()

    # Initialize OAuth2 manager
    await self.oauth_manager.initialize()

    # Initialize upstream relay with connection pool
    await self.upstream_relay.initialize()

    # Prewarm connections
    if num_accounts > 0:
        accounts = await self.account_manager.get_all()
        await self.upstream_relay.connection_pool.prewarm_adaptive(
            accounts,
            oauth_manager=self.oauth_manager
        )

        # ✅ NEW: Pre-cache all tokens on startup
        # This ensures first message doesn't wait for OAuth2 refresh
        # Tokens are cached for 3600 seconds (1 hour)
        logger.info("[SMTPProxyServer] Pre-populating OAuth2 token cache on startup...")
        for account in accounts:
            try:
                await self.oauth_manager.get_or_refresh_token(account)
                logger.debug(f"[SMTPProxyServer] Cached token for {account.email}")
            except Exception as e:
                logger.warning(f"[SMTPProxyServer] Failed to cache token for {account.email}: {e}")
        logger.info("[SMTPProxyServer] OAuth2 token cache pre-populated")

    logger.info(f"[SMTPProxyServer] Initialized with {num_accounts} accounts")
    return num_accounts
```

---

## XOAUTH2 String Preparation

### What is XOAUTH2?

XOAUTH2 is Google/Microsoft's extension to SMTP AUTH that uses OAuth2 tokens instead of passwords.

**Format** (RFC 6749):
```
user=<email>\1auth=Bearer <access_token>\1\1
```

**Example**:
```
user=sender@gmail.com\1auth=Bearer ya29.a0AfH6SMB...\1\1
```

**Where it's prepared** (upstream.py line 114):
```python
xoauth2_string = f"user={mail_from}\1auth=Bearer {token.access_token}\1\1"
```

### Current Flow

```
Message arrives
  ↓
Relay gets token (from cache or refresh)
  ↓
Build XOAUTH2 string
  ↓
Connect to Gmail/Outlook
  ↓
Send XOAUTH2 string in AUTH command
```

### Why Pre-Caching Helps

**If token is cached** (3600 second TTL):
```
Relay gets token (200μs from cache)
  ↓
Build XOAUTH2 string (instant)
  ↓
Total overhead: 200μs (negligible)
```

**If token is expired and must refresh**:
```
Relay refreshes token (200-500ms network call!)
  ↓
Build XOAUTH2 string (instant)
  ↓
Total overhead: 200-500ms (SIGNIFICANT)
```

---

## Performance Impact

### Scenario 1: No Pre-Caching (Current Partial Implementation)

```
Proxy starts:
├─ Load accounts: 10ms
├─ Initialize OAuth2: 5ms
├─ Prewarm connections: 100ms (for all accounts)
└─ Done (tokens NOT cached)

Message 1 arrives (first message):
├─ Check token cache: MISS
├─ Refresh from OAuth2 provider: 250ms
├─ Build XOAUTH2: 1ms
├─ Send to Gmail: 150ms
└─ Total: 401ms

Message 2-N arrive (same account, token still valid):
├─ Check token cache: HIT (200μs)
├─ Build XOAUTH2: 1ms
├─ Send to Gmail: 150ms
└─ Total: 151ms (MUCH FASTER)
```

### Scenario 2: With Pre-Caching (Proposed)

```
Proxy starts:
├─ Load accounts: 10ms
├─ Initialize OAuth2: 5ms
├─ Prewarm connections: 100ms
├─ Pre-cache all tokens: 250ms × N accounts (network call per account)
│  └─ For 100 accounts: 250ms × 100 = 25 seconds (upfront cost)
└─ Done (all tokens cached!)

Message 1 arrives (first message):
├─ Check token cache: HIT (200μs - pre-cached!)
├─ Build XOAUTH2: 1ms
├─ Send to Gmail: 150ms
└─ Total: 151ms (MUCH FASTER than scenario 1)

Message 2-N arrive:
├─ Check token cache: HIT (200μs)
├─ Build XOAUTH2: 1ms
├─ Send to Gmail: 150ms
└─ Total: 151ms
```

---

## Trade-Offs

### Pre-Caching Advantages

✅ **First message is faster** (no OAuth2 refresh)
✅ **Predictable latency** (no random 250-500ms delays)
✅ **Fewer OAuth2 provider calls** (less load on Google/Microsoft)
✅ **Better for high-volume senders** (consistent throughput)

### Pre-Caching Disadvantages

❌ **Startup time increases** (250ms × N accounts)
❌ **For 100 accounts**: Startup takes 25 extra seconds
❌ **If OAuth2 provider is down**: Startup fails (currently it retries on-demand)
❌ **If credentials are invalid**: Startup fails (instead of failing on first message)

### When Pre-Caching is Worth It

| Scenario | Benefit |
|----------|---------|
| **High-volume mail** (1000+ msg/sec) | ✅ YES - reduces unpredictable delays |
| **Many accounts** (50+) | ✅ YES - upfront cost amortized |
| **Mission-critical** (can't lose messages) | ✅ YES - predictable latency |
| **Low-volume** (10 msg/sec) | ❌ NO - startup delay not worth it |
| **Few accounts** (1-5) | ❌ NO - startup delay makes it slower overall |

---

## Implementation Plan

### Option 1: Pre-Cache All Tokens on Startup (Current Request)

**Location**: `src/smtp/proxy.py` lines 90-121

**Change**: Add token pre-caching loop after prewarm_adaptive()

```python
# In proxy.py initialize() method
if num_accounts > 0:
    accounts = await self.account_manager.get_all()

    # Prewarm connections
    await self.upstream_relay.connection_pool.prewarm_adaptive(accounts, oauth_manager=self.oauth_manager)

    # ✅ Pre-cache tokens
    logger.info("[SMTPProxyServer] Pre-populating OAuth2 token cache on startup...")
    for account in accounts:
        try:
            await self.oauth_manager.get_or_refresh_token(account)
            logger.debug(f"[SMTPProxyServer] Cached token for {account.email}")
        except Exception as e:
            logger.warning(f"[SMTPProxyServer] Failed to cache token for {account.email}: {e}")
    logger.info("[SMTPProxyServer] OAuth2 token cache pre-populated")
```

### Option 2: Optional Pre-Caching (Via Configuration)

**Location**: `src/config/settings.py`

**Add setting**:
```python
@dataclass
class Settings:
    ...
    precache_tokens_on_startup: bool = True  # Default: enabled
    ...
```

**Use in proxy.py**:
```python
if num_accounts > 0 and self.settings.precache_tokens_on_startup:
    # Pre-cache tokens if enabled
```

---

## Token Cache Visibility

### View Cached Tokens

The OAuth2Manager already tracks cache stats:

```python
stats = self.oauth_manager.get_stats()
print(stats['cached_tokens'])  # Number of tokens in cache
print(stats['metrics'])  # Cache hit/miss statistics
```

### Monitor via Logs

When pre-caching runs:
```
[SMTPProxyServer] Pre-populating OAuth2 token cache on startup...
[SMTPProxyServer] Cached token for sender@gmail.com
[SMTPProxyServer] Cached token for sales@outlook.com
...
[SMTPProxyServer] OAuth2 token cache pre-populated
```

### Check via Admin API

Could add endpoint to `/admin/health` or new `/admin/tokens` to show:
- Number of cached tokens
- Cache hit/miss ratio
- Token expiry times

---

## XOAUTH2 String is Generated On-Demand

**Important**: XOAUTH2 strings cannot be pre-generated and cached because:

1. **Different for each message** - mail_from varies per message
2. **Only valid with fresh token** - built from token.access_token
3. **Built just-in-time** (line 114 in upstream.py):
   ```python
   xoauth2_string = f"user={mail_from}\1auth=Bearer {token.access_token}\1\1"
   ```

So the flow is:

```
Pre-cache tokens (✅ What we do on startup)
  ↓
Message arrives
  ↓
Get cached token (✅ Already in memory)
  ↓
Build XOAUTH2 string (✅ Just-in-time with fresh token)
  ↓
Send to Gmail/Outlook
```

**Not**: Pre-generate XOAUTH2 strings (❌ Impossible - don't know mail_from yet)

---

## Summary

**Current State**:
- Tokens are cached with 3600-second TTL
- Token cache only filled on first message or on reload
- Pre-caching only happens on RELOAD, not initial startup

**Proposed Enhancement**:
- Add token pre-caching to initial startup (same code as reload)
- Trade startup time (250ms × N) for faster first message
- XOAUTH2 strings are still generated on-demand (can't be pre-cached)

**Benefit**:
- First message gets cached token (no 250-500ms OAuth2 refresh)
- Consistent latency across all messages
- Better for high-volume senders

