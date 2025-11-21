# Partial Success Pattern - Batch Account Addition

## Overview

The batch account addition endpoint now supports **partial success** - saving successful accounts even when some fail verification.

---

## HTTP Status Codes

### ✅ 200 OK - Full Success
**When**: All accounts added successfully

**Response**:
```json
{
  "success": true,
  "message": "Added 50 accounts successfully",
  "total_accounts": 50,
  "added_count": 50
}
```

**Example**: Add 50 accounts, all 50 pass verification and are saved.

---

### ⚠️ 206 Partial Content - Partial Success
**When**: Some accounts succeeded, some failed

**Response**:
```json
{
  "success": "partial",
  "message": "Added 45 accounts, 5 failed",
  "total_accounts": 45,
  "added_count": 45,
  "failed_count": 5,
  "failed_accounts": [
    {
      "email": "bad1@outlook.com",
      "error": "Token refresh failed: invalid_grant"
    },
    {
      "email": "bad2@outlook.com",
      "error": "Request timeout"
    }
  ]
}
```

**What Happens**:
- ✅ 45 accounts with valid credentials are **saved and loaded**
- ❌ 5 accounts with invalid credentials are **rejected**
- ✅ You get details about which accounts failed and why

**Example**: Add 50 accounts, 45 pass verification, 5 fail due to bad credentials or timeouts. The 45 good accounts are saved.

---

### ❌ 400 Bad Request - All Failed
**When**: ALL accounts failed verification (none succeeded)

**Response**:
```json
{
  "success": false,
  "error": "All 50 accounts failed verification",
  "failed_accounts": [
    {
      "email": "bad1@outlook.com",
      "error": "Token refresh failed: invalid_grant"
    },
    ...
  ],
  "added_count": 0
}
```

**What Happens**:
- ❌ NO accounts are saved
- ❌ Nothing is loaded into the proxy
- You get details about why each account failed

**Example**: Add 50 accounts with expired/invalid refresh tokens. All fail verification, nothing is saved.

---

### ❌ 409 Conflict - Duplicates Exist
**When**: Accounts already exist and `overwrite` is not set

**Response**:
```json
{
  "success": false,
  "error": "25 accounts already exist. Use \"overwrite\": true to replace them.",
  "duplicates": ["existing1@outlook.com", "existing2@outlook.com", ...],
  "failed_accounts": []
}
```

**Solution**: Add `"overwrite": true` to any account in the batch to replace duplicates.

---

### ❌ 500 Internal Server Error - System Failure
**When**: File I/O error, permission denied, disk full, etc.

**Response**:
```json
{
  "success": false,
  "error": "Failed to save accounts to file"
}
```

**What Happens**:
- ❌ Accounts were verified successfully
- ❌ But failed to save to `accounts.json`
- Check file permissions and disk space

---

## Usage Examples

### Example 1: All Succeed (200)
```bash
curl -X POST http://0.0.0.0:9091/admin/accounts/batch \
  -H "Content-Type: application/json" \
  -d '[
    {"email": "acc1@outlook.com", "provider": "outlook", "client_id": "...", "refresh_token": "...", "verify": true},
    {"email": "acc2@outlook.com", "provider": "outlook", "client_id": "...", "refresh_token": "...", "verify": true}
  ]'

# Response: HTTP 200
{
  "success": true,
  "message": "Added 2 accounts successfully",
  "total_accounts": 2,
  "added_count": 2
}
```

---

### Example 2: Partial Success (206)
```bash
curl -X POST http://0.0.0.0:9091/admin/accounts/batch \
  -H "Content-Type: application/json" \
  -d '[
    {"email": "good1@outlook.com", "provider": "outlook", "client_id": "...", "refresh_token": "valid_token", "verify": true},
    {"email": "good2@outlook.com", "provider": "outlook", "client_id": "...", "refresh_token": "valid_token", "verify": true},
    {"email": "bad1@outlook.com", "provider": "outlook", "client_id": "...", "refresh_token": "expired_token", "verify": true}
  ]'

# Response: HTTP 206 (Partial Content)
{
  "success": "partial",
  "message": "Added 2 accounts, 1 failed",
  "total_accounts": 2,
  "added_count": 2,
  "failed_count": 1,
  "failed_accounts": [
    {
      "email": "bad1@outlook.com",
      "error": "Token refresh failed: invalid_grant"
    }
  ]
}
```

**What happened**:
- ✅ `good1@outlook.com` and `good2@outlook.com` were saved and loaded
- ❌ `bad1@outlook.com` failed verification and was NOT saved
- You can now fix `bad1@outlook.com` credentials and add it separately

