# Real-World OAuth2 Token Refresh Implementation

**Date:** 2025-11-14
**Status:** Production-Ready

This document explains the actual OAuth2 token refresh mechanism used in production based on real-world examples.

---

## Overview

The proxy now implements **real OAuth2 token refresh** that matches exactly how Gmail and Outlook handle token requests.

### Key Differences

| Provider | Gmail | Outlook |
|----------|-------|---------|
| **Endpoint** | `https://oauth2.googleapis.com/token` | `https://login.live.com/oauth20_token.srf` |
| **client_id** | `...apps.googleusercontent.com` format | UUID format |
| **client_secret** | ✅ Required | ❌ NOT required |
| **refresh_token** | `1//0gJA...` format | `M.R3_BAY...` format |
| **Expires In** | 3600 seconds | 3600 seconds |
| **Scopes** | `https://mail.google.com/` | `IMAP.AccessAsUser.All, POP.AccessAsUser.All, SMTP.Send` |

---

## Real Token Refresh Flow

### Gmail Token Request

```python
POST https://oauth2.googleapis.com/token
Content-Type: application/x-www-form-urlencoded

grant_type=refresh_token
&client_id=YOUR_CLIENT_ID.apps.googleusercontent.com
&client_secret=YOUR_CLIENT_SECRET
&refresh_token=1//0gJA7asfdZKRE8z...
```

**Response:**
```json
{
  "access_token": "ya29.a0AfH6SMBx...",
  "expires_in": 3599,
  "scope": "https://mail.google.com/",
  "token_type": "Bearer"
}
```

### Outlook Token Request

```python
POST https://login.live.com/oauth20_token.srf
Content-Type: application/x-www-form-urlencoded

grant_type=refresh_token
&client_id=9e5f94bc-e8a4-4e73-b8be-63364c29d753
&refresh_token=M.C538_BAY.0.U.-Cs20*HMW5C11W!geWTLHS1KcDu42jwiBSvzYR1!...
```

**Response:**
```json
{
  "token_type": "bearer",
  "expires_in": 3600,
  "scope": "https://outlook.office.com/IMAP.AccessAsUser.All https://outlook.office.com/POP.AccessAsUser.All https://outlook.office.com/SMTP.Send",
  "access_token": "EwAIBOl3BAAU0wDjFA6usBY8gB2LLZHCr9gRQlcAAaRIm9CdXTuYOTf6+zow32BvSOnUN5gS...",
  "refresh_token": "M.C538_SN1.0.U.-CivTZzniB7rmqokUruce5FDWUg0Bu94!J41m964bzIkMZhL3PWs9i77sTjxNfvPqyQEdDkR3OUpS01uW4U3KqY261DrnH1NNE2B4DBwpHfiSjj0EvLYu5PTDCa5PProcUP6c2ATbx8zXxnJRIQnRGbBThXV58JJyvrRa1VWEzyl1tGMH3v2AoP!...",
  "user_id": "AAAAAAAAAAAAAAAAAAAAABWibML6soV8u816wk5DK3c"
}
```

---

## Important Details

### 1. **Token Expiration**

Both providers return `expires_in: 3600` (1 hour)

```python
expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
```

The proxy implements a 300-second buffer before expiration:
```python
def is_expired(self, buffer_seconds: int = 300) -> bool:
    return datetime.utcnow() >= (self.expires_at - timedelta(seconds=buffer_seconds))
```

This means tokens are refreshed **5 minutes before** actual expiration.

### 2. **Refresh Token Updates**

**Outlook returns an updated refresh_token in the response!**

```python
# Some providers (Outlook) return updated refresh_token
refresh_token = token_data.get('refresh_token', account.refresh_token)

# Update account if token changed
if refresh_token != account.refresh_token:
    logger.info(f"Refresh token updated by provider")
    account.refresh_token = refresh_token
```

**This is critical**: If the refresh token is not updated, future token refreshes will fail with the old token.

### 3. **Scopes**

The scopes returned indicate what the token can be used for:

**Gmail Scopes:**
```
https://mail.google.com/
```

**Outlook Scopes:**
```
https://outlook.office.com/IMAP.AccessAsUser.All
https://outlook.office.com/POP.AccessAsUser.All
https://outlook.office.com/SMTP.Send
```

All scopes are needed for email access.

### 4. **Provider Detection**

The proxy detects provider type from `accounts.json`:

