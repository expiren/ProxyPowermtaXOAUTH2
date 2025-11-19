# Account Deletion Guide

Complete guide for deleting accounts from the XOAUTH2 Proxy using the Admin HTTP API.

---

## 📋 Available DELETE Operations

| Operation | Endpoint | Description |
|-----------|----------|-------------|
| Delete specific account | `DELETE /admin/accounts/{email}` | Remove one account by email |
| Delete all accounts | `DELETE /admin/accounts?confirm=true` | Remove all accounts (requires confirmation) |
| Delete invalid accounts | `DELETE /admin/accounts/invalid` | Remove accounts with bad OAuth2 credentials |

**Base URL:** `http://YOUR_SERVER_IP:9090`

---

## 1️⃣ Delete Specific Account

Remove a single account by email address.

### **cURL**

```bash
curl -X DELETE http://203.0.113.50:9090/admin/accounts/sales@gmail.com
```

**Success Response (200):**
```json
{
  "success": true,
  "message": "Account sales@gmail.com deleted successfully",
  "total_accounts": 4
}
```

**Error - Not Found (404):**
```json
{
  "success": false,
  "error": "Account sales@gmail.com not found"
}
```

### **Python**

```python
import requests

PROXY_URL = "http://203.0.113.50:9090"

def delete_account(email):
    """Delete a specific account"""
    response = requests.delete(f"{PROXY_URL}/admin/accounts/{email}")

    if response.status_code == 200:
        result = response.json()
        print(f"✓ {result['message']}")
        print(f"Remaining accounts: {result['total_accounts']}")
        return True
    else:
        error = response.json()
        print(f"✗ Error: {error['error']}")
        return False

# Example usage
delete_account("sales@gmail.com")
```

### **Node.js**

```javascript
const axios = require('axios');

const PROXY_URL = 'http://203.0.113.50:9090';

async function deleteAccount(email) {
    try {
        const response = await axios.delete(`${PROXY_URL}/admin/accounts/${email}`);

        console.log(`✓ ${response.data.message}`);
        console.log(`Remaining accounts: ${response.data.total_accounts}`);
        return true;
    } catch (error) {
        console.log(`✗ Error: ${error.response.data.error}`);
        return false;
    }
}

// Example usage
deleteAccount('sales@gmail.com');
```

### **PHP**

```php
<?php
$proxyUrl = "http://203.0.113.50:9090";

function deleteAccount($email) {
    global $proxyUrl;

    $options = array(
        'http' => array(
            'method' => 'DELETE'
        )
    );

    $context = stream_context_create($options);
    $result = file_get_contents("$proxyUrl/admin/accounts/$email", false, $context);

    if ($result === FALSE) {
        echo "✗ Failed to delete account\n";
        return false;
    }

    $response = json_decode($result, true);

    if ($response['success']) {
        echo "✓ " . $response['message'] . "\n";
        echo "Remaining accounts: " . $response['total_accounts'] . "\n";
        return true;
    } else {
        echo "✗ Error: " . $response['error'] . "\n";
        return false;
    }
}

// Example usage
deleteAccount('sales@gmail.com');
?>
```

### **PowerShell**

```powershell
$ProxyUrl = "http://203.0.113.50:9090"

function Remove-Account {
    param([string]$Email)

    try {
        $response = Invoke-RestMethod `
            -Uri "$ProxyUrl/admin/accounts/$Email" `
            -Method DELETE

        if ($response.success) {
            Write-Host "✓ $($response.message)" -ForegroundColor Green
            Write-Host "Remaining accounts: $($response.total_accounts)"
            return $true
        }
    }
    catch {
        $errorResponse = $_.ErrorDetails.Message | ConvertFrom-Json
        Write-Host "✗ Error: $($errorResponse.error)" -ForegroundColor Red
        return $false
    }
}

# Example usage
Remove-Account -Email "sales@gmail.com"
```

---

## 2️⃣ Delete All Accounts

Remove **all accounts** at once. Requires `?confirm=true` to prevent accidents.

### **cURL**

```bash
# Without confirmation (will fail)
curl -X DELETE http://203.0.113.50:9090/admin/accounts

# With confirmation (will succeed)
curl -X DELETE "http://203.0.113.50:9090/admin/accounts?confirm=true"
```

**Success Response (200):**
```json
{
  "success": true,
  "message": "All accounts deleted (5 accounts removed)",
  "total_accounts": 0
}
```

**Error - Missing Confirmation (400):**
```json
{
  "success": false,
  "error": "Confirmation required. Use ?confirm=true to delete all accounts"
}
```

### **Python**

