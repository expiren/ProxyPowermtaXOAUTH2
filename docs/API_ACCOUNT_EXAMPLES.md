# Add Account Via HTTP API - Complete Examples

## Quick Start

**Start Proxy First:**
```bash
python3 xoauth2_proxy_v2.py --host 0.0.0.0 --port 2525 --admin-port 9091
```

**Add Account:**
```bash
curl -X POST http://127.0.0.1:9091/admin/accounts \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "gmail_01",
    "email": "your-email@gmail.com",
    "provider": "gmail",
    "client_id": "YOUR_GMAIL_CLIENT_ID.apps.googleusercontent.com",
    "client_secret": "YOUR_GMAIL_CLIENT_SECRET",
    "refresh_token": "YOUR_GMAIL_REFRESH_TOKEN"
  }'
```

---

## API Endpoint

**URL:** `http://127.0.0.1:9091/admin/accounts`
**Method:** `POST`
**Port:** `9091` (Admin API)
**Content-Type:** `application/json`

---

## Request Body Fields

### Required Fields:
- `account_id` (string) - Unique identifier for account
- `email` (string) - Email address (Gmail or Outlook)
- `provider` (string) - "gmail" or "outlook"
- `client_id` (string) - OAuth2 client ID
- `refresh_token` (string) - OAuth2 refresh token

### For Gmail:
- `client_secret` (string) - **REQUIRED** for Gmail accounts

### For Outlook:
- `client_secret` (string) - Optional (depends on OAuth flow)

### Optional Fields:
- `verify` (bool) - Verify OAuth2 credentials (default: false)
- `ip_address` (string) - Source IP for SMTP binding
- `vmta_name` (string) - PowerMTA name (informational)

### Auto-Populated (don't include):
- `oauth_token_url` - Auto-set based on provider
- `oauth_endpoint` - Not needed

---

## Examples

### 1. Add Gmail Account (Minimal)

```bash
curl -X POST http://127.0.0.1:9091/admin/accounts \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "gmail_sales",
    "email": "sales@gmail.com",
    "provider": "gmail",
    "client_id": "123456789-abc.apps.googleusercontent.com",
    "client_secret": "GOCSPX-abc123def456",
    "refresh_token": "1//0gABC123DEF456ghijklmnop..."
  }'
```

**Response:**
```json
{
  "status": "success",
  "message": "Account added successfully",
  "account": {
    "account_id": "gmail_sales",
    "email": "sales@gmail.com",
    "provider": "gmail"
  }
}
```

---

### 2. Add Outlook Account

```bash
curl -X POST http://127.0.0.1:9091/admin/accounts \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "outlook_support",
    "email": "support@outlook.com",
    "provider": "outlook",
    "client_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "refresh_token": "0.AYXXX..."
  }'
```

**Response:**
```json
{
  "status": "success",
  "message": "Account added successfully",
  "account": {
    "account_id": "outlook_support",
    "email": "support@outlook.com",
    "provider": "outlook"
  }
}
```

---

### 3. Add Account With Verification

```bash
curl -X POST http://127.0.0.1:9091/admin/accounts \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "gmail_sales",
    "email": "sales@gmail.com",
    "provider": "gmail",
    "client_id": "123456789-abc.apps.googleusercontent.com",
    "client_secret": "GOCSPX-abc123def456",
    "refresh_token": "1//0gABC123DEF456...",
    "verify": true
  }'
```

**Response (takes 2-5 seconds):**
```json
{
  "status": "success",
  "message": "Account added and OAuth2 verified",
  "account": {
    "account_id": "gmail_sales",
    "email": "sales@gmail.com",
    "provider": "gmail"
  },
  "oauth_valid": true
}
```

---

### 4. Add Multiple Accounts (Script)

**Python:**
```python
import requests
import json

accounts = [
    {
        "account_id": "gmail_01",
        "email": "sales@gmail.com",
        "provider": "gmail",
        "client_id": "123456789-abc.apps.googleusercontent.com",
        "client_secret": "GOCSPX-abc123def456",
        "refresh_token": "1//0gABC123DEF456...",
        "verify": False
    },
    {
        "account_id": "outlook_01",
        "email": "support@outlook.com",
        "provider": "outlook",
        "client_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
        "refresh_token": "0.AYXXX...",
        "verify": False
    }
]

for account in accounts:
    response = requests.post(
        "http://127.0.0.1:9091/admin/accounts",
        json=account,
        headers={"Content-Type": "application/json"}
    )

    result = response.json()
    if result['status'] == 'success':
        print(f"Added: {account['email']}")
    else:
        print(f"Error: {result['message']}")
```