```python
if account.provider.lower() == 'outlook':
    # Use Outlook-specific request format (no client_secret)
    payload = {
        'grant_type': 'refresh_token',
        'client_id': account.client_id,
        'refresh_token': account.refresh_token,
    }
else:
    # Use Gmail-specific request format (with client_secret)
    payload = {
        'grant_type': 'refresh_token',
        'client_id': account.client_id,
        'client_secret': account.client_secret,
        'refresh_token': account.refresh_token,
    }
```

---

## Logging Output

### Successful Gmail Token Refresh

```
2025-11-14 10:15:30 - [gmail.account1@gmail.com] Refreshing OAuth token (provider: gmail)
2025-11-14 10:15:30 - [gmail.account1@gmail.com] Gmail token request to https://oauth2.googleapis.com/token with client_id=558976430978...
2025-11-14 10:15:30 - [gmail.account1@gmail.com] Token scopes: https://mail.google.com/
2025-11-14 10:15:30 - [gmail.account1@gmail.com] Token refreshed successfully (expires in 3599s, duration: 0.23s, scope: https://mail.google.com/)
```

### Successful Outlook Token Refresh with Token Update

```
2025-11-14 10:15:30 - [outlook.account1@outlook.com] Refreshing OAuth token (provider: outlook)
2025-11-14 10:15:30 - [outlook.account1@outlook.com] Outlook token request to https://login.live.com/oauth20_token.srf with client_id=9e5f94bc-e8a...
2025-11-14 10:15:30 - [outlook.account1@outlook.com] Token scopes: https://outlook.office.com/IMAP.AccessAsUser.All https://outlook.office.com/POP.AccessAsUser.All https://outlook.office.com/SMTP.Send
2025-11-14 10:15:31 - [outlook.account1@outlook.com] Refresh token updated by provider (was M.C538_BAY..., now M.C538_SN1...)
2025-11-14 10:15:31 - [outlook.account1@outlook.com] Token refreshed successfully (expires in 3600s, duration: 0.34s, scope: https://outlook.office.com/...)
```

### Token Refresh Failure

```
2025-11-14 10:15:30 - [outlook.account1@outlook.com] Refreshing OAuth token (provider: outlook)
2025-11-14 10:15:30 - [outlook.account1@outlook.com] Token refresh failed with status 401: {"error":"invalid_grant","error_description":"..."}
2025-11-14 10:15:30 - ERROR - Token refresh request failed with status 401: ...
2025-11-14 10:15:30 - Metrics: token_refresh_total{account="outlook.account1@outlook.com",result="failure"} incremented
```

---

## Configuration in accounts.json

### Gmail Account Example

```json
{
  "account_id": "gmail_user1",
  "email": "gmail.account1@gmail.com",
  "ip_address": "192.168.1.100",
  "vmta_name": "vmta-gmail-user1",
  "provider": "gmail",
  "client_id": "558976430978-xxxxxxxxxxxxxxx.apps.googleusercontent.com",
  "client_secret": "GOCSPX-xxxxxxxxxxxxxxxxxxxxx",
  "refresh_token": "1//0gJA7asfdZKRE8z...",
  "oauth_endpoint": "smtp.gmail.com:587",
  "oauth_token_url": "https://oauth2.googleapis.com/token",
  "max_concurrent_messages": 10,
  "max_messages_per_hour": 10000
}
```

### Outlook Account Example

```json
{
  "account_id": "outlook_user1",
  "email": "outlook.account1@outlook.com",
  "ip_address": "192.168.1.110",
  "vmta_name": "vmta-outlook-user1",
  "provider": "outlook",
  "client_id": "9e5f94bc-e8a4-4e73-b8be-63364c29d753",
  "client_secret": "",
  "refresh_token": "M.C538_BAY.0.U.-Cs20*HMW5C11W!geWTLHS1KcDu42jwiBSvzYR1!...",
  "oauth_endpoint": "smtp.office365.com:587",
  "oauth_token_url": "https://login.live.com/oauth20_token.srf",
  "max_concurrent_messages": 10,
  "max_messages_per_hour": 10000
}
```

---

## XOAUTH2 String Construction

After token refresh, the proxy constructs XOAUTH2 authentication string:

```python
xoauth2_string = f"user={account.email}\1auth=Bearer {token.access_token}\1\1"
xoauth2_b64 = base64.b64encode(xoauth2_string.encode('utf-8')).decode('utf-8')
```

