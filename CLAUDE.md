
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Overview

This is a **production-ready XOAUTH2 SMTP proxy for PowerMTA v6** (refactored v2.0). It enables PowerMTA to send emails through Gmail and Outlook accounts using OAuth2 authentication instead of passwords.

**Core Purpose**: Handle real-time OAuth2 token refresh and XOAUTH2 authentication so PowerMTA can relay emails through multiple Gmail/Outlook accounts with dedicated IPs.

**Architecture**: Modular, enterprise-grade Python application with 25+ modules organized by responsibility.

---

## Architecture

### High-Level Flow

```
Your Application Code
    ↓ (SMTP on port 25/587)
PowerMTA (37.27.3.136:25)
    ├─ Receives emails from applications
    └─ Routes to proxy for OAuth2 validation
       ↓ (Internal: port 2525)
XOAUTH2 Proxy (127.0.0.1:2525 or server IP)
    ├─ Validates AUTH PLAIN credentials
    ├─ Refreshes OAuth2 tokens from Microsoft/Google
    ├─ Constructs XOAUTH2 authentication strings
    └─ Returns 235 OK or 454 error to PowerMTA
       ↓
PowerMTA forwards to Gmail/Outlook SMTP servers
    ↓
Gmail/Outlook SMTP (smtp.gmail.com:587, smtp.office365.com:587)
    └─ Email delivered
```

### Modular Architecture (v2.0)

The proxy has been refactored from a monolithic 1100-line script into a professional modular architecture:

```
src/
├── accounts/           # Account management
│   ├── manager.py     # AccountManager - account loading, caching, hot-reload
│   └── models.py      # AccountConfig - account data model
│
├── config/            # Configuration management
│   ├── loader.py      # ConfigLoader - loads and validates accounts.json
│   └── settings.py    # Settings - global proxy settings, environment vars
│
├── logging/           # Logging setup
│   └── setup.py       # Platform-specific log paths, formatters
│
├── admin/             # Admin HTTP API
│   └── server.py      # AdminServer - HTTP API for managing accounts (port 9090)
│
├── oauth2/            # OAuth2 token management
│   ├── manager.py     # OAuth2Manager - token refresh, caching, HTTP pool
│   ├── models.py      # OAuthToken, TokenCache - token data models
│   └── exceptions.py  # Token-related exceptions
│
├── smtp/              # SMTP protocol handling
│   ├── proxy.py       # SMTPProxyServer - main server orchestrator
│   ├── handler.py     # SMTPProxyHandler - asyncio Protocol for SMTP commands
│   ├── upstream.py    # UpstreamRelay - sends messages to Gmail/Outlook SMTP
│   ├── constants.py   # SMTP protocol constants
│   └── exceptions.py  # SMTP-related exceptions
│
├── utils/             # Utilities and resilience patterns
│   ├── circuit_breaker.py  # CircuitBreaker - prevents cascade failures
│   ├── retry.py            # Retry with exponential backoff and jitter
│   ├── rate_limiter.py     # RateLimiter - token bucket algorithm
│   ├── http_pool.py        # HTTPConnectionPool - reusable HTTP sessions
│   ├── connection_pool.py  # Connection pooling utilities
│   └── exceptions.py       # Utility exceptions
│
├── tools/             # Management tools
│   └── add_account.py # Interactive account addition tool
│
├── cli.py             # CLI argument parsing
└── main.py            # Application entry point, signal handlers

add_account.py         # Standalone wrapper for adding accounts

archive/               # Original monolithic implementations
├── xoauth2_proxy.py          # Original 1100-line proxy
├── import_accounts.py        # Account import tool
└── generate_pmta_config.py   # PowerMTA config generator
```

### Key Components

1. **src/main.py** - Application entry point
   - CLI argument parsing
   - Signal handlers (SIGHUP, SIGTERM, SIGINT)
   - Application lifecycle management
   - Cross-platform support (Windows/Linux/macOS)

2. **src/smtp/proxy.py** - SMTPProxyServer
   - Main SMTP server orchestrator
   - Component initialization (accounts, OAuth2, metrics)
   - Async server lifecycle management

3. **src/smtp/handler.py** - SMTPProxyHandler
   - Async SMTP protocol handler (asyncio.Protocol)
   - EHLO/HELO, AUTH PLAIN, MAIL/RCPT/DATA commands
   - Per-connection state machine
   - XOAUTH2 verification

4. **src/smtp/upstream.py** - UpstreamRelay
   - Relays messages to Gmail/Outlook SMTP servers
   - XOAUTH2 authentication with upstream
   - Handles SMTP conversation (EHLO, STARTTLS, AUTH, MAIL, RCPT, DATA)
   - Runs in thread pool executor (blocking SMTP calls)