---

### Example 3: All Failed (400)
```bash
curl -X POST http://0.0.0.0:9091/admin/accounts/batch \
  -H "Content-Type: application/json" \
  -d '[
    {"email": "bad1@outlook.com", "provider": "outlook", "client_id": "...", "refresh_token": "expired1", "verify": true},
    {"email": "bad2@outlook.com", "provider": "outlook", "client_id": "...", "refresh_token": "expired2", "verify": true}
  ]'

# Response: HTTP 400
{
  "success": false,
  "error": "All 2 accounts failed verification",
  "failed_accounts": [
    {"email": "bad1@outlook.com", "error": "Token refresh failed: invalid_grant"},
    {"email": "bad2@outlook.com", "error": "Token refresh failed: invalid_grant"}
  ],
  "added_count": 0
}
```

---

## Benefits

### Before Partial Success:
- ❌ Add 50 accounts, 1 has bad credentials
- ❌ Entire batch fails with HTTP 400
- ❌ NO accounts saved (even the 49 good ones)
- ❌ Hard to know which account failed
- ❌ Must manually split batch and retry

### After Partial Success:
- ✅ Add 50 accounts, 1 has bad credentials
- ✅ 49 good accounts are **saved and working**
- ✅ 1 bad account is **clearly identified**
- ✅ HTTP 206 indicates partial success
- ✅ Can immediately fix the 1 bad account and retry just that one

---

## Response Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean/"partial" | `true` (all succeeded), `"partial"` (some failed), `false` (all failed or error) |
| `message` | string | Human-readable summary |
| `total_accounts` | number | Total accounts now in system |
| `added_count` | number | How many accounts were added in this batch |
| `failed_count` | number | How many accounts failed (only in 206 response) |
| `failed_accounts` | array | List of failed accounts with error details (in 206, 400) |
| `error` | string | Error message (in 400, 409, 500) |

---

## Handling Responses in Your Code

### Python Example
```python
import requests

response = requests.post('http://0.0.0.0:9091/admin/accounts/batch', json=accounts)

if response.status_code == 200:
    print(f"✅ All {response.json()['added_count']} accounts added successfully!")

elif response.status_code == 206:
    data = response.json()
    print(f"⚠️  Partial success: {data['added_count']} added, {data['failed_count']} failed")
    print(f"Failed accounts:")
    for failed in data['failed_accounts']:
        print(f"  - {failed['email']}: {failed['error']}")

elif response.status_code == 400:
    data = response.json()
    print(f"❌ All accounts failed: {data['error']}")
    for failed in data['failed_accounts']:
        print(f"  - {failed['email']}: {failed['error']}")

elif response.status_code == 409:
    print(f"❌ Duplicates exist. Add 'overwrite': true to replace them.")

elif response.status_code == 500:
    print(f"❌ Server error: {response.json()['error']}")
```

---

## Testing

### Test 1: All Valid (expect 200)
```bash
# Add 10 accounts with valid credentials
curl -X POST http://0.0.0.0:9091/admin/accounts/batch -H "Content-Type: application/json" -d @valid_accounts.json
# Should return HTTP 200
```

### Test 2: Mixed Valid/Invalid (expect 206)
```bash
# Add 10 accounts: 8 valid, 2 with expired tokens
curl -X POST http://0.0.0.0:9091/admin/accounts/batch -H "Content-Type: application/json" -d @mixed_accounts.json
# Should return HTTP 206 with 8 added, 2 failed
```

### Test 3: All Invalid (expect 400)
```bash
# Add 10 accounts with all expired tokens
curl -X POST http://0.0.0.0:9091/admin/accounts/batch -H "Content-Type: application/json" -d @invalid_accounts.json
# Should return HTTP 400 with 0 added
```

---

## Migration Guide

If you have existing code that expects HTTP 200 or 400 only:

**Old Code**:
```python
if response.status_code == 200:
    print("Success!")
else:
    print("Failed!")
```

**New Code** (handles partial success):
```python
if response.status_code in [200, 206]:
    data = response.json()
    print(f"Added {data['added_count']} accounts")

    if response.status_code == 206:
        print(f"Warning: {data['failed_count']} accounts failed")
        # Handle failures
else:
    print("Failed!")
```

---

## Summary

The partial success pattern provides:
- ✅ **Better UX**: Don't lose good accounts just because one is bad
- ✅ **Clear feedback**: Know exactly which accounts failed and why
- ✅ **Faster workflow**: No need to manually split and retry batches
- ✅ **Standard HTTP codes**: 200 (success), 206 (partial), 400 (all failed), 500 (server error)
