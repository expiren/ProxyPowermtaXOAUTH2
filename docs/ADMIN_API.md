# Admin HTTP API Documentation

The XOAUTH2 Proxy includes an HTTP API for managing accounts while the server is running. This allows you to add, list, and manage accounts without restarting the proxy.

## Quick Start

When you start the proxy, the Admin HTTP server runs on port 9090 by default:

```bash
python xoauth2_proxy_v2.py --host 0.0.0.0 --port 2525
```

The Admin API will be available at: `http://127.0.0.1:9090`

### Custom Admin Port

```bash
python xoauth2_proxy_v2.py --admin-host 0.0.0.0 --admin-port 8080
```

---

## Endpoints

### 1. Health Check

**GET /health**

Check if the admin server is running.

**Example:**

```bash
curl http://127.0.0.1:9090/health
```

**Response:**

```json
{
  "status": "healthy",
  "service": "xoauth2-proxy-admin"
}
```

---

### 2. List Accounts

**GET /admin/accounts**

List all configured accounts (without sensitive credentials).

**Example:**

```bash
curl http://127.0.0.1:9090/admin/accounts
```

**Response:**

```json
{
  "success": true,
  "total_accounts": 2,
  "accounts": [
    {
      "email": "user@gmail.com",
      "provider": "gmail",
      "oauth_endpoint": "smtp.gmail.com:587"
    },
    {
      "email": "user@outlook.com",
      "provider": "outlook",
      "oauth_endpoint": "smtp.office365.com:587"
    }
  ]
}
```

---

### 3. Add Account

**POST /admin/accounts**

Add a new email account to the proxy.

**Request Body:**

```json
{
  "email": "sales@gmail.com",
  "provider": "gmail",
  "client_id": "123456789-abc.apps.googleusercontent.com",
  "client_secret": "GOCSPX-abc123def456",
  "refresh_token": "1//0gABC123DEF456...",
  "verify": true,
  "overwrite": false
}
```

**Required Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `email` | string | Email address (must be valid format) |
| `provider` | string | `"gmail"` or `"outlook"` |
| `client_id` | string | OAuth2 Client ID |
| `refresh_token` | string | OAuth2 Refresh Token |

**Optional Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `client_secret` | string | `null` | OAuth2 Client Secret (required for Gmail, optional for Outlook) |
| `verify` | boolean | `true` | Verify OAuth2 credentials before saving |
| `overwrite` | boolean | `false` | Overwrite existing account with same email |

**Note:** The `oauth_endpoint` field is auto-detected based on the provider and doesn't need to be specified.

---

## Examples

### Add Gmail Account

```bash
curl -X POST http://127.0.0.1:9090/admin/accounts \
  -H "Content-Type: application/json" \
  -d '{
    "email": "sales@gmail.com",
    "provider": "gmail",
    "client_id": "123456789-abc.apps.googleusercontent.com",
    "client_secret": "GOCSPX-abc123def456",
    "refresh_token": "1//0gABC123DEF456...",
    "verify": true
  }'
```

**Success Response (200):**

```json
{
  "success": true,
  "message": "Account sales@gmail.com added successfully",
  "total_accounts": 3,
  "account": {
    "email": "sales@gmail.com",
    "provider": "gmail",
    "oauth_endpoint": "smtp.gmail.com:587"
  }
}
```

---

### Add Outlook Account

```bash
curl -X POST http://127.0.0.1:9090/admin/accounts \
  -H "Content-Type: application/json" \
  -d '{
    "email": "support@outlook.com",
    "provider": "outlook",
    "client_id": "12345678-1234-1234-1234-123456789abc",
    "refresh_token": "M.R3_BAY...",
    "verify": true
  }'
```

**Note:** `client_secret` is optional for Outlook.

**Success Response (200):**

```json
{
  "success": true,
  "message": "Account support@outlook.com added successfully",
  "total_accounts": 4,
  "account": {
    "email": "support@outlook.com",
    "provider": "outlook",
    "oauth_endpoint": "smtp.office365.com:587"
  }
}
```

---

### Add Account Without Verification

```bash
curl -X POST http://127.0.0.1:9090/admin/accounts \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@gmail.com",
    "provider": "gmail",
    "client_id": "123456789-abc.apps.googleusercontent.com",
    "client_secret": "GOCSPX-abc123def456",
    "refresh_token": "1//0gABC123DEF456...",
    "verify": false
  }'
```

**Note:** Setting `"verify": false` skips OAuth2 credential verification. Use this if you're sure the credentials are valid but can't verify them at the moment.

---

### Overwrite Existing Account

```bash
curl -X POST http://127.0.0.1:9090/admin/accounts \
  -H "Content-Type: application/json" \
  -d '{
    "email": "sales@gmail.com",
    "provider": "gmail",
    "client_id": "NEW-CLIENT-ID",
    "client_secret": "NEW-CLIENT-SECRET",
    "refresh_token": "NEW-REFRESH-TOKEN",
    "overwrite": true
  }'
```

**Note:** Without `"overwrite": true`, attempting to add an existing email will return a 409 Conflict error.

---

## Error Responses

### 400 Bad Request - Missing Fields

```json
{
  "success": false,
  "error": "Missing required fields: client_secret, refresh_token"
}
```

### 400 Bad Request - Invalid Email

```json
{
  "success": false,
  "error": "Invalid email format"
}
```