5. **src/oauth2/manager.py** - OAuth2Manager
   - Token refresh with real HTTP POST requests
   - Provider-specific token refresh (Gmail vs Outlook)
   - Token caching with TTL (default 60s)
   - Retry with exponential backoff
   - Circuit breaker per provider

6. **src/accounts/manager.py** - AccountManager
   - Loads accounts from accounts.json
   - In-memory account cache (email -> AccountConfig)
   - Hot-reload support (SIGHUP signal, not yet wired)
   - Thread-safe account lookups

7. **src/admin/server.py** - AdminServer
   - HTTP API server on port 9090
   - POST /admin/accounts - Add new accounts
   - GET /admin/accounts - List all accounts
   - GET /health - Health check
   - OAuth2 credential verification
   - Automatic hot-reload after adding accounts

8. **src/tools/add_account.py** - Add Account Tool
   - Interactive CLI tool for adding accounts
   - Email validation and OAuth2 verification
   - Supports both Gmail and Outlook
   - Can be run standalone or as module

9. **src/utils/** - Resilience patterns
   - **CircuitBreaker**: Prevents cascading failures to OAuth2/SMTP providers
   - **Retry**: Exponential backoff with jitter for transient failures
   - **RateLimiter**: Token bucket per-account rate limiting
   - **HTTPConnectionPool**: Reusable HTTP sessions for OAuth2 requests

### Entry Points

**Production**: `python xoauth2_proxy_v2.py --config accounts.json --port 2525`
- Thin wrapper that imports `src.main.main()`

**Development**: `python -m src.main --config accounts.json --port 2525`
- Direct module execution

**Installed**: `xoauth2-proxy --config accounts.json --port 2525`
- Console script entry point (via `pip install -e .`)

### Provider-Specific Behavior

**Gmail**:
- OAuth endpoint: `https://oauth2.googleapis.com/token`
- SMTP endpoint: `smtp.gmail.com:587`
- Requires: client_id, client_secret, refresh_token
- Scope: `https://mail.google.com/`

**Outlook**:
- OAuth endpoint: `https://login.microsoftonline.com/common/oauth2/v2.0/token`
- SMTP endpoint: `smtp.office365.com:587`
- Requires: client_id, refresh_token (NO client_secret for some flows)
- Scopes: IMAP.AccessAsUser.All, POP.AccessAsUser.All, SMTP.Send
- Can return updated refresh_token in response (must be persisted)

---

## Common Development Tasks

### Running the Proxy

```bash
# Basic usage (localhost, port 2525)
python xoauth2_proxy_v2.py --config accounts.json

# Bind to all interfaces (for remote PowerMTA)
python xoauth2_proxy_v2.py --config accounts.json --host 0.0.0.0 --port 2525

# Dry-run mode (accept messages but don't send)
python xoauth2_proxy_v2.py --config accounts.json --dry-run

# Custom metrics port
python xoauth2_proxy_v2.py --config accounts.json --metrics-port 9091

# With reduced global concurrency
python xoauth2_proxy_v2.py --config accounts.json --global-concurrency 50
```

### Development Setup

```bash
# Install in development mode
pip install -e .

# Install dependencies
pip install -r requirements.txt

# Run tests
python -m pytest tests/

# Type checking (if mypy configured)
mypy src/

# Run from module
python -m src.main --config accounts.json
```

### Working with Accounts

```bash
# Add a new account interactively (RECOMMENDED)
python add_account.py
# Or: python -m src.tools.add_account
# Or (if installed): xoauth2-add-account

# Add account to custom file
python add_account.py /path/to/accounts.json

# Validate accounts.json
python -c "import json; json.load(open('accounts.json'))"

# Use archived import tool (not yet refactored)
python archive/import_accounts.py -i data.txt -o accounts.json

# Use archived config generator (not yet refactored)
python archive/generate_pmta_config.py accounts.json -o pmta.cfg
```

### Managing Accounts via HTTP API

The proxy includes an HTTP Admin API (port 9090) for managing accounts while the server is running:

```bash
# Add account via HTTP POST (while server is running)
curl -X POST http://127.0.0.1:9090/admin/accounts \
  -H "Content-Type: application/json" \
  -d '{
    "email": "sales@gmail.com",
    "provider": "gmail",
    "client_id": "123456789-abc.apps.googleusercontent.com",
    "client_secret": "GOCSPX-abc123def456",
    "refresh_token": "1//0gABC123DEF456...",
    "verify": true
  }'

# List all accounts
curl http://127.0.0.1:9090/admin/accounts

# Customize admin port
python xoauth2_proxy_v2.py --admin-port 8080

# See docs/ADMIN_API.md for complete API documentation
```

**Benefits:**
- Add accounts without restarting the proxy
- Automatic hot-reload (zero downtime)
- OAuth2 credential verification
- API-first design for automation

### Testing & Monitoring

```bash
# Health check (Admin API)
curl http://127.0.0.1:9090/health
# Response: {"status": "healthy", "service": "xoauth2-proxy-admin"}

# List accounts (Admin API)
curl http://127.0.0.1:9090/admin/accounts

# SMTP test (telnet)
telnet 127.0.0.1 2525
# Type: QUIT

# Full auth test (swaks)
swaks --server 127.0.0.1:2525 \
  --auth-user user@gmail.com \
  --auth-password placeholder \
  --from test@example.com \
  --to recipient@gmail.com
```

### Monitor Logs

```bash
# Linux/macOS
tail -f /var/log/xoauth2/xoauth2_proxy.log

# Windows
Get-Content "$env:TEMP\xoauth2_proxy\xoauth2_proxy.log" -Tail 50 -Wait

# Current directory (fallback)
tail -f xoauth2_proxy.log
```

---

## Important Files

| File | Purpose | Key Points |
|------|---------|-----------|
| `src/main.py` | Application entry point | Signal handlers, lifecycle management |
| `src/smtp/proxy.py` | SMTPProxyServer | Main server orchestrator |
| `src/smtp/handler.py` | SMTPProxyHandler | Async SMTP protocol handler |
| `src/smtp/upstream.py` | UpstreamRelay | Relays to Gmail/Outlook SMTP |
| `src/oauth2/manager.py` | OAuth2Manager | Token refresh, caching, HTTP pool |
| `src/accounts/manager.py` | AccountManager | Account loading, caching |
| `src/config/loader.py` | ConfigLoader | Loads and validates accounts.json |
| `src/admin/server.py` | AdminServer | HTTP API for managing accounts |
| `src/tools/add_account.py` | Add account tool | Interactive account addition |
| `src/utils/circuit_breaker.py` | CircuitBreaker | Prevents cascade failures |
| `src/utils/retry.py` | Retry logic | Exponential backoff with jitter |
| `src/utils/rate_limiter.py` | RateLimiter | Token bucket algorithm |
| `xoauth2_proxy_v2.py` | Entry point wrapper | Thin wrapper for src/main.py |
| `accounts.json` | Account config | OAuth2 credentials per account |
| `example_accounts.json` | Example config | Template for accounts.json |
| `pmta.cfg` | PowerMTA config | Virtual-MTAs and routes |
| `setup.py` | Package setup | pip install support |
| `requirements.txt` | Dependencies | aiosmtpd, requests, prometheus-client |
| `CLAUDE.md` | This file | Development guidance |
| `README.md` | Project README | Quick start, features |
| `QUICK_START.md` | Quick reference | 3-step setup guide |
| `SETUP_ACCOUNTS.md` | Account setup guide | OAuth2 credentials, configuration |
| `docs/ADMIN_API.md` | Admin API guide | HTTP API documentation, examples |
| `docs/ADD_ACCOUNT_GUIDE.md` | Add account guide | Interactive tool usage |
| `docs/DEPLOYMENT_GUIDE.md` | Deployment guide | Production deployment |
| `docs/TEST_PLAN.md` | Test plan | Comprehensive testing |
| `docs/OAUTH2_REAL_WORLD.md` | OAuth2 details | Token refresh flow, examples |
| `docs/CROSS_PLATFORM_SETUP.md` | Platform setup | Windows/Linux/macOS |
| `archive/xoauth2_proxy.py` | Original monolith | 1100-line original implementation |
| `archive/import_accounts.py` | Account importer | CSV → JSON conversion |
| `archive/generate_pmta_config.py` | Config generator | Creates PowerMTA config |

---

## Key Technical Decisions

### Modular Architecture (v2.0)
- **Before**: 1 file (1100+ lines)
- **After**: 25+ modules in `src/`
- **Benefits**: Testability, maintainability, scalability
- **Designed for**: 1000+ accounts, 1000+ req/sec

### Async I/O with asyncio
- **Protocol**: asyncio.Protocol for SMTP handling
- **Executor**: ThreadPoolExecutor for blocking SMTP operations
- **Concurrency**: Per-account and global concurrency limits

### OAuth2 Token Refresh
- Real HTTP POST requests to provider-specific endpoints
- 300-second buffer before expiration to trigger refresh
- Outlook can return updated refresh_token (must be persisted if implementing database storage)
- Automatic retry on network failure, permanent error on invalid credentials

### SMTP Protocol Compliance
- EHLO response includes: AUTH PLAIN, SIZE limit, 8BITMIME
- Server name: "xoauth2-proxy" (can be changed in code for production)
- AUTH PLAIN format: base64(NULL + email + NULL + password)
- Password is ignored by proxy; only email and OAuth2 token matter

### PowerMTA Integration
- Proxy listens on separate port (2525) from PowerMTA (25/587)
- PowerMTA authenticates to proxy before message delivery
- SMTP pattern lists must NOT have empty patterns
- Routes to proxy should use standard SMTP capabilities

### Concurrency Model
- Per-account concurrency limits (default: 10 messages)
- Global concurrency limit (default: 100 messages)
- Asyncio-based for high concurrency on single thread
- No database - in-memory account state (lost on restart)

### Resilience Patterns
- **Circuit Breaker**: Per-provider circuit breakers (OAuth2, SMTP)
- **Retry**: Exponential backoff with jitter for transient failures
- **Rate Limiting**: Token bucket algorithm, per-account
- **Connection Pooling**: HTTP session reuse for OAuth2 requests

### Cross-Platform Support
- **Windows**: Logs to `%TEMP%\xoauth2_proxy\`, no SIGHUP support
- **Linux/macOS**: Logs to `/var/log/xoauth2/`, SIGHUP support
- **Fallback**: Current directory if standard paths unavailable
- **Smart config discovery**: tries exact path → current directory → standard OS locations

### Async I/O & Threading Model

**Critical Pattern** (affects all SMTP handler code):
- **Main event loop**: `asyncio` running in `src/smtp/handler.py` (asyncio.Protocol)
- **Blocking operations**: Run in `ThreadPoolExecutor` to avoid blocking the event loop
  - Upstream SMTP relay (sending to Gmail/Outlook) - runs in executor
  - Synchronous network operations - run in executor
- **Per-email locking**: `AccountManager.get_token()` uses per-email locks to prevent race conditions on token refresh

**Concurrency Model**:
```
┌─ asyncio event loop (single-threaded)
│  ├─ SMTP protocol handling (async)
│  ├─ OAuth2 HTTP requests (async via aiohttp)
│  ├─ Admin API (async via aiohttp)
│  └─ Executor submission (async submission of blocking ops)
│
└─ ThreadPoolExecutor (default: 5 workers)
   └─ Upstream SMTP relay (blocking SMTPlib)
```

When modifying code:
- Keep `src/smtp/handler.py` async (never use blocking calls directly)
- Use `loop.run_in_executor()` for blocking I/O
- Use `asyncio.Lock` for coordination between coroutines
- Use `threading.Lock` for cross-thread coordination

---

## Code Organization Patterns

### Where to Find Things

| Goal | Location | Files |
|------|----------|-------|
| **Fix SMTP protocol bugs** | `src/smtp/` | `handler.py` (command parsing), `constants.py` (responses) |
| **Fix OAuth2 token issues** | `src/oauth2/` | `manager.py` (refresh logic), `models.py` (token models) |
| **Fix account loading/caching** | `src/accounts/` | `manager.py` (cache logic), `models.py` (AccountConfig structure) |
| **Fix authentication failures** | `src/smtp/handler.py` | `auth_plain_handler()` method (~line 200-250) |
| **Add features to Admin API** | `src/admin/server.py` | HTTP endpoints and request handlers |
| **Fix message relay issues** | `src/smtp/upstream.py` | Upstream SMTP conversation flow |
| **Add configuration options** | `src/config/` | `settings.py` (global), `loader.py` (file loading) |
| **Add new tools** | `src/tools/` | Standalone CLI tools |
| **Fix resilience patterns** | `src/utils/` | `circuit_breaker.py`, `retry.py`, `rate_limiter.py` |

### Common Code Patterns

**Token Refresh (async)**:
```python
# In src/smtp/handler.py, OAuth2Manager
token = await oauth2_manager.get_or_refresh_token(email)  # May block on per-email lock
auth_string = oauth2_manager.build_xoauth2_string(email, token)
```

**Account Lookup (thread-safe)**:
```python
# In src/smtp/handler.py, AccountManager
account = account_manager.get_account(email)  # Thread-safe in-memory lookup
if not account:
    return INVALID_ACCOUNT_RESPONSE
```

**Retry with Exponential Backoff**:
```python
# In src/utils/retry.py
result = await retry(
    func=some_async_function,
    max_attempts=3,
    initial_delay=1.0,
    max_delay=10.0
)
```

**Circuit Breaker (prevent cascade failures)**:
```python
# In src/utils/circuit_breaker.py
breaker = CircuitBreaker(failure_threshold=5, timeout_seconds=60)
try:
    result = await breaker.call(async_function)
except BreakerOpenException:
    # Provider is failing, return cached or error
    pass
```

**Logging with Context**:
```python
logger.info(f"AUTH successful for {email}", extra={"account_id": account.account_id})
```

### Module Dependencies

```
src/main.py
    ├─ src/cli.py (argument parsing)
    ├─ src/config/settings.py (config discovery)
    ├─ src/logging/setup.py (logging initialization)
    └─ src/smtp/proxy.py (start SMTP server)
         ├─ src/accounts/manager.py (load accounts)
         ├─ src/oauth2/manager.py (token management)
         ├─ src/admin/server.py (HTTP API)
         └─ src/smtp/handler.py (protocol handler)
              ├─ src/smtp/upstream.py (relay to providers)
              ├─ src/utils/circuit_breaker.py
              ├─ src/utils/retry.py
              └─ src/utils/rate_limiter.py
```

**Dependency rule**: No circular imports. Lower modules (utils) don't import higher modules (smtp, accounts).

---

## Critical Issues & Fixes

### SMTP Endpoint Configuration (FIXED in v2.0)
**Problem**: `oauth_endpoint` field must be the SMTP server endpoint, not the OAuth authorization URL.

**Solution**: Use SMTP endpoints in accounts.json:
```json
"oauth_endpoint": "smtp.gmail.com:587"        // ✅ Gmail
"oauth_endpoint": "smtp.office365.com:587"    // ✅ Outlook
```

**NOT** authorization URLs:
```json
"oauth_endpoint": "https://oauth2.googleapis.com"  // ❌ WRONG
```

### Datetime Deprecation (Python 3.12+)
**Problem**: `datetime.utcnow()` deprecated.

**Solution**: Use `datetime.now(UTC)` (import `UTC` from datetime module). ✅ Fixed in v2.0

### Windows Signal Handling
**Problem**: `signal.SIGHUP` doesn't exist on Windows.

**Solution**: Check `platform.system() != "Windows"` before registering SIGHUP handler. ✅ Fixed in v2.0

---

## CLI Arguments & Configuration

### Primary Command-Line Arguments

The proxy accepts these key arguments (parsed in `src/cli.py`):

```bash
# Configuration files
--config CONFIG_PATH          # Path to config.json (global settings, default: config.json)
--accounts ACCOUNTS_PATH      # Path to accounts.json (credentials, default: accounts.json)

# Server binding
--host HOST                   # Listen host (default: 127.0.0.1, use 0.0.0.0 for remote)
--port PORT                   # Listen port (default: 2525)

# Admin HTTP API
--admin-host HOST             # Admin server host (default: 0.0.0.0, use 127.0.0.1 for local-only)
--admin-port PORT             # Admin server port (default: 9090)

# Performance tuning
--global-concurrency N        # Global message concurrency limit (default: 100)

# Operating modes
--dry-run                     # Test mode: accept messages but don't send them
```

### Configuration Path Discovery

Both `--config` and `--accounts` paths use smart discovery (in `Settings.get_config_path()`):
1. Try exact path as specified
2. Fall back to current working directory
3. Fall back to platform-specific standard locations:
   - **Linux/macOS**: `/etc/xoauth2/`, `/var/lib/xoauth2/`
   - **Windows**: `%APPDATA%\xoauth2-proxy\`, `%PROGRAMDATA%\xoauth2-proxy\`

This allows flexible deployment without hardcoding paths.

### Common Invocation Patterns

**Development (localhost only)**:
```bash
python xoauth2_proxy_v2.py --config examples/example_config.json --accounts accounts.json
```

**Production (remote PowerMTA)**:
```bash
python xoauth2_proxy_v2.py --host 0.0.0.0 --port 2525 --admin-host 127.0.0.1
```

**High-volume (1000+ msg/sec)**:
```bash
python xoauth2_proxy_v2.py --global-concurrency 1000 --admin-host 127.0.0.1
```

**Testing mode (no actual sends)**:
```bash
python xoauth2_proxy_v2.py --dry-run
```

**Custom ports**:
```bash
python xoauth2_proxy_v2.py --port 2525 --admin-port 8080
```

### Debugging Tips

**Enable verbose logging**:
```python
# In src/logging/setup.py, temporarily change:
logging.basicConfig(level=logging.DEBUG)  # Instead of INFO
```

**Monitor token refresh**:
```bash
# Watch for token refresh attempts in logs
tail -f /var/log/xoauth2/xoauth2_proxy.log | grep "refresh"
```

**Test OAuth2 manually**:
```bash
curl -X POST https://oauth2.googleapis.com/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "client_id=YOUR_ID&client_secret=YOUR_SECRET&refresh_token=YOUR_TOKEN&grant_type=refresh_token"
```

**Inspect account cache**:
```bash
curl http://127.0.0.1:9090/admin/accounts
```

**Test SMTP connection without auth**:
```bash
openssl s_client -connect localhost:2525
# Type: QUIT
```

**Check network limits**:
```bash
# Linux: check file descriptor limits
ulimit -n
# Should be high (65536+) for 1000+ concurrent connections
```

### Configuration File Structure

#### **config.json** (Global Settings)

Loaded by `ConfigLoader` in `src/config/loader.py`. Controls global proxy behavior:

```json
{
  "logging": {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  },
  "providers": {
    "gmail": {
      "smtp_endpoint": "smtp.gmail.com:587",
      "oauth_endpoint": "https://oauth2.googleapis.com/token",
      "max_connections_per_account": 40,
      "rate_limit_per_hour": 10000,
      "token_refresh_buffer_seconds": 300,
      "timeout_seconds": 30
    },
    "outlook": {
      "smtp_endpoint": "smtp.office365.com:587",
      "oauth_endpoint": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
      "max_connections_per_account": 30,
      "rate_limit_per_hour": 10000,
      "token_refresh_buffer_seconds": 300,
      "timeout_seconds": 30
    }
  },
  "connection_pool": {
    "http_pool_size": 100,
    "max_idle_time_seconds": 300,
    "max_connection_age_seconds": 3600
  }
}
```

Key tuning parameters:
- `max_connections_per_account`: Per-account SMTP connection limit
- `rate_limit_per_hour`: Per-account message rate limit
- `token_refresh_buffer_seconds`: Refresh token before this many seconds to expiration (300s = 5min buffer)
- `http_pool_size`: Reusable HTTP connections for OAuth2 requests

#### **accounts.json** (Account Credentials)

Array of account objects (loaded by `ConfigLoader` in `src/config/loader.py`, cached by `AccountManager`):

```json
[
  {
    "account_id": "gmail-1",
    "email": "sales@gmail.com",
    "provider": "gmail",
    "client_id": "123456789-abc.apps.googleusercontent.com",
    "client_secret": "GOCSPX-abc123def456",
    "refresh_token": "1//0gABC123DEF456...",
    "ip_address": "192.168.1.100",
    "vmta_name": "gmail-relay-1",
    "max_concurrent_messages": 10,
    "max_messages_per_hour": 5000
  },
  {
    "account_id": "outlook-1",
    "email": "support@outlook.com",
    "provider": "outlook",
    "client_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "refresh_token": "0.AYXXX...",
    "ip_address": "192.168.1.101",
    "vmta_name": "outlook-relay-1"
  }
]
```

Required fields per account:
- `email`, `provider` (gmail/outlook), `client_id`, `refresh_token`
- `oauth_endpoint` (optional, defaults from config.json)

Optional fields:
- `account_id`: For tracking/logging
- `ip_address`, `vmta_name`: For PowerMTA integration (stored in account object)
- `max_concurrent_messages`, `max_messages_per_hour`: Per-account overrides

**⚠️ IMPORTANT**: Accounts.json contains OAuth2 secrets and should be:
- Added to `.gitignore` (do not commit)
- Protected with restrictive file permissions (600)
- Loaded from secure location in production

---

## Testing Strategy

### Unit-Level Testing
- Validate `accounts.json` with `python -m json.tool accounts.json`
- Run tests: `python -m pytest tests/`
- Syntax check: `python -m py_compile src/**/*.py`

### Integration Testing
1. Start proxy: `python xoauth2_proxy_v2.py --accounts accounts.json`
2. Health check: `curl http://127.0.0.1:9090/health`
3. List accounts: `curl http://127.0.0.1:9090/admin/accounts`
4. Auth test: `swaks --server 127.0.0.1:2525 --auth-user <email> ...`