```python
import requests

PROXY_URL = "http://203.0.113.50:9090"

def delete_all_accounts(confirm=False):
    """Delete all accounts (requires confirmation)"""

    if not confirm:
        print("⚠️  Warning: This will delete ALL accounts!")
        user_confirm = input("Type 'yes' to confirm: ")
        if user_confirm.lower() != 'yes':
            print("Cancelled.")
            return False

    response = requests.delete(
        f"{PROXY_URL}/admin/accounts",
        params={'confirm': 'true'}
    )

    if response.status_code == 200:
        result = response.json()
        print(f"✓ {result['message']}")
        return True
    else:
        error = response.json()
        print(f"✗ Error: {error['error']}")
        return False

# Example usage
delete_all_accounts()
```

### **Node.js**

```javascript
const axios = require('axios');

const PROXY_URL = 'http://203.0.113.50:9090';

async function deleteAllAccounts() {
    try {
        const response = await axios.delete(`${PROXY_URL}/admin/accounts`, {
            params: { confirm: 'true' }
        });

        console.log(`✓ ${response.data.message}`);
        return true;
    } catch (error) {
        console.log(`✗ Error: ${error.response.data.error}`);
        return false;
    }
}

// Example usage
deleteAllAccounts();
```

### **Bash Script with Confirmation**

```bash
#!/bin/bash

PROXY_URL="http://203.0.113.50:9090"

delete_all_accounts() {
    echo "⚠️  WARNING: This will delete ALL accounts!"
    read -p "Type 'yes' to confirm: " confirm

    if [ "$confirm" != "yes" ]; then
        echo "Cancelled."
        return 1
    fi

    response=$(curl -s -X DELETE "${PROXY_URL}/admin/accounts?confirm=true")

    success=$(echo "$response" | jq -r '.success')
    message=$(echo "$response" | jq -r '.message')

    if [ "$success" = "true" ]; then
        echo "✓ $message"
        return 0
    else
        error=$(echo "$response" | jq -r '.error')
        echo "✗ Error: $error"
        return 1
    fi
}

# Example usage
delete_all_accounts
```

---

## 3️⃣ Delete Invalid Accounts (Auto-Clean)

Automatically test and remove accounts with bad OAuth2 credentials.

**This is extremely useful for:**
- Cleaning up expired refresh tokens
- Removing revoked OAuth2 access
- Periodic maintenance (cron job)

### **cURL**

```bash
curl -X DELETE http://203.0.113.50:9090/admin/accounts/invalid
```

**Success Response - Invalid Accounts Found (200):**
```json
{
  "success": true,
  "message": "Deleted 3 invalid accounts",
  "total_accounts": 7,
  "deleted_count": 3,
  "deleted_accounts": [
    "expired@gmail.com",
    "revoked@outlook.com",
    "bad@gmail.com"
  ]
}
```

**Success Response - All Accounts Valid (200):**
```json
{
  "success": true,
  "message": "No invalid accounts found",
  "total_accounts": 10,
  "deleted_count": 0,
  "deleted_accounts": []
}
```

### **Python**

```python
import requests

PROXY_URL = "http://203.0.113.50:9090"

def delete_invalid_accounts():
    """Delete accounts with bad OAuth2 credentials"""

    print("🔍 Testing all accounts for validity...")

    response = requests.delete(f"{PROXY_URL}/admin/accounts/invalid")

    if response.status_code == 200:
        result = response.json()
        print(f"✓ {result['message']}")

        if result['deleted_count'] > 0:
            print(f"Deleted accounts:")
            for email in result['deleted_accounts']:
                print(f"  - {email}")

        print(f"Remaining accounts: {result['total_accounts']}")
        return True
    else:
        error = response.json()
        print(f"✗ Error: {error['error']}")
        return False

# Example usage
delete_invalid_accounts()
```

### **Node.js**

```javascript
const axios = require('axios');

const PROXY_URL = 'http://203.0.113.50:9090';

async function deleteInvalidAccounts() {
    try {
        console.log('🔍 Testing all accounts for validity...');

        const response = await axios.delete(`${PROXY_URL}/admin/accounts/invalid`);

        console.log(`✓ ${response.data.message}`);

        if (response.data.deleted_count > 0) {
            console.log('Deleted accounts:');
            response.data.deleted_accounts.forEach(email => {
                console.log(`  - ${email}`);
            });
        }

        console.log(`Remaining accounts: ${response.data.total_accounts}`);
        return true;
    } catch (error) {
        console.log(`✗ Error: ${error.response.data.error}`);
        return false;
    }
}

// Example usage
deleteInvalidAccounts();
```

### **Cron Job for Automatic Cleanup**

Add to crontab to clean invalid accounts daily:

```bash
# Edit crontab
crontab -e

# Add this line (runs daily at 3 AM)
0 3 * * * curl -X DELETE http://203.0.113.50:9090/admin/accounts/invalid >> /var/log/xoauth2/cleanup.log 2>&1
```

Or use a Python script:

