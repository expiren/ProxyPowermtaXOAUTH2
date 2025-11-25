# Batch Add Accounts - Official Endpoint

## Quick Start

**Endpoint:** `POST http://127.0.0.1:9091/admin/accounts/batch`

**Features:**
- ✅ Add multiple accounts in ONE request
- ✅ Parallel verification (fast!)
- ✅ Batch size up to 100 accounts
- ✅ Partial success handling
- ✅ Duplicate detection with overwrite option
- ✅ Auto-assign account_id, vmta_name, ip_address if not provided
- ✅ Zero downtime hot-reload

---

## Simple Batch Example

### Add 3 Gmail + 2 Outlook Accounts in One Request

```bash
curl -X POST http://127.0.0.1:9091/admin/accounts/batch \
  -H "Content-Type: application/json" \
  -d '[
    {
      "email": "sales@gmail.com",
      "provider": "gmail",
      "client_id": "123456789-abc.apps.googleusercontent.com",
      "client_secret": "GOCSPX-abc123def456",
      "refresh_token": "1//0gABC123DEF456..."
    },
    {
      "email": "support@gmail.com",
      "provider": "gmail",
      "client_id": "123456789-abc.apps.googleusercontent.com",
      "client_secret": "GOCSPX-abc123def456",
      "refresh_token": "1//0gXYZ789JKL012..."
    },
    {
      "email": "noreply@gmail.com",
      "provider": "gmail",
      "client_id": "123456789-abc.apps.googleusercontent.com",
      "client_secret": "GOCSPX-abc123def456",
      "refresh_token": "1//0gMNO456PQR789..."
    },
    {
      "email": "sales@outlook.com",
      "provider": "outlook",
      "client_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
      "refresh_token": "0.AYXXX..."
    },
    {
      "email": "support@outlook.com",
      "provider": "outlook",
      "client_id": "yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy",
      "refresh_token": "0.AYZZZ..."
    }
  ]'
```

**Response (201 Created):**
```json
{
  "success": true,
  "message": "All 5 accounts added and verified",
  "added_count": 5,
  "verified_count": 5,
  "verification_time_seconds": 3.45,
  "accounts": [
    {
      "account_id": "gmail_sales_gmail_com",
      "email": "sales@gmail.com",
      "provider": "gmail",
      "status": "verified"
    },
    {
      "account_id": "gmail_support_gmail_com",
      "email": "support@gmail.com",
      "provider": "gmail",
      "status": "verified"
    },
    {
      "account_id": "gmail_noreply_gmail_com",
      "email": "noreply@gmail.com",
      "provider": "gmail",
      "status": "verified"
    },
    {
      "account_id": "outlook_sales_outlook_com",
      "email": "sales@outlook.com",
      "provider": "outlook",
      "status": "verified"
    },
    {
      "account_id": "outlook_support_outlook_com",
      "email": "support@outlook.com",
      "provider": "outlook",
      "status": "verified"
    }
  ]
}
```

---

## Request Body Structure

### Required Fields (per account):
```json
{
  "email": "string",              // Email address
  "provider": "string",            // "gmail" or "outlook"
  "client_id": "string",           // OAuth2 client ID
  "refresh_token": "string"        // OAuth2 refresh token
}
```

### For Gmail (client_secret REQUIRED):
```json
{
  "email": "sales@gmail.com",
  "provider": "gmail",
  "client_id": "123456789-abc.apps.googleusercontent.com",
  "client_secret": "GOCSPX-abc123def456",      // REQUIRED for Gmail
  "refresh_token": "1//0gABC123DEF456..."
}
```

### For Outlook (client_secret OPTIONAL):
```json
{
  "email": "sales@outlook.com",
  "provider": "outlook",
  "client_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "refresh_token": "0.AYXXX..."
  // client_secret optional
}
```

### Optional Fields (per account):
```json
{
  "account_id": "gmail_01",         // Custom account ID (auto-generated if omitted)
  "vmta_name": "vmta-gmail-sales",  // PowerMTA VMTA name (auto-generated if omitted)
  "ip_address": "192.168.1.100",    // Source IP for SMTP binding (auto-assigned if omitted)
  "verify": true,                    // Verify OAuth2 credentials (default: true)
  "overwrite": false                 // Overwrite duplicate emails (default: false)
}
```

---