### Production Testing (with PowerMTA)
1. Configure PowerMTA routes to proxy (port 2525)
2. Start proxy on production IP (use `--host 0.0.0.0` for external access)
3. Start PowerMTA
4. Send test email via PowerMTA: `swaks --server <pmta_ip>:25 --from ... --to ...`
5. Verify in proxy logs: "AUTH successful", "Message relayed"

---

## Connection Pool Pre-warming & Periodic Re-warming

### Overview

To achieve **<100ms latency on burst traffic**, the proxy uses two techniques:

1. **Initial Pre-warming**: Creates connections upfront at startup
2. **Periodic Re-warming**: Maintains ready connections during idle periods

### Configuration

Add these fields to your `config.json` under each provider's `connection_pool` section:

```json
{
  "providers": {
    "gmail": {
      "connection_pool": {
        "max_connections_per_account": 40,
        "prewarm_percentage": 50,
        "periodic_rewarm_enabled": true,
        "periodic_rewarm_interval_seconds": 300
      }
    }
  }
}
```

**Key Parameters:**

- **prewarm_percentage** (default: 50)
  - Percentage of `max_connections_per_account` to create at startup
  - 40 max → 20 connections pre-warmed (50%)
  - Tune for your use case:
    - Light traffic: 25% (minimal resource usage)
    - Normal: 50% (balanced approach)
    - High volume: 100% (warm to max at startup)

