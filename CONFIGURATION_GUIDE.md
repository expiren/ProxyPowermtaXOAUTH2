# XOAUTH2 Proxy Configuration Guide

## Overview

The proxy now supports **full JSON-based configuration** where ALL variables are controllable from configuration files.

## Configuration Files

### 1. `config.json` - Global & Provider Settings

Location: Same directory as `accounts.json` (optional, uses defaults if not present)

Purpose:
- Global proxy settings (concurrency, timeouts, backpressure)
- Provider-specific defaults (Gmail, Outlook, custom)
- Feature flags (enable/disable SMTP pipelining, rate limiting, etc.)
- Resilience patterns (retry, circuit breaker settings)

See: `example_config.json` for full schema

### 2. `accounts.json` - Account Credentials & Overrides

Purpose:
- OAuth2 credentials for each account
- Per-account overrides (optional) that override provider defaults

See: `example_accounts_with_overrides.json` for examples

---

## How It Works: Configuration Hierarchy

```
Provider Defaults (config.json)
    ↓
Account-Specific Overrides (accounts.json)
    ↓
Final Merged Configuration (used by proxy)
```

### Example:

**config.json:**
```json
{
  "providers": {
    "gmail": {
      "connection_pool": {
        "max_messages_per_connection": 50
      }
    }
  }
}
```

**accounts.json (Account 1 - uses defaults):**
```json
{
  "account_id": "1",
  "email": "sender1@domain.com",
  "provider": "gmail"
  // NO overrides - uses 50 from config.json
}
```

**accounts.json (Account 2 - overrides):**
```json
{
  "account_id": "2",
  "email": "vip@domain.com",
  "provider": "gmail",
  "connection_settings": {
    "max_messages_per_connection": 80  // Override: uses 80 instead of 50
  }
}
```

**Result:**
- Account 1: Uses 50 messages/connection (provider default)
- Account 2: Uses 80 messages/connection (account override)

---

## Configuration Variables

### Global Settings

```json
{
  "global": {
    "concurrency": {
      "max_concurrent_connections": 1000,     // Max total SMTP connections
      "global_concurrency_limit": 100,        // Max concurrent messages being sent
      "backpressure_queue_size": 1000,        // Queue size before backpressure kicks in
      "connection_backlog": 100               // TCP backlog for listening socket
    },

    "timeouts": {
      "oauth2_timeout": 10,                   // OAuth2 token refresh timeout (seconds)
      "smtp_timeout": 30,                     // SMTP command timeout (seconds)
      "connection_acquire_timeout": 5         // Max wait time to acquire connection from pool
    }
  }
}
```

### Provider-Specific Settings

Each provider (gmail, outlook, default) can have:

#### Connection Pool
```json
"connection_pool": {
  "max_connections_per_account": 40,          // Max pooled connections per account
  "max_messages_per_connection": 50,          // Reuse connection for X messages before closing
  "connection_max_age_seconds": 600,          // Close connection after X seconds (age limit)
  "connection_idle_timeout_seconds": 120,     // Close connection if idle for X seconds
  "connection_acquire_timeout_seconds": 5     // Max wait for available connection
}
```

**Important**: `max_messages_per_connection` controls connection reuse:
- Gmail: 50-80 recommended (conservative to avoid spam filters)
- Outlook: 30-50 recommended (Outlook is stricter)
- Higher = more reuse, more throughput, but risk of provider throttling

#### Rate Limiting
```json
"rate_limiting": {
  "enabled": true,
  "messages_per_hour": 10000,                 // Total messages per hour per account
  "messages_per_minute_per_connection": 25,   // Messages per minute per connection
  "burst_size": 50                            // Allow bursts up to X messages
}
```

#### Retry Settings
```json
"retry": {
  "max_attempts": 2,                          // Retry failed requests X times
  "backoff_factor": 2.0,                      // Exponential backoff multiplier
  "max_delay_seconds": 30,                    // Max delay between retries
  "jitter_enabled": true                      // Add random jitter to prevent thundering herd
}
```

#### Circuit Breaker
```json
"circuit_breaker": {
  "enabled": true,
  "failure_threshold": 5,                     // Open circuit after X failures
  "recovery_timeout_seconds": 60,             // Try recovery after X seconds
  "half_open_max_calls": 2                    // Test with X calls before fully closing
}
```