## Batch Examples

### Example 1: Minimal Batch (Just Required Fields)

```bash
curl -X POST http://127.0.0.1:9091/admin/accounts/batch \
  -H "Content-Type: application/json" \
  -d '[
    {
      "email": "sales@gmail.com",
      "provider": "gmail",
      "client_id": "123456789-abc.apps.googleusercontent.com",
      "client_secret": "GOCSPX-abc123def456",
      "refresh_token": "1//0gABC123DEF456..."
    },
    {
      "email": "sales@outlook.com",
      "provider": "outlook",
      "client_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
      "refresh_token": "0.AYXXX..."
    }
  ]'
```

---

### Example 2: Batch with Custom IDs and IPs

```bash
curl -X POST http://127.0.0.1:9091/admin/accounts/batch \
  -H "Content-Type: application/json" \
  -d '[
    {
      "account_id": "corp_gmail_01",
      "email": "sales@gmail.com",
      "provider": "gmail",
      "client_id": "123456789-abc.apps.googleusercontent.com",
      "client_secret": "GOCSPX-abc123def456",
      "refresh_token": "1//0gABC123DEF456...",
      "ip_address": "192.168.1.10",
      "vmta_name": "vmta-sales-dedicated-ip"
    },
    {
      "account_id": "corp_outlook_01",
      "email": "support@outlook.com",
      "provider": "outlook",
      "client_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
      "refresh_token": "0.AYZZZ...",
      "ip_address": "192.168.1.11",
      "vmta_name": "vmta-support-dedicated-ip"
    }
  ]'
```

---

### Example 3: Large Batch (100 Accounts - Max Limit)

```python
import requests
import json

# Generate 100 Gmail accounts
accounts = []
for i in range(1, 101):
    accounts.append({
        "email": f"sales{i:03d}@gmail.com",
        "provider": "gmail",
        "client_id": "123456789-abc.apps.googleusercontent.com",
        "client_secret": "GOCSPX-abc123def456",
        "refresh_token": f"1//0gToken{i:03d}...",
        "account_id": f"gmail_{i:03d}"
    })

response = requests.post(
    "http://127.0.0.1:9091/admin/accounts/batch",
    json=accounts,
    headers={"Content-Type": "application/json"}
)

result = response.json()
print(f"Added: {result['added_count']}/{len(accounts)}")
print(f"Verified: {result['verified_count']}/{len(accounts)}")
print(f"Time: {result['verification_time_seconds']:.2f} seconds")
```

---

### Example 4: Batch with No Verification (Faster)

```bash
curl -X POST http://127.0.0.1:9091/admin/accounts/batch \
  -H "Content-Type: application/json" \
  -d '[
    {
      "email": "sales@gmail.com",
      "provider": "gmail",
      "client_id": "123456789-abc.apps.googleusercontent.com",
      "client_secret": "GOCSPX-abc123def456",
      "refresh_token": "1//0gABC123DEF456...",
      "verify": false
    },
    {
      "email": "support@gmail.com",
      "provider": "gmail",
      "client_id": "123456789-abc.apps.googleusercontent.com",
      "client_secret": "GOCSPX-abc123def456",
      "refresh_token": "1//0gXYZ789JKL012...",
      "verify": false
    }
  ]'
```

**Response (instant, no OAuth2 calls):**
```json
{
  "success": true,
  "message": "Added 2 accounts (not verified)",
  "added_count": 2,
  "verified_count": 0
}
```

---

### Example 5: Batch with Overwrite

```bash
curl -X POST http://127.0.0.1:9091/admin/accounts/batch \
  -H "Content-Type: application/json" \
  -d '[
    {
      "email": "sales@gmail.com",
      "provider": "gmail",
      "client_id": "NEW_CLIENT_ID",
      "client_secret": "NEW_CLIENT_SECRET",
      "refresh_token": "NEW_REFRESH_TOKEN",
      "overwrite": true
    }
  ]'
```

**Response (if account already exists):**
```json
{
  "success": true,
  "message": "Account updated (overwritten)",
  "added_count": 1,
  "overwritten_count": 1
}
```

---

## Response Codes and Messages

### Success (201 Created)
```json
{
  "success": true,
  "message": "All 5 accounts added and verified",
  "added_count": 5,
  "verified_count": 5,
  "verification_time_seconds": 3.45
}
```

