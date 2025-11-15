# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Overview

This is a **production-ready XOAUTH2 SMTP proxy for PowerMTA v6**. It enables PowerMTA to send emails through Gmail and Outlook accounts using OAuth2 authentication instead of passwords.

**Core Purpose**: Handle real-time OAuth2 token refresh and XOAUTH2 authentication so PowerMTA can relay emails through multiple Gmail/Outlook accounts with dedicated IPs.

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

### Key Components

1. **xoauth2_proxy.py** (1100+ lines)
   - **Main SMTP server**: Async protocol handler listening on port 2525
   - **OAuth2 token refresh**: Real HTTP POST requests to Google/Microsoft endpoints
   - **Account management**: Loads accounts from `accounts.json`, supports hot-reload via SIGHUP
   - **Cross-platform support**: Automatic OS detection, platform-specific log paths
   - **Prometheus metrics**: Counters/gauges for monitoring auth, tokens, connections
   - **HTTP metrics server**: Exposes metrics on port 9090

2. **import_accounts.py** (300+ lines)
   - Converts CSV account data to `accounts.json`
   - Auto-detects provider (Gmail vs Outlook) from email domain
   - Auto-generates IP addresses (192.168.1.100+)
   - Validates for duplicate emails/account IDs
   - Supports batch import with error handling

3. **generate_pmta_config.py** (280+ lines)
   - Generates complete PowerMTA configuration from `accounts.json`
   - Creates virtual-MTAs with dedicated IPs
   - Creates routes pointing to proxy on port 2525
   - Validates generated config syntax
   - Optional PMTA reload via external command

4. **accounts.json**
   - Account configuration (20 accounts: 10 Gmail, 10 Outlook)
   - Per-account: email, client_id, refresh_token, provider type, IP address
   - Provider-specific OAuth endpoints (Gmail vs Outlook use different token URLs)
   - Rate limits (max_concurrent_messages, max_messages_per_hour)

5. **pmta.cfg**
   - PowerMTA configuration with 20 virtual-MTAs
   - Routes for gmail.com and outlook.com domains
   - Each route points to proxy (127.0.0.1:2525 for same server, or IP:2525 for remote)
   - SMTP pattern lists to avoid matching empty patterns (critical: `/^220 .*/` only)

### Provider-Specific Behavior

**Gmail**:
- OAuth endpoint: `https://oauth2.googleapis.com/token`
- Requires: client_id, client_secret, refresh_token
- Scope: `https://mail.google.com/`

**Outlook**:
- OAuth endpoint: `https://login.live.com/oauth20_token.srf`
- Requires: client_id, refresh_token (NO client_secret)
- Scopes: IMAP.AccessAsUser.All, POP.AccessAsUser.All, SMTP.Send
- Can return updated refresh_token in response (must be persisted)

---

## Common Development Tasks

### Import Multiple Accounts

```bash
# Create data file (format: email,account_id,refresh_token,client_id)
cat > accounts_data.txt << 'EOF'
user1@gmail.com,acc1,1//0gJA7asfdZKRE8z...,558976430978-xxx.apps.googleusercontent.com
user2@outlook.com,acc2,M.C519_BAY.0.U.-Cuf!...,9e5f94bc-e8a4-4e73-b8be-63364c29d753
EOF

# Import
python import_accounts.py -i accounts_data.txt -o accounts.json

# Verify
cat accounts.json | python -m json.tool
```

### Start Proxy

```bash
# Development (localhost, all debug logging)
python xoauth2_proxy.py --config accounts.json --host 0.0.0.0 --port 2525

# With custom port
python xoauth2_proxy.py --config accounts.json --port 2526 --metrics-port 9091

# Dry-run mode (accept messages but don't send)
python xoauth2_proxy.py --config accounts.json --dry-run

# With reduced global concurrency
python xoauth2_proxy.py --config accounts.json --global-concurrency 50
```

### Generate PowerMTA Config

```bash
# Basic generation
python generate_pmta_config.py accounts.json -o pmta_generated.cfg

# With validation
python generate_pmta_config.py accounts.json -o pmta.cfg --validate-only

# With PMTA reload
python generate_pmta_config.py accounts.json -o pmta.cfg --reload
```

### Test Proxy Health

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
# Windows
Get-Content "$env:TEMP\xoauth2_proxy\xoauth2_proxy.log" -Tail 50

# Linux/macOS
tail -f /var/log/xoauth2/xoauth2_proxy.log
```

### Hot-Reload Accounts

```bash
# Update accounts.json with new accounts

