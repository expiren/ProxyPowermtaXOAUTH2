# Configuration Reference Guide

Complete reference for all configuration options in XOAUTH2 Proxy v2.0.

---

## 📁 Configuration Files

### **config.json** - Global Settings
Contains **global proxy settings** and **provider defaults**. This file controls:
- Concurrency limits
- Timeouts
- SMTP protocol settings
- Logging configuration
- Provider-specific defaults (Gmail, Outlook)

### **accounts.json** - Account Credentials
Contains **OAuth2 credentials** for individual accounts. This file controls:
- Email addresses
- OAuth2 client IDs, secrets, refresh tokens
- Per-account overrides

**IMPORTANT:** Keep config.json and accounts.json separate! The CLI expects:
```bash
python xoauth2_proxy_v2.py --config config.json --accounts accounts.json
```

---

## 🔧 config.json Structure

### **Global Settings**

#### **global.concurrency**
Controls overall proxy concurrency and queue management.

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `global_concurrency_limit` | int | 100 | Maximum concurrent messages across ALL accounts |
| `backpressure_queue_size` | int | 1000 | Maximum queued messages before rejecting new connections |
| `connection_backlog` | int | 100 | TCP backlog for incoming SMTP connections |

**Tuning Recommendations:**
- **Low traffic (< 100 msg/sec):** Use defaults
- **Medium traffic (100-500 msg/sec):** Increase `global_concurrency_limit` to 500
- **High traffic (> 500 msg/sec):** Increase to 1000+ and test

**Example:**
```json
"concurrency": {
  "global_concurrency_limit": 500,
  "backpressure_queue_size": 2000,
  "connection_backlog": 200
}
```

---

#### **global.timeouts**
Global timeout settings in seconds.

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `oauth2_timeout` | int | 10 | Timeout for OAuth2 token refresh to Google/Microsoft APIs |
| `connection_acquire_timeout` | int | 5 | Timeout for acquiring connection from pool |
| `smtp_command_timeout` | int | 300 | Timeout for SMTP commands (5 minutes) |
| `smtp_data_timeout` | int | 600 | Timeout for DATA command / message upload (10 minutes) |

**Tuning Recommendations:**
- **Slow networks:** Increase `oauth2_timeout` to 20-30 seconds
- **Large messages:** Increase `smtp_data_timeout` to 1200 seconds (20 minutes)
- **Fast internal network:** Decrease `connection_acquire_timeout` to 2-3 seconds

**Example:**
```json
"timeouts": {
  "oauth2_timeout": 15,
  "connection_acquire_timeout": 3,
  "smtp_command_timeout": 300,
  "smtp_data_timeout": 1200
}
```

---

#### **global.smtp**
SMTP protocol configuration.

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `server_hostname` | string | "xoauth2-proxy" | SMTP server name advertised in EHLO responses |
| `max_message_size` | int | 52428800 | Maximum message size in bytes (50 MB) |
| `max_recipients` | int | 1000 | Maximum recipients per message |
| `max_line_length` | int | 1000 | Maximum SMTP command line length |

**Tuning Recommendations:**
- **Production:** Change `server_hostname` to match your domain (e.g., "mail.example.com")
- **Large attachments:** Increase `max_message_size` (Gmail limit: 25 MB, Outlook: 25 MB)
- **Bulk email:** Keep `max_recipients` at 1000 or lower

**Example:**
```json
"smtp": {
  "server_hostname": "mail.example.com",
  "max_message_size": 26214400,
  "max_recipients": 500,
  "max_line_length": 1000
}
```

---

#### **global.logging**
Logging configuration.

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `level` | string | "INFO" | Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `format` | string | (see below) | Python logging format string |
| `log_file_override` | string\|null | null | Override default log file path |
| `console_output` | bool | true | Enable console (stdout) logging |

**Default log format:**
```
%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s] - %(message)s
```

**Log Levels:**
- **DEBUG:** Very verbose (includes OAuth2 requests, connection pool, etc.)
- **INFO:** Normal operations (recommended for production)
- **WARNING:** Warnings and recoverable errors
- **ERROR:** Errors that affect individual messages
- **CRITICAL:** Fatal errors that stop the proxy

**Platform-specific log paths:**
- **Linux/macOS:** `/var/log/xoauth2/xoauth2_proxy.log`
- **Windows:** `%TEMP%\xoauth2_proxy\xoauth2_proxy.log`
- **Fallback:** Current directory

**Example:**
```json
"logging": {
  "level": "INFO",
  "format": "%(asctime)s [%(levelname)s] %(message)s",
  "log_file_override": "/var/log/myapp/xoauth2.log",
  "console_output": true
}
```