### Partial Success (206 Partial Content)
```json
{
  "success": true,
  "message": "Partial success: 3 added, 2 failed verification",
  "added_count": 3,
  "verified_count": 3,
  "failed_accounts": [
    {
      "email": "bad-token@gmail.com",
      "error": "Invalid refresh token"
    },
    {
      "email": "wrong-creds@outlook.com",
      "error": "OAuth2 verification failed"
    }
  ]
}
```

### All Failed (400 Bad Request)
```json
{
  "success": false,
  "error": "All 5 accounts failed verification",
  "failed_accounts": [...]
}
```

### Invalid Request (400 Bad Request)
```json
{
  "success": false,
  "error": "Body must be an array of account objects"
}
```

### Empty Array (400 Bad Request)
```json
{
  "success": false,
  "error": "Empty array provided"
}
```

### Too Many Accounts (400 Bad Request)
```json
{
  "success": false,
  "error": "Maximum 100 accounts per batch"
}
```

### Missing Required Field (400 Bad Request)
```json
{
  "success": false,
  "error": "Account 2: Missing required fields: client_secret"
}
```

### Duplicate Accounts (400 Bad Request)
```json
{
  "success": false,
  "error": "2 accounts already exist. Use \"overwrite\": true to replace them.",
  "duplicates": ["sales@gmail.com", "support@outlook.com"]
}
```

---

## Python Examples

### Simple Batch with Requests

```python
import requests

accounts = [
    {
        "email": "sales@gmail.com",
        "provider": "gmail",
        "client_id": "123456789-abc.apps.googleusercontent.com",
        "client_secret": "GOCSPX-abc123def456",
        "refresh_token": "1//0gABC123DEF456..."
    },
    {
        "email": "support@gmail.com",
        "provider": "gmail",
        "client_id": "123456789-abc.apps.googleusercontent.com",
        "client_secret": "GOCSPX-abc123def456",
        "refresh_token": "1//0gXYZ789JKL012..."
    }
]

response = requests.post(
    "http://127.0.0.1:9091/admin/accounts/batch",
    json=accounts,
    headers={"Content-Type": "application/json"}
)

result = response.json()

if result['success']:
    print(f"Added {result['added_count']} accounts")
    if result.get('verified_count'):
        print(f"Verified {result['verified_count']} accounts")
else:
    print(f"Error: {result['error']}")
    if result.get('failed_accounts'):
        for failed in result['failed_accounts']:
            print(f"  - {failed['email']}: {failed['error']}")
```

---

### Batch from JSON File

```python
import json
import requests

# Load accounts from file
with open('accounts_batch.json') as f:
    accounts = json.load(f)

# Add to proxy
response = requests.post(
    "http://127.0.0.1:9091/admin/accounts/batch",
    json=accounts,
    headers={"Content-Type": "application/json"}
)

result = response.json()
print(f"Result: {result['message']}")
print(f"Added: {result['added_count']}")

# Save report
with open('batch_result.json', 'w') as f:
    json.dump(result, f, indent=2)
```

---

### Batch with Error Handling

```python
import requests
import json
import time

def batch_add_accounts(accounts, max_retries=3):
    """Add accounts in batch with retry logic"""

    api_url = "http://127.0.0.1:9091/admin/accounts/batch"

    for attempt in range(1, max_retries + 1):
        try:
            print(f"[Attempt {attempt}/{max_retries}] Adding {len(accounts)} accounts...")

            response = requests.post(
                api_url,
                json=accounts,
                headers={"Content-Type": "application/json"},
                timeout=30
            )

            result = response.json()

            print(f"Response: {result['message']}")
            print(f"  Added: {result['added_count']}")

            if result.get('verified_count'):
                print(f"  Verified: {result['verified_count']}")
                print(f"  Time: {result['verification_time_seconds']:.2f}s")

            if result.get('failed_accounts'):
                print(f"  Failed: {len(result['failed_accounts'])}")
                for failed in result['failed_accounts']:
                    print(f"    - {failed['email']}: {failed['error']}")

            return result

        except requests.exceptions.RequestException as e:
            if attempt < max_retries:
                wait_time = 5 * attempt
                print(f"  Error: {e}")
                print(f"  Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"  Failed after {max_retries} attempts")
                raise

# Usage
accounts = [...]  # Your accounts list
result = batch_add_accounts(accounts)
```