**Example for Gmail:**
```
user=gmail.account1@gmail.com\1auth=Bearer ya29.a0AfH6SMBx...\1\1
```

Base64 encoded for SMTP:
```
dXNlcj1nbWFpbC5hY2NvdW50MUBnbWFpbC5jb20BYWN0aD1CZWFyZXIgeWEyOS5hMEFmSDZTTUJ4Li4uAQE=
```

**This is sent to Gmail SMTP server** (not implemented in proxy, only constructed and validated)

---

## Production Considerations

### 1. **Monitor Token Age**

```bash
curl -s http://127.0.0.1:9090/metrics | grep token_age_seconds
```

Token age should gradually increase from 0 to ~3300 seconds, then reset to 0 after refresh.

### 2. **Handle Token Expiration Gracefully**

If token refresh fails:
- Proxy returns SMTP 454 (Temporary authentication failure)
- PMTA automatically retries the message
- No message loss

### 3. **Update Refresh Tokens**

For Outlook accounts, the refresh token returned in the response should be persisted:
- Proxy logs when token is updated
- Next startup uses updated token
- For production, consider syncing updated tokens back to database

### 4. **Error Recovery**

Token refresh can fail due to:
- **401 Unauthorized** → Invalid/expired refresh token → Update token
- **400 Bad Request** → Malformed request → Check configuration
- **Network Error** → Temporary failure → Automatically retried

---

## Testing Token Refresh

### Get Current Token from Metrics

```bash
curl -s http://127.0.0.1:9090/metrics | grep -E "token_|auth_"
```

**Example output:**
```
token_refresh_total{account="gmail.account1@gmail.com",result="success"} 5.0
token_refresh_total{account="outlook.account1@outlook.com",result="success"} 3.0
token_refresh_duration_seconds_sum{account="gmail.account1@gmail.com"} 1.15
token_age_seconds{account="gmail.account1@gmail.com"} 234
token_age_seconds{account="outlook.account1@outlook.com"} 123
```

### Verify Token in Logs

```bash
tail -100 /var/log/xoauth2_proxy.log | grep -i "token\|refresh"
```

### Manual Token Test

```bash
# Get fresh token for Outlook
python3 << 'EOF'
import requests

client_id = "9e5f94bc-e8a4-4e73-b8be-63364c29d753"
refresh_token = "M.C538_BAY.0.U.-Cs20*HMW5C11W!geWTLHS1KcDu42jwiBSvzYR1!..."

data = {
    'grant_type': 'refresh_token',
    'client_id': client_id,
    'refresh_token': refresh_token
}

ret = requests.post('https://login.live.com/oauth20_token.srf', data=data)
print(f"Status: {ret.status_code}")
print(f"Response: {ret.json()}")

if ret.status_code == 200:
    print(f"\nAccess Token: {ret.json()['access_token'][:50]}...")
    print(f"Expires In: {ret.json()['expires_in']} seconds")
    print(f"New Refresh Token: {ret.json()['refresh_token'][:50]}...")
EOF
```

---

## Troubleshooting

### Token Refresh Returns 401

**Problem:** `Token refresh failed with status 401`

**Cause:**
- Refresh token expired (old token)
- Token revoked (user changed password)
- Invalid client_id

**Solution:**
- Regenerate OAuth tokens
- Update accounts.json
- Restart proxy or send SIGHUP

### Token Refresh Returns 400

**Problem:** `Token refresh failed with status 400`

**Cause:**
- Malformed request
- Missing required parameters
- Wrong endpoint URL

**Solution:**
- Verify `oauth_token_url` in accounts.json
- Check provider type (gmail vs outlook)
- Verify client_id and refresh_token format

### Refresh Token Not Updating

**Problem:** Outlook returns new refresh_token, but proxy doesn't update

**Current Implementation:**
```python
if refresh_token != account.refresh_token:
    account.refresh_token = refresh_token
```

**Production Note:** For persistent storage, you should:
1. Save updated refresh_token to database
2. Load on next startup
3. Alert if token updates frequently (security issue)

---

## Real-World Example

The provided `accounts.json` includes:
- **outlook_user1**: Real client_id and refresh_token example
  - client_id: `9e5f94bc-e8a4-4e73-b8be-63364c29d753`
  - refresh_token: Real M.C538_BAY... token (redacted for security)

This demonstrates exact format used in production.

---

**Status:** Production-Ready ✅
**Last Updated:** 2025-11-14