**PowerShell:**
```powershell
$accounts = @(
    @{
        account_id = "gmail_01"
        email = "sales@gmail.com"
        provider = "gmail"
        client_id = "123456789-abc.apps.googleusercontent.com"
        client_secret = "GOCSPX-abc123def456"
        refresh_token = "1//0gABC123DEF456..."
    },
    @{
        account_id = "outlook_01"
        email = "support@outlook.com"
        provider = "outlook"
        client_id = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
        refresh_token = "0.AYXXX..."
    }
)

foreach ($account in $accounts) {
    $body = $account | ConvertTo-Json
    $response = Invoke-WebRequest `
        -Uri "http://127.0.0.1:9091/admin/accounts" `
        -Method POST `
        -Headers @{"Content-Type" = "application/json"} `
        -Body $body

    $result = $response.Content | ConvertFrom-Json
    if ($result.status -eq "success") {
        Write-Host "Added: $($account.email)"
    } else {
        Write-Host "Error: $($result.message)"
    }
}
```

---

### 5. List All Accounts

```bash
curl -X GET http://127.0.0.1:9091/admin/accounts
```

**Response:**
```json
{
  "accounts": [
    {
      "account_id": "gmail_01",
      "email": "sales@gmail.com",
      "provider": "gmail"
    },
    {
      "account_id": "outlook_01",
      "email": "support@outlook.com",
      "provider": "outlook"
    }
  ]
}
```

---

## Error Responses

### Error 1: Missing Required Field

```bash
curl -X POST http://127.0.0.1:9091/admin/accounts \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "gmail_01",
    "email": "sales@gmail.com",
    "provider": "gmail",
    "client_id": "123456789-abc.apps.googleusercontent.com"
  }'
```

**Response (400 Bad Request):**
```json
{
  "status": "error",
  "message": "Missing required field: client_secret for Gmail accounts"
}
```

---

### Error 2: Invalid Email Format

**Response (400 Bad Request):**
```json
{
  "status": "error",
  "message": "Invalid email format: notanemail"
}
```

---

### Error 3: Invalid OAuth2 Credentials

```bash
curl -X POST http://127.0.0.1:9091/admin/accounts \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "gmail_01",
    "email": "sales@gmail.com",
    "provider": "gmail",
    "client_id": "123456789-abc.apps.googleusercontent.com",
    "client_secret": "GOCSPX-abc123def456",
    "refresh_token": "invalid_token",
    "verify": true
  }'
```

**Response (400 Bad Request):**
```json
{
  "status": "error",
  "message": "OAuth2 verification failed: Invalid refresh token",
  "oauth_valid": false
}
```

---

### Error 4: Duplicate Account

**Response (400 Bad Request):**
```json
{
  "status": "error",
  "message": "Account already exists: sales@gmail.com"
}
```

---

## Complete Workflow

### Step 1: Start Proxy
```bash
python3 xoauth2_proxy_v2.py --host 0.0.0.0 --port 2525 --admin-port 9091
```

### Step 2: Add Gmail Account
```bash
curl -X POST http://127.0.0.1:9091/admin/accounts \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "gmail_01",
    "email": "sales@gmail.com",
    "provider": "gmail",
    "client_id": "123456789-abc.apps.googleusercontent.com",
    "client_secret": "GOCSPX-abc123def456",
    "refresh_token": "1//0gABC123DEF456..."
  }'
```

### Step 3: Add Outlook Account
```bash
curl -X POST http://127.0.0.1:9091/admin/accounts \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "outlook_01",
    "email": "support@outlook.com",
    "provider": "outlook",
    "client_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "refresh_token": "0.AYXXX..."
  }'
```

### Step 4: Verify Accounts Added
```bash
curl -X GET http://127.0.0.1:9091/admin/accounts
```

### Step 5: Test with Proxy
```bash
swaks --server 127.0.0.1:2525 \
  --auth-user sales@gmail.com \
  --auth-password placeholder \
  --from sales@gmail.com \
  --to recipient@example.com \
  --body "Test email"
```

---

## Important Notes

1. **Admin Port** - Default is `9091`, specified with `--admin-port`
2. **Proxy Must Run** - Admin API is only available when proxy is running
3. **Zero Downtime** - Adding accounts does NOT require proxy restart
4. **Verification Optional** - `verify: true` makes HTTP call to OAuth2 provider
5. **Security** - Keep `client_secret` and `refresh_token` secure
6. **Backward Compatible** - Old accounts.json format still works

---

## Testing the Account

Once account is added, test it:

```bash
# Check account works
curl -X GET http://127.0.0.1:9091/admin/accounts

# Send test email through proxy
swaks --server 127.0.0.1:2525 \
  --auth-user sales@gmail.com \
  --auth-password placeholder \
  --from sales@gmail.com \
  --to test@example.com \
  --body "Test"

# Check proxy logs for success
tail -f /var/log/xoauth2/xoauth2_proxy.log
```

---

## OAuth2 Credentials

### Getting Gmail Credentials:
1. Go to https://console.cloud.google.com
2. Create OAuth2 credentials (Desktop app)
3. Authorize and get refresh token
4. Format: `1//0gABC123DEF456...` (100+ characters)

### Getting Outlook Credentials:
1. Go to https://portal.azure.com
2. Register application
3. Add Mail.Send permission
4. Authorize and get refresh token
5. Format: `0.AYXXX...` (200+ characters)