---

### **Provider Settings**

Provider settings define defaults for Gmail, Outlook, and fallback providers. Each provider has 4 sub-sections:

#### **Provider: oauth_token_url & smtp_endpoint**

| Provider | OAuth Token URL | SMTP Endpoint |
|----------|----------------|---------------|
| Gmail | `https://oauth2.googleapis.com/token` | `smtp.gmail.com:587` |
| Outlook | `https://login.microsoftonline.com/common/oauth2/v2.0/token` | `smtp.office365.com:587` |

**These are provider defaults.** Individual accounts can override `oauth_endpoint` and `oauth_token_url` in accounts.json.

---

#### **provider.connection_pool**
Connection pool settings per account.

| Setting | Type | Gmail Default | Outlook Default | Description |
|---------|------|---------------|-----------------|-------------|
| `max_connections_per_account` | int | 40 | 30 | Maximum concurrent SMTP connections per account |
| `max_messages_per_connection` | int | 50 | 40 | Maximum messages before closing connection |
| `connection_max_age_seconds` | int | 600 | 300 | Maximum connection lifetime (seconds) |
| `connection_idle_timeout_seconds` | int | 120 | 60 | Idle timeout before closing (seconds) |
| `connection_acquire_timeout_seconds` | int | 5 | 5 | Timeout for acquiring connection from pool |

**Tuning Recommendations:**
- **High volume (> 100 msg/sec per account):** Increase `max_connections_per_account` to 60-80
- **Low volume (< 10 msg/sec per account):** Decrease to 10-20 to reduce resource usage
- **Gmail limits:** ~100 simultaneous connections per account
- **Outlook limits:** ~30-40 simultaneous connections per account

**Example:**
```json
"gmail": {
  "connection_pool": {
    "max_connections_per_account": 60,
    "max_messages_per_connection": 100,
    "connection_max_age_seconds": 900,
    "connection_idle_timeout_seconds": 180,
    "connection_acquire_timeout_seconds": 5
  }
}
```

---

#### **provider.rate_limiting**
Rate limiting per account using token bucket algorithm.

| Setting | Type | Gmail Default | Outlook Default | Description |
|---------|------|---------------|-----------------|-------------|
| `enabled` | bool | true | true | Enable rate limiting |
| `messages_per_hour` | int | 10000 | 10000 | Maximum messages per hour per account |
| `messages_per_minute_per_connection` | int | 25 | 15 | Maximum messages per minute per connection |
| `burst_size` | int | 50 | 30 | Burst allowance for token bucket |

**Provider Limits:**
- **Gmail:** ~2000 messages/day (~83/hour average, bursts allowed)
- **Outlook:** ~10000 messages/day (~417/hour average)

**Tuning Recommendations:**
- Set `messages_per_hour` to **50-60% of daily limit** to allow headroom
- Use `burst_size` to handle traffic spikes
- Disable with `"enabled": false` for testing

**Example:**
```json
"gmail": {
  "rate_limiting": {
    "enabled": true,
    "messages_per_hour": 100,
    "messages_per_minute_per_connection": 20,
    "burst_size": 40
  }
}
```

---

#### **provider.retry**
Retry configuration for transient failures.

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `max_attempts` | int | 2 | Maximum retry attempts |
| `backoff_factor` | float | 2.0 | Exponential backoff multiplier |
| `max_delay_seconds` | int | 30 | Maximum retry delay |
| `jitter_enabled` | bool | true | Add random jitter to retry delays |

**Retry Delays (with backoff_factor=2.0):**
- Attempt 1: Immediate
- Attempt 2: ~1 second
- Attempt 3: ~2 seconds
- Attempt 4: ~4 seconds
- ...
- Max delay: `max_delay_seconds`

**Tuning Recommendations:**
- **Aggressive retries:** Increase `max_attempts` to 3-4
- **Conservative retries:** Decrease to 1 (no retry)
- **Jitter:** Keep enabled to avoid thundering herd

**Example:**
```json
"retry": {
  "max_attempts": 3,
  "backoff_factor": 1.5,
  "max_delay_seconds": 60,
  "jitter_enabled": true
}
```

---

#### **provider.circuit_breaker**
Circuit breaker to prevent cascading failures.

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | bool | true | Enable circuit breaker |
| `failure_threshold` | int | 5 | Consecutive failures before opening circuit |
| `recovery_timeout_seconds` | int | 60 | Seconds before attempting half-open state |
| `half_open_max_calls` | int | 2 | Test calls in half-open state before closing circuit |