- **periodic_rewarm_enabled** (default: true)
  - Enable periodic re-warming to handle idle timeout gaps
  - Maintains connections even after 60-120 second idle periods

- **periodic_rewarm_interval_seconds** (default: 300)
  - How often to re-warm (300 seconds = 5 minutes)
  - Tune based on your burst frequency:
    - Frequent bursts (< 2 min apart): 60 seconds
    - Normal bursts (2-10 min apart): 300 seconds
    - Infrequent bursts (> 10 min apart): 600 seconds

### Performance Impact

**Initial Pre-warming:**
- Creates 50% of max_connections in parallel at startup
- Time: ~2 seconds for 10 accounts (50 connections)
- Eliminates cold-start lag on first message burst

**Periodic Re-warming:**
- Maintains connections across idle gaps
- Uses cached tokens (no OAuth2 overhead!)
- Speed: 400-700ms vs 700-1200ms without token cache
- Runs in background every 5 minutes (configurable)

### How It Works

1. **At Startup:**
   - Load config with `prewarm_percentage: 50`
   - Create 50% of connections for each account in parallel
   - Use cached tokens for authentication
   - Ready for burst traffic immediately

2. **During Idle (60-120 seconds):**
   - Connections timeout and drain from pool
   - Pool becomes empty temporarily

