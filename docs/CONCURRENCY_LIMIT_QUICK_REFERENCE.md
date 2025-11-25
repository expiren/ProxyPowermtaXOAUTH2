# Per-Account Concurrency Limits - Quick Reference

## Quick Answer

**Yes!** You can now control the per-account concurrency limit from `config.json`.

## Current Defaults

```json
// config.json
"providers": {
  "gmail": {
    "max_concurrent_messages": 15    // Gmail accounts
  },
  "outlook": {
    "max_concurrent_messages": 12    // Outlook accounts
  },
  "default": {
    "max_concurrent_messages": 10    // Custom providers
  }
}
```

## How to Change It

Edit `config.json` and modify the `max_concurrent_messages` value:

```json
"gmail": {
  "max_concurrent_messages": 20  // Increase to 20
}
```

Then restart the proxy.

## What This Means

- **15**: Gmail account can process max 15 messages simultaneously
- **12**: Outlook account can process max 12 messages simultaneously
- **10**: Custom provider account can process max 10 messages simultaneously

When an account reaches its limit, PowerMTA gets: `SMTP 451 "Server busy - per-account limit reached, try again later"`

## When to Increase/Decrease

**Increase if:**
- Seeing "Per-account concurrency limit reached" frequently
- Provider rate limit allows higher throughput
- High-volume sending deployment

**Decrease if:**
- Getting rate-limited by provider
- Need more stability/safety
- Testing/conservative deployment

## Safe Starting Points

| Provider | Current | Min | Max |
|----------|---------|-----|-----|
| Gmail | 15 | 10 | 50 |
| Outlook | 12 | 5 | 20 |
| Default | 10 | 5 | 20 |

## Log Message Format

```
[email@domain.com] Per-account concurrency limit reached (12/12)
                                                          ↑   ↑
                                                   current max
```

This is normal when traffic is high. It means:
- The proxy is protecting itself from overload ✓
- PowerMTA will retry (good) ✓
- When messages finish, more can be accepted ✓

## Technical Details

- **Location in code**: `src/config/proxy_config.py` (ProviderConfig class)
- **Applied to accounts**: `src/accounts/models.py` (apply_provider_config method)
- **Used in**: `src/smtp/handler.py` (when accepting messages)
- **Backward compatible**: Yes (defaults to 10 if not in config)

## Example: High-Volume Gmail Deployment

```json
"gmail": {
  "max_concurrent_messages": 25,     // Increase for high volume
  "connection_pool": {
    "max_connections_per_account": 40,
    "max_messages_per_connection": 200
  }
}
```

## Example: Conservative Deployment

```json
"gmail": {
  "max_concurrent_messages": 10,     // Keep it safe
  "connection_pool": {
    "max_connections_per_account": 20,
    "max_messages_per_connection": 50
  }
}
```

## Testing Your Changes

1. Edit config.json
2. Verify syntax: `python -m json.tool config.json`
3. Restart proxy
4. Watch logs for limit messages
5. Adjust if needed

## Troubleshooting

**Q: Seeing limit message every second?**
A: Limit too low for your traffic. Increase it in config.json.

**Q: Want different limits for different accounts?**
A: Current version: No. Future option (Option 3) would allow per-account override in accounts.json.

**Q: Limit not taking effect?**
A:
1. Make sure you edited the right provider (gmail/outlook/default)
2. Verify JSON syntax: `python -m json.tool config.json`
3. Restart proxy (config loaded at startup only)

**Q: Back to hardcoded 10?**
A: Remove the max_concurrent_messages field from config.json and restart.

## Related

- **What does limit mean?** → See `PER_ACCOUNT_CONCURRENCY_IMPLEMENTATION.md`
- **Global concurrency limit?** → See `global_concurrency_limit` in config.json
- **Connection pool sizing?** → See `max_connections_per_account` field

---

**Last Updated**: 2025-11-23
**Status**: Production Ready