**Circuit States:**
1. **CLOSED:** Normal operation
2. **OPEN:** After `failure_threshold` failures, reject all calls immediately
3. **HALF_OPEN:** After `recovery_timeout_seconds`, allow `half_open_max_calls` test calls
4. **CLOSED:** If test calls succeed, return to normal

**Tuning Recommendations:**
- **Strict:** Decrease `failure_threshold` to 3
- **Lenient:** Increase to 10
- **Disable for testing:** `"enabled": false`

**Example:**
```json
"circuit_breaker": {
  "enabled": true,
  "failure_threshold": 3,
  "recovery_timeout_seconds": 120,
  "half_open_max_calls": 3
}
```

---

## 📝 accounts.json Structure

### **Required Fields**

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `account_id` | string | Unique identifier for account | `"gmail_001"` |
| `email` | string | Email address | `"sender@gmail.com"` |
| `ip_address` | string | IP address for sending (legacy, optional) | `"192.168.1.100"` |
| `vmta_name` | string | PowerMTA virtual MTA name (legacy, optional) | `"vmta_gmail_01"` |
| `provider` | string | Provider: "gmail" or "outlook" | `"gmail"` |
| `client_id` | string | OAuth2 client ID | `"123-abc.apps.googleusercontent.com"` |
| `client_secret` | string | OAuth2 client secret (required for Gmail) | `"GOCSPX-abc123"` |
| `refresh_token` | string | OAuth2 refresh token | `"1//0gABC..."` |
| `oauth_endpoint` | string | SMTP endpoint (host:port) | `"smtp.gmail.com:587"` |
| `oauth_token_url` | string | OAuth2 token refresh URL | `"https://oauth2.googleapis.com/token"` |
| `max_concurrent_messages` | int | Per-account concurrency limit (legacy) | `10` |
| `max_messages_per_hour` | int | Per-account rate limit (legacy) | `10000` |

### **Optional Override Fields**

Accounts can override provider defaults from config.json:

| Field | Type | Description |
|-------|------|-------------|
| `connection_settings` | object | Override connection pool settings |
| `rate_limiting` | object | Override rate limiting settings |
| `retry` | object | Override retry settings |
| `circuit_breaker` | object | Override circuit breaker settings |

**Example with overrides:**
```json
{
  "account_id": "gmail_high_volume_001",
  "email": "bulk@gmail.com",
  "provider": "gmail",
  "client_id": "...",
  "client_secret": "...",
  "refresh_token": "...",
  "oauth_endpoint": "smtp.gmail.com:587",
  "oauth_token_url": "https://oauth2.googleapis.com/token",

  "connection_settings": {
    "max_connections_per_account": 80,
    "max_messages_per_connection": 100
  },

  "rate_limiting": {
    "messages_per_hour": 200,
    "burst_size": 100
  }
}
```

---

## 🔄 Configuration Validation

### **Validate config.json**

```bash
# Check JSON syntax
python3 -m json.tool config.json

# Check for required fields
python3 -c "
import json
with open('config.json') as f:
    config = json.load(f)
    assert 'global' in config
    assert 'providers' in config
    assert 'gmail' in config['providers']
    assert 'outlook' in config['providers']
    print('✓ config.json is valid')
"
```

### **Validate accounts.json**

```bash
# Check JSON syntax
python3 -m json.tool accounts.json

# Check for required fields
python3 -c "
import json
with open('accounts.json') as f:
    accounts = json.load(f)
    for acc in accounts:
        required = ['email', 'provider', 'client_id', 'refresh_token', 'oauth_endpoint', 'oauth_token_url']
        for field in required:
            assert field in acc, f'Missing {field} in account {acc.get(\"email\")}'
    print(f'✓ accounts.json is valid ({len(accounts)} accounts)')
"
```

---

## 🚀 CLI Argument Overrides

CLI arguments **override** config.json settings:

| CLI Argument | Overrides | Example |
|--------------|-----------|---------|
| `--host` | N/A (not in config) | `--host 0.0.0.0` |
| `--port` | N/A (not in config) | `--port 2525` |
| `--admin-host` | N/A (not in config) | `--admin-host 127.0.0.1` |
| `--admin-port` | N/A (not in config) | `--admin-port 9090` |
| `--global-concurrency` | `global.concurrency.global_concurrency_limit` | `--global-concurrency 500` |
| `--dry-run` | N/A (not in config) | `--dry-run` |

**Example:**
```bash
# Use config.json but override concurrency
python xoauth2_proxy_v2.py --config config.json --global-concurrency 1000
```