3. **Periodic Re-warming (every 5 minutes):**
   - Background task kicks in
   - Creates fresh connections to 50% capacity
   - Uses still-valid cached tokens (fast!)
   - Next burst finds ready connections

4. **On Burst Arrival:**
   - Pool has pre-warmed connections available
   - First message sends within <100ms
   - No waiting for TCP/TLS/AUTH handshakes

### Real-World Example

**Scenario:** 10 accounts, bursts every 1-2 hours, 10k messages per burst

**Configuration:**
```json
"connection_pool": {
  "max_connections_per_account": 40,
  "prewarm_percentage": 50,
  "periodic_rewarm_enabled": true,
  "periodic_rewarm_interval_seconds": 300
}
```

**Results:**
- Startup: Pre-warm creates 20 connections per account (200 total) in ~2 seconds ✅
- After 60s idle: Connections timeout (expected)
- After 5 minutes idle: Re-warm creates fresh 20 connections per account ✅
- 1-2 hour mark: Burst arrives to pool with 20 ready connections per account
- First message: <100ms latency ✅
- Subsequent messages: Reuse existing connections, 10-100ms latency

### Tuning Guide

| Use Case | prewarm_percentage | periodic_rewarm_interval_seconds | Notes |
|----------|-------------------|----------------------------------|-------|
| Light traffic (< 100/hour) | 25 | 600 | Minimal memory, low latency still good |
| Normal (100-1000/hour) | 50 | 300 | Default, balanced |
| High volume (1000+/hour) | 75-100 | 60 | Frequent re-warming, high throughput |
| Bursty (10k every 2h) | 50 | 300 | Re-warm before expected bursts |

