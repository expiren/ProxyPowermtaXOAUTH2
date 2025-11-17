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
├── metrics/           # Prometheus metrics
│   ├── collector.py   # MetricsCollector - counters, gauges, histograms
│   └── server.py      # MetricsServer - HTTP server on port 9090
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

7. **src/metrics/server.py** - MetricsServer
   - HTTP server on port 9090
   - Exposes Prometheus metrics at /metrics
   - Health check at /health

8. **src/utils/** - Resilience patterns
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

### Testing & Monitoring

```bash
# Health check
curl http://127.0.0.1:9090/health
# Response: {"status": "healthy"}

# Metrics
curl http://127.0.0.1:9090/metrics | grep auth_attempts

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
| `src/metrics/server.py` | MetricsServer | Prometheus metrics HTTP server |
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

## Testing Strategy

### Unit-Level Testing
- Validate `accounts.json` with `python -m json.tool accounts.json`
- Run tests: `python -m pytest tests/`
- Syntax check: `python -m py_compile src/**/*.py`

### Integration Testing
1. Start proxy: `python xoauth2_proxy_v2.py --config accounts.json`
2. Health check: `curl http://127.0.0.1:9090/health`
3. Metrics: `curl http://127.0.0.1:9090/metrics | grep token_`
4. Auth test: `swaks --server 127.0.0.1:2525 --auth-user <email> ...`

### Production Testing (with PowerMTA)
1. Configure PowerMTA routes to proxy (port 2525)
2. Start proxy on production IP (use `--host 0.0.0.0` for external access)
3. Start PowerMTA
4. Send test email via PowerMTA: `swaks --server <pmta_ip>:25 --from ... --to ...`
5. Verify in proxy logs: "AUTH successful", "Message relayed"

---

## Dependencies

```
aiosmtpd>=1.4.4         - Async SMTP server library (not used in v2.0, replaced with asyncio.Protocol)
requests>=2.28.0         - OAuth2 HTTP requests
prometheus-client>=0.15.0 - Metrics collection
```

Install with:
```bash
pip install -r requirements.txt
```

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

## Version History

**v2.0** (Current - November 2025)
- ✅ Refactored to modular architecture (25+ modules)
- ✅ Fixed oauth_endpoint configuration bug
- ✅ Added resilience patterns (circuit breaker, retry, rate limiting)
- ✅ Improved observability (Prometheus metrics, structured logging)
- ✅ Cross-platform support (Windows/Linux/macOS)
- ✅ Production-ready for 100-500 accounts

**v1.0** (Original - 2024)
- ✅ Monolithic implementation (1100 lines)
- ✅ OAuth2 token refresh for Gmail and Outlook
- ✅ XOAUTH2 SMTP proxy
- ✅ Basic metrics and logging