---

### Batch from CSV

```python
import csv
import requests

def load_accounts_from_csv(filepath):
    """Load accounts from CSV file"""
    accounts = []

    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)

        for row in reader:
            account = {
                "email": row['email'],
                "provider": row['provider'],
                "client_id": row['client_id'],
                "refresh_token": row['refresh_token']
            }

            if row.get('client_secret'):
                account['client_secret'] = row['client_secret']

            if row.get('account_id'):
                account['account_id'] = row['account_id']

            accounts.append(account)

    return accounts

# CSV Format:
# email,provider,client_id,client_secret,refresh_token,account_id
# sales@gmail.com,gmail,123...,GOCSPX...,1//0g...,gmail_01
# support@outlook.com,outlook,xxxx...,,,outlook_01

accounts = load_accounts_from_csv('accounts.csv')

response = requests.post(
    "http://127.0.0.1:9091/admin/accounts/batch",
    json=accounts,
    headers={"Content-Type": "application/json"}
)

print(response.json())
```

---

## PowerShell Examples

### Simple Batch

```powershell
$accounts = @(
    @{
        email = "sales@gmail.com"
        provider = "gmail"
        client_id = "123456789-abc.apps.googleusercontent.com"
        client_secret = "GOCSPX-abc123def456"
        refresh_token = "1//0gABC123DEF456..."
    },
    @{
        email = "support@gmail.com"
        provider = "gmail"
        client_id = "123456789-abc.apps.googleusercontent.com"
        client_secret = "GOCSPX-abc123def456"
        refresh_token = "1//0gXYZ789JKL012..."
    }
)

$body = $accounts | ConvertTo-Json

$response = Invoke-WebRequest `
    -Uri "http://127.0.0.1:9091/admin/accounts/batch" `
    -Method POST `
    -Headers @{"Content-Type" = "application/json"} `
    -Body $body

$result = $response.Content | ConvertFrom-Json

Write-Host "Added: $($result.added_count)"
Write-Host "Verified: $($result.verified_count)"

if ($result.failed_accounts) {
    Write-Host "Failed: $($result.failed_accounts.Count)"
    foreach ($failed in $result.failed_accounts) {
        Write-Host "  - $($failed.email): $($failed.error)"
    }
}
```

---

## Complete Workflow

**Step 1: Start Proxy**
```bash
python3 xoauth2_proxy_v2.py --host 0.0.0.0 --port 2525 --admin-port 9091
```

**Step 2: Prepare Accounts JSON**
```json
[
  {
    "email": "sales@gmail.com",
    "provider": "gmail",
    "client_id": "YOUR_CLIENT_ID",
    "client_secret": "YOUR_CLIENT_SECRET",
    "refresh_token": "YOUR_REFRESH_TOKEN"
  },
  ...
]
```

**Step 3: Add in Batch**
```bash
curl -X POST http://127.0.0.1:9091/admin/accounts/batch \
  -H "Content-Type: application/json" \
  -d @accounts.json
```

**Step 4: Verify Results**
```bash
curl http://127.0.0.1:9091/admin/accounts | jq '.accounts | length'
```

**Step 5: Test Accounts**
```bash
for email in sales@gmail.com support@gmail.com; do
  swaks --server 127.0.0.1:2525 \
    --auth-user "$email" \
    --auth-password placeholder \
    --from "$email" \
    --to test@example.com
done
```

---

## Performance Notes

- **Parallel Verification**: Processes accounts in batches of 50 (configurable)
- **Fast Add**: Omit `verify: true` to skip OAuth2 verification (instant)
- **Large Batches**: Up to 100 accounts per request
- **Typical Time**: 3-5 seconds for 100 verified accounts
- **Zero Downtime**: Changes apply immediately to running proxy

---

## Comparison: Single vs Batch Endpoint

| Operation | Single | Batch |
|-----------|--------|-------|
| Add 1 account | 1 request | 1 request |
| Add 5 accounts | 5 requests | 1 request ✅ |
| Add 100 accounts | 100 requests | 1 request ✅ |
| Verification | Serial | Parallel ✅ |
| Time for 100 | ~50+ seconds | ~3-5 seconds ✅ |
| Network calls | 100+ | 1 ✅ |

**Batch endpoint is significantly faster and more efficient!**
