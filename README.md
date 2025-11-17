# XOAUTH2 Proxy for PowerMTA & Outlook/Gmail SMTP

A production-ready, modular SMTP proxy that bridges PowerMTA with Office 365/Outlook and Gmail SMTP servers using OAuth2 authentication (XOAUTH2 protocol).

**Version**: 2.0 (Refactored)
**Status**: Production-Ready
**Scale**: 100-500 accounts, 1000+ req/sec capable

---

## Features

- **OAuth2 Token Management**: Automatic token refresh with 300-second expiration buffer
- **Full XOAUTH2 Protocol**: RFC 7628 compliant SMTP authentication
- **Complete SMTP Support**: EHLO/HELO, AUTH PLAIN, MAIL/RCPT/DATA, RSET, QUIT
- **Asynchronous I/O**: Built on asyncio for high concurrency
- **Resilience Patterns**:
  - Circuit breaker per provider (prevents cascade failures)
  - Retry with exponential backoff and jitter
  - Token bucket rate limiting per account
  - HTTP connection pooling for OAuth2 requests
- **Observability**:
  - Prometheus metrics (auth attempts, token refresh, message relay, errors)
  - Structured logging with context
  - Health check endpoint
- **Cross-Platform**: Windows, Linux, macOS support
- **Modular Architecture**: 25+ modules for testability and maintainability

---

## Architecture

### Modular Structure (v2.0)

```
src/
├── accounts/      # Account management (loading, caching, hot-reload)
├── config/        # Configuration loading and settings
├── logging/       # Platform-specific logging setup
├── metrics/       # Prometheus metrics server and collectors
├── oauth2/        # OAuth2 token management (refresh, caching, HTTP pool)
├── smtp/          # SMTP protocol (server, handler, upstream relay)
└── utils/         # Utilities (circuit breaker, retry, rate limiter)
```

### Message Flow

```
Your Application
    ↓
PowerMTA (port 25/587)
    ↓
XOAUTH2 Proxy (port 2525)
    ├─ AUTH PLAIN validation
    ├─ OAuth2 token refresh
    └─ XOAUTH2 authentication
    ↓
Gmail/Outlook SMTP (smtp.gmail.com:587, smtp.office365.com:587)
    ↓
Email Delivered
```

---

## Installation

### Quick Install

```bash
# Clone repository
git clone https://github.com/yourusername/ProxyPowermtaXOAUTH2.git
cd ProxyPowermtaXOAUTH2

# Install dependencies
pip install -r requirements.txt

# Or install as package (recommended)
pip install -e .
```

### Requirements

- Python 3.8+
- `requests` - OAuth2 HTTP requests
- `prometheus-client` - Metrics collection

---

## Configuration

### 1. Create accounts.json

```bash
cp example_accounts.json accounts.json
# Edit accounts.json with your OAuth2 credentials
```

**Example accounts.json**:

```json
[
  {
    "account_id": "gmail_account_001",
    "email": "sender001@gmail.com",
    "ip_address": "192.168.1.101",
    "vmta_name": "vmta_gmail_01",
    "provider": "gmail",
    "client_id": "YOUR_CLIENT_ID.apps.googleusercontent.com",
    "client_secret": "YOUR_CLIENT_SECRET",
    "refresh_token": "YOUR_REFRESH_TOKEN",
    "oauth_endpoint": "smtp.gmail.com:587",
    "oauth_token_url": "https://oauth2.googleapis.com/token",
    "max_concurrent_messages": 10,
    "max_messages_per_hour": 10000
  },
  {
    "account_id": "outlook_account_001",
    "email": "sender001@outlook.com",
    "ip_address": "192.168.1.201",
    "vmta_name": "vmta_outlook_01",
    "provider": "outlook",
    "client_id": "YOUR_CLIENT_ID",
    "client_secret": "YOUR_CLIENT_SECRET",
    "refresh_token": "YOUR_REFRESH_TOKEN",
    "oauth_endpoint": "smtp.office365.com:587",
    "oauth_token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
    "max_concurrent_messages": 10,
    "max_messages_per_hour": 10000
  }
]
```

**Required Fields**:
- `account_id` - Unique identifier
- `email` - Email address
- `provider` - "gmail" or "outlook"
- `client_id`, `client_secret`, `refresh_token` - OAuth2 credentials
- `oauth_endpoint` - SMTP server (host:port)
- `oauth_token_url` - OAuth2 token refresh URL

See `SETUP_ACCOUNTS.md` for detailed setup instructions and obtaining OAuth2 credentials.