### Feature Flags

```json
"features": {
  "smtp_pipelining": true,                    // Enable connection reuse (CRITICAL for performance)
  "connection_pooling": true,                 // Enable connection pooling
  "xoauth2_verification": false,              // Verify tokens with upstream (adds latency, set false)
  "backpressure_control": true,               // Enable backpressure mechanisms
  "rate_limiting": true,                      // Enable rate limiting
  "circuit_breaker": true,                    // Enable circuit breaker
  "metrics_enabled": true                     // Enable Prometheus metrics
}
```

---

## Per-Account Overrides

Any account can override provider defaults by adding these fields to `accounts.json`:

```json
{
  "account_id": "1",
  "email": "vip@domain.com",
  "provider": "gmail",
  "client_id": "...",
  "refresh_token": "...",
  "oauth_endpoint": "smtp.gmail.com:587",

  // OVERRIDES (all optional):

  "connection_settings": {
    "max_connections_per_account": 80,        // Override provider default
    "max_messages_per_connection": 100
  },

  "rate_limiting": {
    "messages_per_hour": 20000,               // Higher limit for VIP account
    "messages_per_minute_per_connection": 50
  },

  "retry": {
    "max_attempts": 3                         // More aggressive retries
  }
}
```

---

## Usage

### Running with config.json

```bash
# Create config.json in same directory as accounts.json
cp example_config.json config.json

# Edit config.json with your settings
nano config.json

# Run proxy (it will auto-detect config.json)
python xoauth2_proxy_v2.py --config accounts.json
```

### Running without config.json

```bash
# Proxy will use built-in provider defaults
python xoauth2_proxy_v2.py --config accounts.json
```

---

## Recommended Settings by Use Case

### High-Volume Email Marketing (50k-200k emails/min)

**config.json:**
```json
{
  "global": {
    "concurrency": {
      "global_concurrency_limit": 200
    }
  },
  "providers": {
    "gmail": {
      "connection_pool": {
        "max_connections_per_account": 60,
        "max_messages_per_connection": 80
      }
    }
  },
  "features": {
    "smtp_pipelining": true,
    "backpressure_control": true
  }
}
```

### Transactional Emails (Low Volume, High Reliability)

**config.json:**
```json
{
  "providers": {
    "gmail": {
      "connection_pool": {
        "max_messages_per_connection": 30
      },
      "retry": {
        "max_attempts": 3,
        "max_delay_seconds": 60
      },
      "circuit_breaker": {
        "failure_threshold": 10
      }
    }
  }
}
```

### Testing / Development

**config.json:**
```json
{
  "global": {
    "concurrency": {
      "global_concurrency_limit": 10
    }
  },
  "providers": {
    "gmail": {
      "connection_pool": {
        "max_connections_per_account": 5,
        "max_messages_per_connection": 20
      }
    }
  },
  "features": {
    "xoauth2_verification": false
  }
}
```

---

## Monitoring Your Configuration

### Check Effective Settings

The proxy logs the merged configuration on startup:

```
[ConfigLoader] Applied gmail config to sender@domain.com (max_connections=40, max_messages=50)
```

### Prometheus Metrics

```bash
# Check connection pool usage
curl http://localhost:9090/metrics | grep smtp_connection_pool

# Check if hitting limits
curl http://localhost:9090/metrics | grep rate_limit
```

---

## Tuning Guide

### If you see: "All connections busy"
→ Increase `max_connections_per_account`

### If you see: "4.x.x errors from Gmail/Outlook"
→ Decrease `max_messages_per_connection` (provider is throttling)

### If you see: "Circuit breaker OPEN"
→ Check provider status, may need to increase `failure_threshold`

### If you see: High latency
→ Enable `smtp_pipelining` if not already enabled
→ Increase `max_connections_per_account`

### If you see: OOM (Out of Memory)
→ Decrease `global_concurrency_limit`
→ Decrease `backpressure_queue_size`

---

## Migration from Old Config

Old `accounts.json` (without overrides) will continue to work with provider defaults from config.json.

No changes needed unless you want per-account customization.
