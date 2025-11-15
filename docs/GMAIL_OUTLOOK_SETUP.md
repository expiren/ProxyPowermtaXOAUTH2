# Gmail + Outlook XOAUTH2 Setup Guide

**Version:** 1.0 (Updated for Gmail + Outlook Support)
**Last Updated:** 2025-11-14
**Status:** Production-Ready

This guide explains how to configure the system for both Gmail and Outlook accounts with real OAuth2 token refresh using `client_id`, `client_secret`, and `refresh_token`.

---

## Table of Contents

1. [What Changed](#what-changed)
2. [OAuth2 Token Endpoints](#oauth2-token-endpoints)
3. [Getting OAuth Tokens](#getting-oauth-tokens)
4. [Configuration Overview](#configuration-overview)
5. [Proxy Token Refresh Logic](#proxy-token-refresh-logic)
6. [Testing Both Providers](#testing-both-providers)

---

## What Changed

### XOAUTH2 Proxy Updates

✅ **Real OAuth2 Token Refresh**
- Replaced placeholder token generation with actual OAuth2 refresh flow
- Uses `requests` library for HTTP communication with OAuth providers
- Implements proper error handling for token refresh failures
- Logs all token refresh operations and duration

✅ **Provider Support**
- Detects provider type (gmail or outlook) from accounts.json
- Uses provider-specific OAuth token endpoints
- Supports both Gmail (Google OAuth2) and Outlook (Microsoft OAuth2)

✅ **Token Management**
- Tracks token expiration time from OAuth response
- Refreshes tokens 300 seconds before expiration
- Caches tokens in memory per account
- Resets token age metrics on successful refresh

✅ **XOAUTH2 Verification**
- Constructs proper XOAUTH2 string for both providers
- Format: `user=<email>\1auth=Bearer <token>\1\1`
- Validates token format before use
- Logs XOAUTH2 string construction details

### Accounts Configuration Updates

✅ **10 Gmail + 10 Outlook Accounts**
- Accounts 1-10: Gmail (gmail.account1@gmail.com to gmail.account10@gmail.com)
- Accounts 11-20: Outlook (outlook.account1@outlook.com to outlook.account10@outlook.com)

✅ **OAuth Token URL Field**
- Gmail: `https://oauth2.googleapis.com/token`
- Outlook: `https://login.microsoftonline.com/common/oauth2/v2.0/token`

✅ **Proper Credentials Format**
- `client_id`: OAuth application ID
- `client_secret`: OAuth application secret
- `refresh_token`: Long-lived refresh token from OAuth provider

### PMTA Configuration Updates

✅ **Domain-Based Routing**
- Gmail routes: Handle `gmail.com` domain
- Outlook routes: Handle `outlook.com` and `hotmail.com` domains

✅ **Account Separation**
- Gmail VMTAs: vmta-gmail-user1 to vmta-gmail-user10 (IPs 192.168.1.100-109)
- Outlook VMTAs: vmta-outlook-user1 to vmta-outlook-user10 (IPs 192.168.1.110-119)

✅ **Provider-Specific Authentication**
- Each route authenticates with the account email
- Proxy uses email to look up provider type and credentials
- Proxy handles provider-specific OAuth flow

---

## OAuth2 Token Endpoints

### Gmail OAuth2

**Token Endpoint:** `https://oauth2.googleapis.com/token`

**Request Format:**
```
POST https://oauth2.googleapis.com/token
Content-Type: application/x-www-form-urlencoded

grant_type=refresh_token
&client_id=YOUR_CLIENT_ID.apps.googleusercontent.com
&client_secret=YOUR_CLIENT_SECRET
&refresh_token=YOUR_REFRESH_TOKEN
```

**Response Format:**
```json
{
  "access_token": "ya29.a0AfH6SMBx...",
  "expires_in": 3599,
  "scope": "https://mail.google.com/",
  "token_type": "Bearer"
}
```

### Outlook/Office365 OAuth2

**Token Endpoint:** `https://login.microsoftonline.com/common/oauth2/v2.0/token`

**Request Format:**
```
POST https://login.microsoftonline.com/common/oauth2/v2.0/token
Content-Type: application/x-www-form-urlencoded

grant_type=refresh_token
&client_id=YOUR_CLIENT_ID
&client_secret=YOUR_CLIENT_SECRET
&refresh_token=YOUR_REFRESH_TOKEN
&scope=smtp.send offline_access
```

**Response Format:**
```json
{
  "token_type": "Bearer",
  "scope": "Mail.Send offline_access",
  "expires_in": 3599,
  "ext_expires_in": 3599,
  "access_token": "EwAIA8l6BAAURSN...",
  "refresh_token": "M.R3_BAY...",
  "id_token": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

---

## Getting OAuth Tokens

### For Gmail

**Method 1: OAuth 2.0 Playground (Recommended for Testing)**

1. Go to: https://developers.google.com/oauthplayground
2. Click settings icon → Use your own OAuth credentials
3. Enter your Gmail OAuth Client ID and Secret
4. In Step 1, select "Gmail API v1" → `https://mail.google.com/`
5. Click "Authorize APIs"
6. Complete Google login flow
7. In Step 2, click "Exchange authorization code for tokens"
8. Copy the `refresh_token` from the response

**Method 2: Official Google OAuth Flow**

1. Create OAuth app at: https://console.developers.google.com/
2. Create credentials → OAuth 2.0 Client ID (Desktop)
3. Download credentials JSON
4. Use google-auth library to get refresh token:
   ```bash
   pip install google-auth-oauthlib
   python3 google_oauth_flow.py
   ```

### For Outlook

**Method 1: Azure Portal**

1. Go to: https://portal.azure.com/
2. Search for "App registrations"
3. Create new registration
4. Under "Certificates & secrets" → Create client secret
5. Copy `client_id` and `client_secret`
6. Use OAuth authorization code flow to get `refresh_token`:
   ```
   https://login.microsoftonline.com/common/oauth2/v2.0/authorize
   ?client_id=YOUR_CLIENT_ID
   &scope=smtp.send%20offline_access
   &response_type=code
   &redirect_uri=http://localhost:8000/callback
   ```

**Method 2: Microsoft Graph Explorer**

1. Go to: https://developer.microsoft.com/en-us/graph/explorer
2. Sign in with Office365 account
3. Adjust permissions to `Mail.Send`
4. Under "Request headers", copy the `Authorization` header token
5. Use that token to request refresh token via Microsoft endpoint

---

## Configuration Overview

### accounts.json Structure

```json
{
  "accounts": [
    {
      "account_id": "gmail_user1",           // Unique ID for routing
      "email": "gmail.account1@gmail.com",   // Gmail address
      "ip_address": "192.168.1.100",         // Dedicated outbound IP
      "vmta_name": "vmta-gmail-user1",       // PMTA virtual-mta name
      "provider": "gmail",                   // Provider: gmail or outlook
      "client_id": "YOUR_CLIENT_ID.apps.googleusercontent.com",
      "client_secret": "YOUR_CLIENT_SECRET",
      "refresh_token": "1//0gJA7asfdZKRE8z...",  // OAuth refresh token
      "oauth_endpoint": "smtp.gmail.com:587",    // SMTP endpoint
      "oauth_token_url": "https://oauth2.googleapis.com/token",  // Token URL
      "max_concurrent_messages": 10,
      "max_messages_per_hour": 10000
    },
    {
      "account_id": "outlook_user1",
      "email": "outlook.account1@outlook.com",
      "ip_address": "192.168.1.110",
      "vmta_name": "vmta-outlook-user1",
      "provider": "outlook",
      "client_id": "YOUR_CLIENT_ID",
      "client_secret": "YOUR_CLIENT_SECRET",
      "refresh_token": "M.R3_BAY...",
      "oauth_endpoint": "smtp.office365.com:587",
      "oauth_token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
      "max_concurrent_messages": 10,
      "max_messages_per_hour": 10000
    }
  ]
}
```

### PMTA Configuration Structure

**Gmail Domain:**
```
<domain gmail.com>
  bounce-log pmta-bounces
  failure-log pmta-failures
  use-dkim yes
  dkim-signer-domain gmail.com
</domain>

<route gmail-user1>
  virtual-mta vmta-gmail-user1
  domain gmail.com
  smtp-host 127.0.0.1 port=2525
  auth-username gmail.account1@gmail.com
  auth-password placeholder
</route>
```

**Outlook Domain:**
```
<domain outlook.com>
  bounce-log pmta-bounces
  failure-log pmta-failures
  use-dkim yes
  dkim-signer-domain outlook.com
</domain>

<route outlook-user1>
  virtual-mta vmta-outlook-user1
  domain outlook.com
  domain hotmail.com
  smtp-host 127.0.0.1 port=2525
  auth-username outlook.account1@outlook.com
  auth-password placeholder
</route>
```

---

## Proxy Token Refresh Logic

### How Token Refresh Works

1. **Auth Received**: PMTA authenticates with proxy using AUTH PLAIN
2. **Account Lookup**: Proxy looks up account by email in accounts.json
3. **Token Check**: Proxy checks if token is expired (with 300s buffer)
4. **Token Refresh** (if needed):
   - Provider type detected from `account.provider`
   - POST to `oauth_token_url` with:
     - `grant_type=refresh_token`
     - `client_id`, `client_secret`
     - `refresh_token`
   - Parse response for `access_token` and `expires_in`
   - Store new token with calculated expiration time
5. **XOAUTH2 Verify**: Construct XOAUTH2 string and validate
6. **Message Handling**: Accept MAIL FROM, RCPT TO, DATA
7. **Log Everything**: Log each step with timestamps and status

### Token Refresh Metrics

```
token_refresh_total{account="...",result="success"} 5
token_refresh_total{account="...",result="failure"} 0
token_refresh_duration_seconds_sum{account="..."} 2.34
token_refresh_duration_seconds_count{account="..."} 5
token_age_seconds{account="..."} 1200  # seconds since token was obtained
```

### Error Handling

**If Token Refresh Fails:**
- Log error with HTTP status and response body
- Increment `errors_total` metric
- Return SMTP 454 (Temporary authentication failure)
- PMTA will retry message delivery later

**If Token Format Invalid:**
- Log validation error
- Return SMTP 535 (Authentication failed)
- Message bounces

---

## Testing Both Providers

### Test Gmail Account

```bash
# Send test message via Gmail account
swaks \
  --server 127.0.0.1:25 \
  --auth-user gmail.account1@gmail.com \
  --auth-password placeholder \
  --auth-method PLAIN \
  --from "test@example.com" \
  --to "recipient@gmail.com" \
  --h-Subject "Gmail Test" \
  --body "Testing Gmail account via proxy"

# Check logs
grep "gmail.account1" /var/log/xoauth2_proxy.log | head -20
```

### Test Outlook Account

```bash
# Send test message via Outlook account
swaks \
  --server 127.0.0.1:25 \
  --auth-user outlook.account1@outlook.com \
  --auth-password placeholder \
  --auth-method PLAIN \
  --from "test@example.com" \
  --to "recipient@outlook.com" \
  --h-Subject "Outlook Test" \
  --body "Testing Outlook account via proxy"

# Check logs
grep "outlook.account1" /var/log/xoauth2_proxy.log | head -20
```

### Verify Token Refresh

```bash
# Check metrics for token refresh
curl -s http://127.0.0.1:9090/metrics | grep token_refresh

# Expected output:
# token_refresh_total{account="gmail.account1@gmail.com",result="success"} 1
# token_refresh_duration_seconds_sum{account="gmail.account1@gmail.com"} 0.234
# token_age_seconds{account="gmail.account1@gmail.com"} 45
```

### Monitor Token Expiration

```bash
# Watch token ages and expiration
watch -n 10 'curl -s http://127.0.0.1:9090/metrics | grep token'

# Token should gradually age from 0 to 3600 seconds
# When approaching expiration (300s buffer), refresh should occur
# Token age resets to 0 after refresh
```

---

## Key Differences Between Providers

| Feature | Gmail | Outlook |
|---------|-------|---------|
| **OAuth Endpoint** | `oauth2.googleapis.com` | `login.microsoftonline.com` |
| **Token URL** | `/token` | `/oauth2/v2.0/token` |
| **SMTP Host** | `smtp.gmail.com:587` | `smtp.office365.com:587` |
| **Refresh Token Format** | `1//0gJA...` | `M.R3_BAY...` |
| **Scope** | `https://mail.google.com/` | `smtp.send offline_access` |
| **Response Format** | `expires_in` in seconds | `expires_in` in seconds |
| **Rate Limiting** | Per-second limits | Per-second limits |

---

## Production Deployment Steps

### 1. Prepare Accounts

```bash
# Edit accounts.json with your credentials
nano /etc/xoauth2/accounts.json

# Verify JSON syntax
python3 -m json.tool /etc/xoauth2/accounts.json > /dev/null && echo "Valid"
```

### 2. Update Dependencies

```bash
# Install requests library for OAuth
pip3 install requests

# Verify installation
python3 -c "import requests; print(requests.__version__)"
```

### 3. Validate Configuration

```bash
# Start proxy in test mode
python3 /opt/xoauth2/xoauth2_proxy.py \
  --config /etc/xoauth2/accounts.json \
  --dry-run \
  --port 2525

# In another terminal, test auth
swaks \
  --server 127.0.0.1:2525 \
  --auth-user gmail.account1@gmail.com \
  --auth-password placeholder \
  --auth-method PLAIN \
  --from "test@example.com" \
  --to "verify@gmail.com" \
  --body "Test"

# Check logs for token refresh
tail -50 /var/log/xoauth2_proxy.log | grep -i "token"
```

### 4. Monitor Token Refresh

```bash
# Setup log monitoring
tail -f /var/log/xoauth2_proxy.log | grep -E "token|auth|refresh"

# In another window, check metrics
watch -n 5 'curl -s http://127.0.0.1:9090/metrics | grep -E "token|auth" | head -20'
```

---

## Troubleshooting

### Token Refresh Fails with 401

**Symptom:**
```
[gmail.account1@gmail.com] Token refresh request failed with status 401
```

**Cause:** Invalid client credentials or expired refresh token

**Solution:**
1. Verify `client_id` and `client_secret` in accounts.json
2. Regenerate refresh token using OAuth flow
3. Ensure refresh token has not been revoked

### Token Refresh Fails with 400

**Symptom:**
```
[gmail.account1@gmail.com] Invalid JSON in token response: JSONDecodeError
```

**Cause:** Invalid request format or provider API change

**Solution:**
1. Check provider-specific parameters in token request
2. Verify `oauth_token_url` matches provider endpoint
3. Review provider documentation for recent changes

### AUTH Fails After Token Refresh

**Symptom:**
```
[gmail.account1@gmail.com] XOAUTH2 verification failed
```

**Cause:** Token format invalid or XOAUTH2 string construction error

**Solution:**
1. Verify token from OAuth endpoint is non-empty
2. Check token format (should be long alphanumeric string)
3. Review XOAUTH2 string construction in logs

---

## Important Notes

1. **Keep Secrets Safe**: Never commit accounts.json with real credentials
2. **Rotate Tokens**: Periodically refresh OAuth tokens for security
3. **Monitor Expiration**: Set alerts for token age approaching 3600s
4. **Test Both Providers**: Always test with both Gmail and Outlook accounts
5. **Check Logs**: Review logs for any authentication errors

---

## Resources

- [Google OAuth 2.0 Documentation](https://developers.google.com/identity/protocols/oauth2)
- [Gmail API with XOAUTH2](https://developers.google.com/gmail/imap_xoauth2)
- [Microsoft OAuth 2.0](https://docs.microsoft.com/en-us/azure/active-directory/develop/v2-oauth2-auth-code-flow)
- [Office 365 XOAUTH2](https://learn.microsoft.com/en-us/exchange/client-developer/legacy-protocols/how-to-authenticate-an-imap-pop-smtp-application-by-using-oauth)

---

**Created:** 2025-11-14
**Status:** Production-Ready ✅