# Signal proxy to reload (Unix only)
kill -SIGHUP <proxy_pid>

# Or restart on Windows (SIGHUP not available)
# Kill proxy and restart manually
```

---

## Key Technical Decisions

### Cross-Platform Path Handling
- Windows: Logs to `%TEMP%\xoauth2_proxy\`, fallback to current directory
- Linux/macOS: Logs to `/var/log/xoauth2/`, fallback to current directory
- Smart config file discovery: tries exact path → current directory → standard OS locations

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
- SMTP pattern lists must NOT have empty patterns (`reply // mode=backoff` causes backoff for all responses)
- Routes to proxy should use standard SMTP capabilities (no custom extensions)

### Concurrency Model
- Per-account concurrency limits (default: 10 messages)
- Global concurrency limit (default: 100 messages)
- Asyncio-based for high concurrency on single thread
- No database - in-memory account state (lost on restart)

---

## Important Files

| File | Purpose | Key Points |
|------|---------|-----------|
| `xoauth2_proxy.py` | Main proxy | Async SMTP server, OAuth2 refresh, metrics |
| `import_accounts.py` | Account importer | CSV → JSON conversion, provider detection |
| `generate_pmta_config.py` | Config generator | Creates PMTA virtual-MTAs and routes |
| `accounts.json` | Account config | Format: array of account objects |
| `pmta.cfg` | PMTA config | Must have smtp-pattern-list with safe patterns |
| `QUICK_START.md` | Quick reference | 3-step setup guide |
| `IMPORT_ACCOUNTS_README.md` | Import tool docs | Detailed import instructions |
| `OAUTH2_REAL_WORLD.md` | OAuth2 details | Token refresh flow, examples |
| `CROSS_PLATFORM_SETUP.md` | Platform setup | Windows/Linux/macOS specific |

---

## Critical Issues & Fixes

### Empty SMTP Pattern List Bug
**Problem**: PowerMTA config with `reply // mode=backoff` causes all responses to trigger backoff mode, including successful "220" banner.

**Solution**: Remove empty pattern or use specific error codes only:
```cfg
<smtp-pattern-list safe-errors>
    reply /^421 .*/ mode=backoff
    reply /^450 .*/ mode=backoff
    reply /^500 .*/ mode=backoff
    reply /^550 .*/ mode=backoff
</smtp-pattern-list>
```

### Datetime Deprecation (Python 3.12+)
**Problem**: `datetime.utcnow()` deprecated.

**Solution**: Use `datetime.now(UTC)` (import `UTC` from datetime module).

### Windows Signal Handling
**Problem**: `signal.SIGHUP` doesn't exist on Windows.

**Solution**: Check `platform.system() != "Windows"` before registering SIGHUP handler.

### Unicode on Windows Console
**Problem**: Unicode characters (✓) cause UnicodeEncodeError on Windows console (cp1252 encoding).

**Solution**: Use ASCII alternatives like `[OK]` instead of `✓`.

---

## Testing Strategy

### Unit-Level Testing
- Validate `accounts.json` with `python -m json.tool`
- Test import: `python import_accounts.py --validate-only`
- Generate PMTA config: `python generate_pmta_config.py accounts.json --validate-only`

### Integration Testing
1. Start proxy: `python xoauth2_proxy.py --config accounts.json`
2. Health check: `curl http://127.0.0.1:9090/health`
3. Metrics: `curl http://127.0.0.1:9090/metrics | grep token_`
4. Auth test: `swaks --server 127.0.0.1:2525 --auth-user <email> ...`

### Production Testing (with PowerMTA)
1. Configure PowerMTA routes to proxy (port 2525)
2. Start proxy on production IP (use `--host 0.0.0.0` for external access)
3. Start PowerMTA
4. Send test email via PowerMTA: `swaks --server <pmta_ip>:25 --from ... --to ...`
5. Verify in proxy logs: "AUTH successful", "Message delivered"

---

## Dependencies

```
prometheus-client  - Metrics collection
requests          - OAuth2 HTTP requests
```

Install with:
```bash
pip install prometheus-client requests
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

## Documentation

- **QUICK_START.md**: 3-step quick reference
- **QUICK_IMPORT_GUIDE.md**: Account import guide
- **IMPORT_ACCOUNTS_README.md**: Detailed import tool documentation
- **OAUTH2_REAL_WORLD.md**: OAuth2 implementation details
- **CROSS_PLATFORM_SETUP.md**: Platform-specific installation
- **DEPLOYMENT_GUIDE.md**: Production deployment steps
- **TEST_PLAN.md**: Comprehensive testing procedures
