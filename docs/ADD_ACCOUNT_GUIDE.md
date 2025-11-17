# Add Account Tool - User Guide

The XOAUTH2 Proxy includes an interactive tool to easily add new email accounts to your `accounts.json` file.

## Quick Start

### Option 1: Run the standalone script

```bash
python add_account.py
```

### Option 2: Run as a Python module

```bash
python -m src.tools.add_account
```

### Option 3: Run the installed console script (after `pip install -e .`)

```bash
xoauth2-add-account
```

### Option 4: Specify a custom accounts file

```bash
python add_account.py /path/to/custom_accounts.json
```

## Interactive Prompts

The tool will guide you through entering the required information:

### 1. **Email Address**
The email account you want to add (e.g., `user@gmail.com` or `user@outlook.com`)

**Validation**: Must be a valid email format

### 2. **Provider**
Choose the email provider: `gmail` or `outlook`

**Auto-detection**: The tool automatically sets the correct SMTP endpoint based on the provider:
- Gmail → `smtp.gmail.com:587`
- Outlook → `smtp.office365.com:587`

### 3. **Client ID**
Your OAuth2 application's Client ID

**Where to get it**:
- **Gmail**: [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials
- **Outlook**: [Azure Portal](https://portal.azure.com/) → App registrations

### 4. **Client Secret**
Your OAuth2 application's Client Secret

**Notes**:
- **Required for Gmail**
- **Optional for Outlook** (some flows don't require it)

**Where to get it**: Same location as Client ID

### 5. **Refresh Token**
The OAuth2 refresh token for the account

**Where to get it**:
- Use your OAuth2 authorization flow to obtain the refresh token
- See [SETUP_ACCOUNTS.md](../SETUP_ACCOUNTS.md) for detailed instructions

## OAuth2 Credential Verification

After entering all details, the tool will ask:

```
Verify OAuth2 credentials? (y/n) [y]:
```

**Recommended**: Press `y` (or just Enter) to verify credentials before saving

**What happens**:
- The tool makes a test request to refresh the OAuth2 token
- If successful, you know the credentials are valid ✓
- If it fails, you can choose to add the account anyway or cancel

## Duplicate Detection

If an account with the same email already exists:

```
⚠ Warning: Account user@gmail.com already exists.
Overwrite existing account? (y/n) [n]:
```

- Press `y` to replace the existing account with the new credentials
- Press `n` to cancel and keep the existing account

## Example Session

```
============================================================
ADD NEW ACCOUNT TO XOAUTH2 PROXY
============================================================

Email address: sales@example.com
Provider (gmail/outlook): gmail
SMTP endpoint: smtp.gmail.com:587 (auto-detected)
Client ID: 123456789-abcdefg.apps.googleusercontent.com
Client Secret: GOCSPX-abc123def456
Refresh Token: 1//0gABC123DEF456...

Verify OAuth2 credentials? (y/n) [y]: y

Verifying OAuth2 credentials for sales@example.com...
✓ OAuth2 credentials verified successfully!

✓ Account sales@example.com added successfully!
✓ Total accounts: 3
✓ Saved to: /home/user/ProxyPowermtaXOAUTH2/accounts.json

============================================================
NEXT STEPS:
============================================================
1. Restart the XOAUTH2 proxy to load the new account:
   python xoauth2_proxy_v2.py --accounts accounts.json

2. Or send SIGHUP signal to reload accounts without restart:
   kill -HUP <pid>

3. Test the account:
   swaks --server 127.0.0.1:2525 --auth-user sales@example.com \
         --from test@example.com --to recipient@example.com
============================================================
```

## Required Information Summary

### Gmail Accounts
| Field | Required | Example |
|-------|----------|---------|
| Email | ✓ | `user@gmail.com` |
| Provider | ✓ | `gmail` |
| Client ID | ✓ | `123456789-abc.apps.googleusercontent.com` |
| Client Secret | ✓ | `GOCSPX-abc123def456` |
| Refresh Token | ✓ | `1//0gABC123DEF456...` |

### Outlook Accounts
| Field | Required | Example |
|-------|----------|---------|
| Email | ✓ | `user@outlook.com` |
| Provider | ✓ | `outlook` |
| Client ID | ✓ | `12345678-1234-1234-1234-123456789abc` |
| Client Secret | Optional | `abc~123.DEF-456_ghi` |
| Refresh Token | ✓ | `M.R3_BAY...` |

## File Format

The tool saves accounts in the following JSON format:

```json
[
  {
    "email": "user@gmail.com",
    "provider": "gmail",
    "oauth_endpoint": "smtp.gmail.com:587",
    "client_id": "123456789-abc.apps.googleusercontent.com",
    "client_secret": "GOCSPX-abc123def456",
    "refresh_token": "1//0gABC123DEF456..."
  },
  {
    "email": "user@outlook.com",
    "provider": "outlook",
    "oauth_endpoint": "smtp.office365.com:587",
    "client_id": "12345678-1234-1234-1234-123456789abc",
    "refresh_token": "M.R3_BAY..."
  }
]
```

## Troubleshooting

### Verification Fails

If OAuth2 verification fails, check:

1. **Client ID and Secret are correct**
   - Copy directly from provider console to avoid typos
   - Check for extra spaces or hidden characters

2. **Refresh token hasn't expired**
   - Some refresh tokens expire if not used
   - Generate a new refresh token

3. **Correct provider selected**
   - Gmail credentials won't work with Outlook provider and vice versa

4. **Network connectivity**
   - Ensure you can reach `oauth2.googleapis.com` (Gmail) or `login.microsoftonline.com` (Outlook)

### File Not Found

If the tool can't find `accounts.json`:

```bash
# Specify the full path
python add_account.py /full/path/to/accounts.json
```

### Permission Denied

If you get "Permission denied" when saving:

```bash
# Check file permissions
ls -l accounts.json

# Make sure you have write permission
chmod 644 accounts.json
```

## Security Best Practices

1. **Protect accounts.json**
   ```bash
   chmod 600 accounts.json  # Read/write for owner only
   ```

2. **Keep backups**
   ```bash
   cp accounts.json accounts.json.backup
   ```

3. **Never commit to version control**
   - `accounts.json` is already in `.gitignore`
   - Double-check before committing

4. **Use environment-specific files**
   - Production: `/etc/xoauth2/accounts.json`
   - Development: `./accounts.json`

## Next Steps

After adding accounts:

1. **Restart the proxy** to load new accounts
2. **Test the account** with swaks or your application
3. **Monitor logs** to ensure OAuth2 token refresh works
4. **Check metrics** at http://localhost:9090/metrics

## Related Documentation

- [SETUP_ACCOUNTS.md](../SETUP_ACCOUNTS.md) - How to get OAuth2 credentials
- [QUICK_START.md](../QUICK_START.md) - Quick reference guide
- [CLAUDE.md](../CLAUDE.md) - Development guide
- [docs/OAUTH2_REAL_WORLD.md](OAUTH2_REAL_WORLD.md) - OAuth2 implementation details