```bash
# cleanup_invalid.py
#!/usr/bin/env python3
import requests
import logging
from datetime import datetime

logging.basicConfig(
    filename='/var/log/xoauth2/cleanup.log',
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)

PROXY_URL = "http://127.0.0.1:9090"

def cleanup():
    logging.info("Starting invalid account cleanup...")

    try:
        response = requests.delete(f"{PROXY_URL}/admin/accounts/invalid")
        result = response.json()

        if result['success']:
            logging.info(f"✓ {result['message']}")
            if result['deleted_count'] > 0:
                logging.info(f"Deleted: {', '.join(result['deleted_accounts'])}")
        else:
            logging.error(f"✗ {result['error']}")

    except Exception as e:
        logging.error(f"✗ Error: {e}")

if __name__ == '__main__':
    cleanup()
```

```bash
# Make executable
chmod +x cleanup_invalid.py

# Add to crontab
0 3 * * * /path/to/cleanup_invalid.py
```

---

## 📊 Response Summary

### Success Codes

| Status | Meaning |
|--------|---------|
| 200 OK | Account(s) deleted successfully |

### Error Codes

| Status | Meaning |
|--------|---------|
| 400 Bad Request | Invalid email format or missing confirmation |
| 404 Not Found | Account not found or no accounts to delete |
| 500 Internal Server Error | Server error (check logs) |

---

## 🔄 Bulk Delete Script

Delete multiple specific accounts:

```python
import requests

PROXY_URL = "http://203.0.113.50:9090"

def bulk_delete_accounts(emails):
    """Delete multiple accounts"""

    success_count = 0
    error_count = 0

    for email in emails:
        response = requests.delete(f"{PROXY_URL}/admin/accounts/{email}")

        if response.status_code == 200:
            result = response.json()
            print(f"✓ Deleted: {email}")
            success_count += 1
        else:
            error = response.json()
            print(f"✗ Failed: {email} - {error['error']}")
            error_count += 1

    print(f"\n✓ Success: {success_count}")
    print(f"✗ Failed: {error_count}")

# Example usage
accounts_to_delete = [
    "old1@gmail.com",
    "old2@gmail.com",
    "expired@outlook.com"
]

bulk_delete_accounts(accounts_to_delete)
```

---

## 🛡️ Safety Features

### 1. **Delete All Requires Confirmation**
```bash
# This will FAIL (safety check)
curl -X DELETE http://203.0.113.50:9090/admin/accounts

# This will SUCCEED (explicit confirmation)
curl -X DELETE "http://203.0.113.50:9090/admin/accounts?confirm=true"
```

### 2. **Automatic Hot-Reload**
After any deletion, accounts are automatically reloaded (zero downtime).

### 3. **Detailed Logging**
All deletions are logged:
```
[AdminServer] Account sales@gmail.com deleted successfully (4 remaining)
[AdminServer] Accounts reloaded: 4 accounts active
```

### 4. **Invalid Account Testing**
Each account is tested individually before deletion.

---

## 📝 Complete API Reference

| Method | Endpoint | Description | Parameters |
|--------|----------|-------------|------------|
| DELETE | `/admin/accounts/{email}` | Delete specific account | `email` (path param) |
| DELETE | `/admin/accounts` | Delete all accounts | `confirm=true` (query param) required |
| DELETE | `/admin/accounts/invalid` | Delete invalid accounts | None |

---

## 🔧 Common Use Cases

### **1. Remove Expired Account**
```bash
curl -X DELETE http://203.0.113.50:9090/admin/accounts/expired@gmail.com
```

### **2. Clean Up Before Migration**
```bash
# Test for invalid accounts
curl -X DELETE http://203.0.113.50:9090/admin/accounts/invalid

# Then delete all
curl -X DELETE "http://203.0.113.50:9090/admin/accounts?confirm=true"
```

### **3. Daily Maintenance**
```bash
# Cron job to remove invalid accounts daily
0 3 * * * curl -X DELETE http://127.0.0.1:9090/admin/accounts/invalid
```

### **4. Remove Test Accounts**
```python
test_accounts = ["test1@gmail.com", "test2@gmail.com", "test3@gmail.com"]

for email in test_accounts:
    requests.delete(f"http://203.0.113.50:9090/admin/accounts/{email}")
```

---

## ⚠️ Important Notes

1. **Deletions are permanent** - Accounts cannot be recovered after deletion
2. **Confirmation required** - Delete all requires `?confirm=true`
3. **Hot-reload automatic** - Accounts are reloaded immediately after deletion
4. **Logs maintained** - All deletions are logged for audit trail
5. **Invalid detection** - Tests OAuth2 credentials before deletion

---

## 📞 Related Documentation

- **Add Accounts:** `docs/REMOTE_ACCOUNT_MANAGEMENT.md`
- **Admin API:** `docs/ADMIN_API.md`
- **Account Setup:** `SETUP_ACCOUNTS.md`