### 400 Bad Request - Invalid Provider

```json
{
  "success": false,
  "error": "Provider must be \"gmail\" or \"outlook\""
}
```

### 400 Bad Request - Verification Failed

```json
{
  "success": false,
  "error": "OAuth2 verification failed: invalid_grant - Token has been expired or revoked"
}
```

### 409 Conflict - Duplicate Account

```json
{
  "success": false,
  "error": "Account sales@gmail.com already exists. Use \"overwrite\": true to replace it."
}
```

### 500 Internal Server Error

```json
{
  "success": false,
  "error": "Failed to save accounts to file"
}
```

---

## Automatic Reload

When an account is successfully added via the API, the proxy automatically:

1. ✅ Saves the account to `accounts.json`
2. ✅ Triggers hot-reload of accounts (no restart needed!)
3. ✅ Makes the account immediately available for SMTP connections

You can see the reload in the logs:

```
[AdminServer] Account sales@gmail.com added successfully (3 total)
[AdminServer] Accounts reloaded: 3 accounts active
```

---

## Using with Python

### Using `requests` library

```python
import requests

# Add Gmail account
data = {
    "email": "sales@gmail.com",
    "provider": "gmail",
    "client_id": "123456789-abc.apps.googleusercontent.com",
    "client_secret": "GOCSPX-abc123def456",
    "refresh_token": "1//0gABC123DEF456...",
    "verify": True
}

response = requests.post(
    "http://127.0.0.1:9090/admin/accounts",
    json=data
)

if response.status_code == 200:
    result = response.json()
    print(f"✓ {result['message']}")
    print(f"Total accounts: {result['total_accounts']}")
else:
    error = response.json()
    print(f"✗ Error: {error['error']}")
```

### Using `aiohttp` (async)

```python
import aiohttp
import asyncio

async def add_account():
    data = {
        "email": "sales@gmail.com",
        "provider": "gmail",
        "client_id": "123456789-abc.apps.googleusercontent.com",
        "client_secret": "GOCSPX-abc123def456",
        "refresh_token": "1//0gABC123DEF456...",
        "verify": True
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "http://127.0.0.1:9090/admin/accounts",
            json=data
        ) as response:
            result = await response.json()
            if response.status == 200:
                print(f"✓ {result['message']}")
            else:
                print(f"✗ Error: {result['error']}")

asyncio.run(add_account())
```

---

## Security Considerations

### 1. **Bind to localhost by default**

The admin server binds to `127.0.0.1` by default, making it only accessible locally:

```bash
# ✓ Safe - only accessible from this machine
python xoauth2_proxy_v2.py
```

### 2. **Be careful with 0.0.0.0**

Only bind to `0.0.0.0` if you need remote access:

```bash
# ⚠ Warning - accessible from network
python xoauth2_proxy_v2.py --admin-host 0.0.0.0 --admin-port 9090
```

**If you use 0.0.0.0:**
- Add firewall rules to restrict access
- Use a reverse proxy with authentication (nginx, Caddy)
- Consider implementing API key authentication

### 3. **Protect accounts.json**

The admin API saves accounts to `accounts.json`. Protect this file:

```bash
chmod 600 accounts.json  # Read/write for owner only
chown root:root accounts.json  # Owned by root (if running as root)
```

### 4. **Use HTTPS**

For production, use a reverse proxy with HTTPS:

**nginx example:**

```nginx
server {
    listen 443 ssl;
    server_name admin.yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:9090;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## Integration with PowerShell (Windows)

```powershell
# Add account using Invoke-RestMethod
$body = @{
    email = "sales@gmail.com"
    provider = "gmail"
    client_id = "123456789-abc.apps.googleusercontent.com"
    client_secret = "GOCSPX-abc123def456"
    refresh_token = "1//0gABC123DEF456..."
    verify = $true
} | ConvertTo-Json

$response = Invoke-RestMethod `
    -Uri "http://127.0.0.1:9090/admin/accounts" `
    -Method POST `
    -Body $body `
    -ContentType "application/json"

Write-Host "✓ $($response.message)"
Write-Host "Total accounts: $($response.total_accounts)"
```

---

## Troubleshooting

### Admin server not starting

Check the logs:

```bash
tail -f /var/log/xoauth2/xoauth2_proxy.log
```

Look for:
```
[AdminServer] Admin HTTP server started on http://127.0.0.1:9090
```

### Port already in use

Change the admin port:

```bash
python xoauth2_proxy_v2.py --admin-port 8080
```

### Cannot connect to admin server

Check if it's running:

```bash
curl http://127.0.0.1:9090/health
```

If using `0.0.0.0`, check firewall:

```bash
# Linux
sudo ufw allow 9090

# Check if port is listening
netstat -tln | grep 9090
```

### Accounts not reloading

Check the proxy logs for reload errors. The admin API should trigger:

```
[AdminServer] Accounts reloaded: X accounts active
```

---

## Related Documentation

- [ADD_ACCOUNT_GUIDE.md](ADD_ACCOUNT_GUIDE.md) - Interactive CLI tool for adding accounts
- [SETUP_ACCOUNTS.md](../SETUP_ACCOUNTS.md) - How to get OAuth2 credentials
- [QUICK_START.md](../QUICK_START.md) - Quick reference guide
- [CLAUDE.md](../CLAUDE.md) - Development guide