### 2. Configure PowerMTA (Optional)

If using PowerMTA, configure routes to point to the proxy:

```
<route gmail-user1>
  virtual-mta vmta_gmail_01
  domain gmail.com
  smtp-host 127.0.0.1 port=2525
  auth-username sender001@gmail.com
  auth-password placeholder
</route>
```

---

## Running the Proxy

### Basic Usage

```bash
# Using the wrapper script
python xoauth2_proxy_v2.py --config accounts.json --port 2525

# Using the installed command (after pip install -e .)
xoauth2-proxy --config accounts.json --port 2525

# Using the module directly
python -m src.main --config accounts.json --port 2525
```

### Command Line Options

```
--config PATH           Path to config.json (default: config.json)
--accounts PATH         Path to accounts.json (default: accounts.json)
--port PORT             SMTP listening port (default: 2525)
--host HOST             Bind address (default: 127.0.0.1)
--admin-port PORT       Admin HTTP API port (default: 9090)
--admin-host HOST       Admin HTTP API host (default: 127.0.0.1)
--dry-run               Test mode without relaying messages
--global-concurrency N  Global concurrency limit (default: 100)
```

### Examples

```bash
# Bind to all interfaces (for remote PowerMTA)
python xoauth2_proxy_v2.py --config accounts.json --host 0.0.0.0

# Dry-run mode (test without sending)
python xoauth2_proxy_v2.py --config accounts.json --dry-run

# Custom ports
python xoauth2_proxy_v2.py --config accounts.json --port 2526 --metrics-port 9091

# Reduced concurrency
python xoauth2_proxy_v2.py --config accounts.json --global-concurrency 50
```

---

## Testing

### Health Check

```bash
curl http://localhost:9090/health
# Response: {"status": "healthy"}
```

### Admin API

```bash
# List accounts
curl http://localhost:9090/admin/accounts

# Add account via HTTP API
curl -X POST http://localhost:9090/admin/accounts \
  -H "Content-Type: application/json" \
  -d '{
    "email": "sales@gmail.com",
    "provider": "gmail",
    "client_id": "YOUR_CLIENT_ID",
    "client_secret": "YOUR_CLIENT_SECRET",
    "refresh_token": "YOUR_REFRESH_TOKEN",
    "verify": true
  }'

# See docs/ADMIN_API.md for complete documentation
```

### SMTP Test

```bash
# Using telnet
telnet localhost 2525
EHLO test
QUIT

# Using swaks (recommended)
swaks --server localhost:2525 \
  --auth-user sender001@gmail.com \
  --auth-password placeholder \
  --from sender001@gmail.com \
  --to recipient@example.com
```

---

## Managing Accounts

### Interactive Tool

Add accounts using the interactive CLI tool:

```bash
# Run interactive tool
python add_account.py

# The tool will prompt you for:
# - Email address
# - Provider (gmail/outlook)
# - Client ID
# - Client Secret
# - Refresh Token
#
# It verifies credentials before saving!
```

### HTTP Admin API

Manage accounts via HTTP while the server is running (port 9090):

**List Accounts:**
```bash
curl http://localhost:9090/admin/accounts
```

**Add Account:**
```bash
curl -X POST http://localhost:9090/admin/accounts \
  -H "Content-Type: application/json" \
  -d '{
    "email": "sales@gmail.com",
    "provider": "gmail",
    "client_id": "YOUR_CLIENT_ID",
    "client_secret": "YOUR_CLIENT_SECRET",
    "refresh_token": "YOUR_REFRESH_TOKEN",
    "verify": true
  }'
```

**Benefits:**
- ✅ Add accounts without restarting
- ✅ Automatic hot-reload (zero downtime)
- ✅ OAuth2 credential verification
- ✅ API-first design for automation

**Complete API documentation:** See `docs/ADMIN_API.md`

---

## Logging

Logs are written to:
- **Linux/macOS**: `/var/log/xoauth2/xoauth2_proxy.log`
- **Windows**: `%TEMP%\xoauth2_proxy\xoauth2_proxy.log`
- **Fallback**: Current directory

```bash
# Monitor logs (Linux/macOS)
tail -f /var/log/xoauth2/xoauth2_proxy.log

# Monitor logs (Windows PowerShell)
Get-Content "$env:TEMP\xoauth2_proxy\xoauth2_proxy.log" -Tail 50 -Wait
```

---

## Security

### Best Practices

1. **Never commit accounts.json** to version control
   - ✅ `.gitignore` already excludes it

2. **Use environment variables** for sensitive data (optional):
   ```bash
   export XOAUTH2_CONFIG=/etc/xoauth2/accounts.json
   ```