---

## 🔥 Hot-Reload (Unix Only)

Reload configuration without restarting:

```bash
# Find process ID
ps aux | grep xoauth2_proxy

# Send SIGHUP signal
kill -HUP <pid>

# Check logs for reload confirmation
tail -f /var/log/xoauth2/xoauth2_proxy.log
```

**What gets reloaded:**
- ✅ All accounts from accounts.json
- ✅ Provider defaults from config.json
- ❌ Global settings (require restart)
- ❌ CLI arguments (require restart)

**Windows:** SIGHUP not supported - restart required.

---

## 📖 Configuration Examples

### **Production: High Volume (1000+ msg/sec)**

**config.json:**
```json
{
  "global": {
    "concurrency": {
      "global_concurrency_limit": 2000,
      "backpressure_queue_size": 5000,
      "connection_backlog": 500
    }
  },
  "providers": {
    "gmail": {
      "connection_pool": {
        "max_connections_per_account": 80,
        "max_messages_per_connection": 100
      }
    }
  }
}
```

### **Development: Low Volume with Debug Logging**

**config.json:**
```json
{
  "global": {
    "logging": {
      "level": "DEBUG",
      "console_output": true
    },
    "concurrency": {
      "global_concurrency_limit": 10
    }
  },
  "providers": {
    "gmail": {
      "connection_pool": {
        "max_connections_per_account": 5
      },
      "circuit_breaker": {
        "enabled": false
      }
    }
  }
}
```

### **Testing: Disabled Rate Limiting and Retries**

**config.json:**
```json
{
  "providers": {
    "gmail": {
      "rate_limiting": {
        "enabled": false
      },
      "retry": {
        "max_attempts": 0
      },
      "circuit_breaker": {
        "enabled": false
      }
    }
  }
}
```

---

## ⚠️ Common Configuration Mistakes

### **1. Accounts in config.json**
**❌ WRONG:**
```json
{
  "global": {...},
  "providers": {...},
  "accounts": [...]
}
```

**✅ CORRECT:**
- config.json: Only global settings and provider defaults
- accounts.json: Only account credentials

### **2. oauth_endpoint is OAuth URL**
**❌ WRONG:**
```json
"oauth_endpoint": "https://oauth2.googleapis.com/token"
```

**✅ CORRECT:**
```json
"oauth_endpoint": "smtp.gmail.com:587",
"oauth_token_url": "https://oauth2.googleapis.com/token"
```

### **3. Missing client_secret for Gmail**
**❌ WRONG (Gmail):**
```json
{
  "provider": "gmail",
  "client_secret": ""
}
```

**✅ CORRECT:**
```json
{
  "provider": "gmail",
  "client_secret": "GOCSPX-abc123def456"
}
```

Note: Outlook may not require `client_secret` for some OAuth2 flows.

### **4. Invalid concurrency limits**
**❌ WRONG:**
```json
{
  "global_concurrency_limit": 10,
  "connection_pool": {
    "max_connections_per_account": 100
  }
}
```

**Problem:** Per-account limit (100) exceeds global limit (10).

**✅ CORRECT:** Ensure global limit ≥ sum of per-account limits.

---

## 📚 Related Documentation

- **SETUP_ACCOUNTS.md** - How to obtain OAuth2 credentials
- **DEPLOYMENT_GUIDE.md** - Production deployment recommendations
- **ADMIN_API.md** - HTTP API for managing accounts
- **QUICK_START.md** - 3-step quick reference

---

## 🔍 Configuration Checklist

Before deploying:

**config.json:**
- [ ] JSON syntax is valid (`python3 -m json.tool config.json`)
- [ ] `global.concurrency.global_concurrency_limit` matches expected load
- [ ] `global.logging.level` is INFO for production
- [ ] Provider settings match Gmail/Outlook limits
- [ ] No `accounts` array in config.json

**accounts.json:**
- [ ] JSON syntax is valid
- [ ] All required fields present for each account
- [ ] `oauth_endpoint` is SMTP endpoint (not OAuth URL)
- [ ] Gmail accounts have non-empty `client_secret`
- [ ] `refresh_token` is valid and not expired
- [ ] No duplicate `email` or `account_id` values

**Deployment:**
- [ ] Files are in correct locations
- [ ] CLI arguments are correct
- [ ] Firewall allows ports (2525 SMTP, 9090 Admin)
- [ ] Log directory is writable
- [ ] SIGHUP reload tested (Unix only)

---

**Configuration Version:** 2.0
**Last Updated:** November 2024
**Status:** Production-Ready