---

## Dependencies

Main dependencies (from `requirements.txt`):
```
aiosmtplib>=3.0.0  - Async SMTP client for upstream relay (send to Gmail/Outlook)
aiohttp>=3.8.0     - Async HTTP client for OAuth2 token refresh and Admin API
netifaces>=0.11.0  - Network interface enumeration (optional, for IP selection)
```

Install with:
```bash
pip install -r requirements.txt

# Or install in development mode with entry points
pip install -e .
```

**Note**: `aiosmtpd` is referenced in comments but not actually used in v2.0 (it's an old implementation detail).

---

## Message Sending

**Important**: Your code should connect to **PowerMTA (port 25)**, not the proxy (port 2525).

```python
import smtplib
from email.mime.text import MIMEText

# Connect to PowerMTA, not proxy
server = smtplib.SMTP("37.27.3.136", 25)
server.ehlo()
server.login("email@hotmail.com", "placeholder")

# Create and send message
msg = MIMEText("Hello World")
msg['Subject'] = "Test"
msg['From'] = "email@hotmail.com"
msg['To'] = "recipient@gmail.com"

server.sendmail("email@hotmail.com", "recipient@gmail.com", msg.as_string())
server.quit()
```

The proxy is **internal to PowerMTA** - your code only connects to PowerMTA port 25/587. PowerMTA internally routes authentication to the proxy on port 2525.

---

## Future Enhancements

### Planned (Backlog)
- Wire up hot-reload functionality (SIGHUP handler to AccountManager.reload())
- Refactor `archive/import_accounts.py` into `src/tools/`
- Refactor `archive/generate_pmta_config.py` into `src/tools/`
- Add CLI commands for account import and config generation
- Add database support for account persistence (PostgreSQL, MySQL)
- Add distributed tracing (OpenTelemetry)
- Add TLS/SSL support for proxy <-> PowerMTA communication
- Expand test coverage to 70%+ with integration tests
- Add mypy type checking to CI/CD

---

## Documentation

- **README.md**: Quick start, features, installation
- **QUICK_START.md**: 3-step quick reference
- **SETUP_ACCOUNTS.md**: Account setup guide, OAuth2 credentials
- **REFACTORING_COMPLETE.md**: Refactoring summary, before/after comparison
- **docs/DEPLOYMENT_GUIDE.md**: Production deployment steps
- **docs/TEST_PLAN.md**: Comprehensive testing procedures
- **docs/OAUTH2_REAL_WORLD.md**: OAuth2 implementation details
- **docs/CROSS_PLATFORM_SETUP.md**: Platform-specific installation
- **docs/GMAIL_OUTLOOK_SETUP.md**: Gmail and Outlook OAuth2 setup
- **docs/IMPORT_ACCOUNTS_README.md**: Detailed import tool documentation
- **docs/QUICK_IMPORT_GUIDE.md**: Quick account import guide

---

---

## Guidelines for Claude Code Sessions

### Documentation File Creation

**⚠️ IMPORTANT**: Do NOT create new `.md` documentation files unless explicitly requested by the user.

**Rule**:
- Focus on **code changes and problem solving**, not documentation
- Only create `.md` files if the user specifically asks for them
- Use existing documentation (README.md, docs/) for reference
- Ask the user before creating new docs files

**Why**:
- Excessive `.md` files clutter the repository
- Code speaks for itself; focus on making it clear and correct
- Users can request docs if they need them
- Commit messages are sufficient for tracking changes

**When to Create Docs**:
1. User explicitly requests: "Create a guide for..."
2. User asks: "Document how to..."
3. User wants a README for a new tool/feature
4. Otherwise: **Ask first** before creating new `.md` files

**When NOT to Create Docs**:
- ❌ Don't create summary files for each feature
- ❌ Don't create quick-start guides automatically
- ❌ Don't create troubleshooting guides without asking
- ❌ Don't create INDEX.md or navigation files
- ❌ Don't create CHANGELOG or version history files

**Existing Documentation**:
- README.md - Main project overview
- QUICK_START.md - 3-step setup
- docs/ - Feature-specific documentation
- CLAUDE.md - This file, development guidance

Use these instead of creating new files. Update them if needed.

---

## Version History

**v2.0** (Current - November 2025)
- ✅ Refactored to modular architecture (25+ modules)
- ✅ Fixed oauth_endpoint configuration bug
- ✅ Added resilience patterns (circuit breaker, retry, rate limiting)
- ✅ Improved observability (Prometheus metrics, structured logging)
- ✅ Cross-platform support (Windows/Linux/macOS)
- ✅ Production-ready for 100-500 accounts
- ✅ Performance Phase 1 fixes (2-5x improvement, 50-150 req/s)
- ✅ Connection pool restructuring (O(1) lookups instead of O(n))
- ✅ Load testing tools (test_smtp_load.py, test_smtp_scenarios.py)
- ✅ Mock token caching (instant testing without real credentials)
- ✅ Real provider testing (test_provider_throughput.py, test_ultra_high_throughput.py)
- ✅ Graceful Ctrl+C shutdown for all test tools

**v1.0** (Original - 2024)
- ✅ Monolithic implementation (1100 lines)
- ✅ OAuth2 token refresh for Gmail and Outlook
- ✅ XOAUTH2 SMTP proxy
- ✅ Basic metrics and logging