3. **Restrict file permissions**:
   ```bash
   chmod 600 accounts.json
   ```

4. **Rotate refresh tokens** periodically

5. **Monitor for auth failures** in metrics

### OAuth2 Token Security

- Refresh tokens are stored in `accounts.json`
- Access tokens are cached in memory (cleared on restart)
- Tokens are never logged in plain text
- OAuth2 requests use HTTPS

---

## Development

### Project Structure

```
ProxyPowermtaXOAUTH2/
├── src/                      # Modular source code
│   ├── accounts/            # Account management
│   ├── config/              # Configuration
│   ├── logging/             # Logging setup
│   ├── metrics/             # Prometheus metrics
│   ├── oauth2/              # OAuth2 token management
│   ├── smtp/                # SMTP protocol handling
│   ├── utils/               # Utilities (circuit breaker, retry, rate limiter)
│   ├── cli.py               # CLI argument parsing
│   └── main.py              # Application entry point
├── tests/                    # Unit and integration tests
├── docs/                     # Documentation
├── archive/                  # Original monolithic implementations
├── xoauth2_proxy_v2.py      # Wrapper script
├── setup.py                  # Package setup
├── requirements.txt          # Dependencies
├── accounts.json             # Account configuration (not in git)
├── example_accounts.json    # Example configuration
└── pmta.cfg                  # PowerMTA configuration example
```

### Running Tests

```bash
# Run all tests
python -m pytest tests/

# Run with coverage
python -m pytest tests/ --cov=src --cov-report=html

# Run specific test file
python -m pytest tests/test_oauth2.py
```

### Code Quality

```bash
# Syntax check
python -m py_compile src/**/*.py

# Type checking (if mypy configured)
mypy src/

# Format code (if black configured)
black src/ tests/
```

---

## Troubleshooting

### Common Issues

**"accounts.json not found"**
```bash
# Solution: Create config file
cp example_accounts.json accounts.json
# Edit accounts.json with your credentials
```

**"invalid_grant" error**
```bash
# Solution: Refresh token expired, get a new one
# See SETUP_ACCOUNTS.md for OAuth2 setup
```

**"Connection refused" on port 2525**
```bash
# Solution: Check if proxy is running
curl http://localhost:9090/health

# Check port binding
netstat -an | grep 2525
```

**"Authentication failed"**
```bash
# Solution: Verify OAuth2 credentials in accounts.json
# Check client_id, client_secret, refresh_token
```

### Debug Mode

```bash
# Run with verbose logging
python xoauth2_proxy_v2.py --config accounts.json --log-level DEBUG
```

---

## Documentation

- **QUICK_START.md** - 3-step quick reference
- **SETUP_ACCOUNTS.md** - Account setup and OAuth2 credentials
- **CLAUDE.md** - Development guidance for Claude Code
- **docs/DEPLOYMENT_GUIDE.md** - Production deployment steps
- **docs/TEST_PLAN.md** - Comprehensive testing procedures
- **docs/OAUTH2_REAL_WORLD.md** - OAuth2 implementation details
- **docs/CROSS_PLATFORM_SETUP.md** - Platform-specific setup
- **docs/GMAIL_OUTLOOK_SETUP.md** - Provider-specific OAuth2 setup

---

## Version History

### v2.0 (Current - November 2025)
- ✅ Refactored to modular architecture (25+ modules)
- ✅ Fixed critical oauth_endpoint configuration bug
- ✅ Added resilience patterns (circuit breaker, retry, rate limiting)
- ✅ Improved observability (Prometheus metrics, structured logging)
- ✅ Cross-platform support (Windows/Linux/macOS)
- ✅ Production-ready for 100-500 accounts

### v1.0 (Original - 2024)
- ✅ Monolithic implementation (1100 lines)
- ✅ OAuth2 token refresh for Gmail and Outlook
- ✅ XOAUTH2 SMTP proxy
- ✅ Basic metrics and logging

---

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## License

MIT License - see LICENSE file for details

---

## Support

For issues and questions:
- Check documentation in `docs/`
- Review `TROUBLESHOOTING.md` (if available)
- Check logs at `/var/log/xoauth2/` or `%TEMP%\xoauth2_proxy\`
- Open an issue on GitHub

---

## Credits

Developed for PowerMTA v6 with production-grade OAuth2 support for Gmail and Outlook.

**Keywords**: XOAUTH2, SMTP proxy, OAuth2, PowerMTA, Gmail, Outlook, Office365, email relay, authentication proxy
