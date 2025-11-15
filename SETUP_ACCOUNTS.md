# XOAUTH2 Proxy v2.0 - Account Setup Guide

## Quick Start

1. **Copy the example file:**
   ```bash
   cp example_accounts.json accounts.json
   ```

2. **Edit `accounts.json` with your OAuth2 credentials**

3. **Start the proxy:**
   ```bash
   python xoauth2_proxy_v2.py --config accounts.json
   ```

---

## accounts.json File Format

The `accounts.json` file contains a JSON array of account configurations. Each account requires OAuth2 credentials for Gmail or Outlook.

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `account_id` | string | Unique identifier for the account (e.g., `gmail_account_001`) |
| `email` | string | Email address for this account |
| `ip_address` | string | IP address PowerMTA will use for this account |
| `vmta_name` | string | Virtual MTA name in PowerMTA config |
| `provider` | string | OAuth2 provider: `"gmail"` or `"outlook"` |
| `client_id` | string | OAuth2 client ID from provider |
| `client_secret` | string | OAuth2 client secret from provider |
| `refresh_token` | string | OAuth2 refresh token for this account |
| `oauth_endpoint` | string | OAuth authorization endpoint URL |
| `oauth_token_url` | string | OAuth token URL for refresh requests |

### Optional Fields

| Field | Default | Description |
|-------|---------|-------------|
| `max_concurrent_messages` | 10 | Max concurrent messages for this account |
| `max_messages_per_hour` | 10000 | Rate limit: messages per hour |

---

## Getting OAuth2 Credentials

### For Gmail

1. **Go to Google Cloud Console:**
   - https://console.cloud.google.com

2. **Create a new project** (or select existing one)

3. **Enable Gmail API:**
   - Go to "APIs & Services" → "Library"
   - Search for "Gmail API"
   - Click "Enable"

4. **Create OAuth2 credentials:**
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "OAuth 2.0 Client ID"
   - Choose "Desktop application"
   - Download the JSON file (contains `client_id` and `client_secret`)

5. **Get refresh token:**
   - Use the OAuth2 authorization flow with your client credentials
   - See GMAIL_OUTLOOK_SETUP.md for detailed steps

6. **Fill in accounts.json:**
   ```json
   {
     "provider": "gmail",
     "client_id": "YOUR_CLIENT_ID.apps.googleusercontent.com",
     "client_secret": "YOUR_CLIENT_SECRET",
     "refresh_token": "YOUR_REFRESH_TOKEN",
     "oauth_endpoint": "https://oauth2.googleapis.com",
     "oauth_token_url": "https://oauth2.googleapis.com/token"
   }
   ```

### For Outlook

1. **Go to Azure Portal:**
   - https://portal.azure.com

2. **Register an application:**
   - Go to "Azure Active Directory" → "App registrations"
   - Click "New registration"
   - Set name, select "Accounts in this organizational directory only"
   - Note the `Application (client) ID`

3. **Create a client secret:**
   - Go to "Certificates & secrets"
   - Click "New client secret"
   - Copy the secret value

4. **Add API permissions:**
   - Go to "API permissions"
   - Click "Add a permission" → "Microsoft Graph"
   - Select "Delegated permissions"
   - Search for "SMTP.Send"
   - Add the permission

5. **Get refresh token:**
   - Use the OAuth2 authorization flow with your client credentials
   - See GMAIL_OUTLOOK_SETUP.md for detailed steps

6. **Fill in accounts.json:**
   ```json
   {
     "provider": "outlook",
     "client_id": "YOUR_CLIENT_ID",
     "client_secret": "YOUR_CLIENT_SECRET",
     "refresh_token": "YOUR_REFRESH_TOKEN",
     "oauth_endpoint": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
     "oauth_token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token"
   }
   ```

---

## Example accounts.json Explained

### Basic Structure
```json
[
  {
    "account_id": "unique_identifier",
    "email": "sender@gmail.com",
    "ip_address": "192.168.1.100",
    "vmta_name": "vmta_name",
    "provider": "gmail",
    "client_id": "...",
    "client_secret": "...",
    "refresh_token": "...",
    "oauth_endpoint": "https://oauth2.googleapis.com",
    "oauth_token_url": "https://oauth2.googleapis.com/token",
    "max_concurrent_messages": 10,
    "max_messages_per_hour": 10000
  }
]
```

### Field Explanations

**account_id** - Must be unique per account
```json
"account_id": "gmail_sender_001"
```

**email** - The actual email address to send from
```json
"email": "noreply@company.com"
```

**ip_address** - IP that PowerMTA will use to connect to proxy
```json
"ip_address": "192.168.1.100"
```

**vmta_name** - Must match PowerMTA's VMTA name for this account
```json
"vmta_name": "vmta_google"
```

**provider** - Either "gmail" or "outlook"
```json
"provider": "gmail"
```

**OAuth2 credentials** - From your provider's console
```json
"client_id": "123456789.apps.googleusercontent.com",
"client_secret": "abc_XYZ_123",
"refresh_token": "1//abc-XYZ-123..."
```

**Endpoints** - Provider-specific URLs (don't change unless you know what you're doing)

**Rate limits** - Adjust based on sending volume
```json
"max_concurrent_messages": 20,      // How many at once
"max_messages_per_hour": 50000      // Max per hour
```

---

## Validation

The proxy will validate accounts.json on startup:

✅ **Checks performed:**
- Valid JSON syntax
- All required fields present
- Unique account IDs
- Unique email addresses
- Valid provider type
- File permissions

❌ **Common errors:**
- Missing required fields → Fill in all fields
- Duplicate emails → Each account needs unique email
- Invalid JSON → Check file format
- Invalid credentials → Verify with provider

---

## Tips

1. **Use environment variables (optional):**
   - Set `XOAUTH2_CONFIG` environment variable to config file path
   - `export XOAUTH2_CONFIG=/etc/xoauth2/accounts.json`

2. **Backup your credentials:**
   - Keep a secure backup of accounts.json
   - Don't commit to version control (use .gitignore)

3. **Test individual accounts:**
   - Use dry-run mode: `--dry-run`
   - Start with 1 account, add more after testing

4. **Monitor metrics:**
   - Check `/metrics` endpoint for connection stats
   - Watch for auth errors in logs

5. **Rate limits:**
   - Gmail: ~200 concurrent connections per account
   - Outlook: ~200 concurrent connections per account
   - Adjust `max_concurrent_messages` based on testing

---

## Troubleshooting

**"invalid_grant" error:**
- Refresh token may have expired
- Get a new refresh token from provider

**"authentication failed" error:**
- Check client_id and client_secret are correct
- Verify refresh_token hasn't expired

**"Connection refused" error:**
- Proxy not running on expected port
- Check --port argument (default: 2525)

**"accounts.json not found" error:**
- File should be in same directory as xoauth2_proxy_v2.py
- Or use `--config /path/to/accounts.json`

---

## Next Steps

1. ✅ Prepare OAuth2 credentials (see Getting OAuth2 Credentials above)
2. ✅ Create accounts.json with your credentials
3. ✅ Start the proxy: `python xoauth2_proxy_v2.py --config accounts.json`
4. ✅ Configure PowerMTA to use proxy on localhost:2525
5. ✅ Monitor logs and metrics

For more details, see:
- `GMAIL_OUTLOOK_SETUP.md` - Detailed OAuth2 setup
- `QUICK_START.md` - Quick reference
- `REFACTORING_FINAL_COMPLETE.md` - Architecture overview
