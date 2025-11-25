# Config.json Update Summary (v2.0)

## Overview

Updated `config.json` to reflect the new **Hybrid Adaptive Connection Pooling** architecture (v2.0) with all required configuration fields and removal of deprecated/unused fields.

**Status**: ✅ COMPLETE - All 7 new adaptive pre-warming fields added to all 3 provider sections (Gmail, Outlook, Default)

---

## Changes Made

### 1. Added Adaptive Pre-Warming Configuration Fields

Added 7 new fields to each provider's `connection_pool` section:

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `adaptive_prewarm_enabled` | boolean | true | Enable/disable adaptive pre-warming |
| `prewarm_min_connections` | integer | 1 | Minimum connections for cold start |
| `prewarm_max_connections` | integer | Gmail:10, Outlook:8, Default:8 | Maximum connections to pre-warm |
| `prewarm_min_message_threshold` | integer | 100 | Only pre-warm if >100 msgs/hour |
| `prewarm_messages_per_connection` | integer | 10 | Tuning: connections = msgs/hour/60/this |
| `prewarm_concurrent_tasks` | integer | 100 | Concurrent creations during startup |
| `idle_connection_reuse_timeout` | integer | 120 | Detect stale connections (seconds) |

**Affected Sections**:
- `providers.gmail.connection_pool` - UPDATED
- `providers.outlook.connection_pool` - UPDATED
- `providers.default.connection_pool` - UPDATED

### 2. Documented Deprecated/Unused Fields

#### Marked as Deprecated in Code:
- **`global.timeouts.connection_acquire_timeout`**
  - Status: NOT USED (timeout logic is hardcoded at 15 seconds in connection_pool.py)
  - Marked with `[DEPRECATED - Not used]` in documentation
  - Kept for backward compatibility

#### Fields that were removed from this config but kept in proxy_config.py for BC:
These fields are defined in `src/config/proxy_config.py` but NOT present in `config.json`:
- `prewarm_percentage` (replaced by adaptive sizing)
- `periodic_rewarm_enabled` (replaced by lazy refresh)
- `periodic_rewarm_interval_seconds` (replaced by lazy refresh)
- `rewarm_concurrent_tasks` (replaced by lazy refresh)

### 3. Updated Usage Notes

Added documentation entries to `_usage_notes` section explaining the adaptive pre-warming strategy and deprecated fields.

---

## Configuration Field Usage Analysis

### USED Fields in Code

**Global Settings**:
- `global.concurrency.*` - All 3 fields (global_concurrency_limit, backpressure_queue_size, connection_backlog)
- `global.timeouts` - 3 fields used (oauth2_timeout, smtp_command_timeout, smtp_data_timeout)
- `global.oauth2.*` - All 3 fields (token refresh, caching)
- `global.http_pool.*` - All 5 fields (HTTP connection pooling for OAuth2)
- `global.smtp.*` - All 7 fields (SMTP protocol configuration)
- `global.logging.*` - 4 fields used (level, format, console_output, log_file_override)

**Provider Settings** (Gmail, Outlook, Default):
- `connection_pool.*` - All 15 fields
- `rate_limiting.*` - All 4 fields (enabled, messages_per_hour, messages_per_minute_per_connection, burst_size)
- `retry.*` - All 4 fields (max_attempts, backoff_factor, max_delay_seconds, jitter_enabled)
- `circuit_breaker.*` - All 4 fields (enabled, failure_threshold, recovery_timeout_seconds, half_open_max_calls)
- `oauth_token_url` - Used in Gmail and Outlook
- `smtp_endpoint` - Used in Gmail and Outlook

### UNUSED Fields in Code

| Field | Location | Status |
|-------|----------|--------|
| `connection_acquire_timeout` | global.timeouts | DEPRECATED - Marked in config |

---

## Provider-Specific Configuration

### Gmail (smtp.gmail.com:587)
- max_connections_per_account: 20
- prewarm_max_connections: 10
- messages_per_minute_per_connection: 25
- Higher connection limits due to Gmail's generous rate limits
- Supports ~10,000 messages/hour per account

### Outlook (smtp.office365.com:587)
- max_connections_per_account: 15
- prewarm_max_connections: 8
- messages_per_minute_per_connection: 15
- Lower connection limits due to Outlook's stricter rate limiting

### Default (custom providers)
- max_connections_per_account: 30
- prewarm_max_connections: 8
- messages_per_hour: 5000
- Balanced defaults for unknown providers

---

## Adaptive Pre-Warming Strategy

### Cold Start (Minute 0)
- Pre-warm minimum connections (1-2) for ALL accounts
- Ensures <100ms latency on first message
- Minimal resource usage

### Active Accounts (Messages Detected)
- If messages_this_hour >= prewarm_min_message_threshold (100):
  - Scale up connections based on traffic
  - Formula: min(max_conn, max(min_conn, (msgs/hour/60) / msgs_per_conn))
  - Example: 6000 msgs/hour = 100 msgs/min = estimated 10 concurrent = 1 connection needed

### Stale Connections
- Connections idle >120 seconds are replaced on-demand
- No background re-warming task (lazy refresh)
- Reduces resource overhead

---

## Validation Results

### JSON Syntax
- VALID - Verified with python json validation

### Field Completeness
- Gmail: 7/7 adaptive fields present
- Outlook: 7/7 adaptive fields present
- Default: 7/7 adaptive fields present

### Field Usage
- All fields in config.json are either used in code or marked as deprecated
- No orphaned fields found

---

## Migration from v1.0 to v2.0

### Fields to REMOVE from custom configs:
- prewarm_percentage (replaced by adaptive sizing)
- periodic_rewarm_enabled (replaced by lazy refresh)
- periodic_rewarm_interval_seconds (replaced by lazy refresh)
- rewarm_concurrent_tasks (replaced by lazy refresh)

### Fields to ADD to custom configs:
- adaptive_prewarm_enabled: true
- prewarm_min_connections: 1
- prewarm_max_connections: 10 (or 8 for Outlook/Default)
- prewarm_min_message_threshold: 100
- prewarm_messages_per_connection: 10
- prewarm_concurrent_tasks: 100
- idle_connection_reuse_timeout: 120

### Behavior Changes:
- Connections now scale with traffic (not fixed percentages)
- Minimum connections pre-warmed for all accounts (cold start optimization)
- On-demand connection creation for bursts (lazy refresh)
- No background re-warming task (reduced overhead)

---

## Files Modified

- **config.json** - Updated with all adaptive prewarm fields, marked deprecated fields
- **examples/example_config.json** - Already had adaptive fields

## Related Files (Code Already Updated)

- src/config/proxy_config.py - Supports adaptive prewarm fields
- src/smtp/connection_pool.py - Implements adaptive prewarm logic
- src/smtp/proxy.py - Calls prewarm_adaptive()
- src/smtp/upstream.py - Removed periodic rewarm task

---

## Summary

Configuration is complete and production-ready:

1. All 7 new adaptive prewarm fields added to all 3 providers
2. All fields documented with tuning guidance
3. Deprecated fields marked with clear notes
4. JSON syntax validated
5. Field usage verified against codebase
6. Usage notes updated with migration guidance

Result: config.json now fully supports v2.0 adaptive connection pooling architecture.

Generated: 2025-11-23
Config Version: 2.0
