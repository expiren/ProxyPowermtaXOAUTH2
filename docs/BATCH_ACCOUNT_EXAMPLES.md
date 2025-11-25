# Batch Add Accounts - Complete Examples

## Quick Start: Add Multiple Accounts at Once

### Option 1: Bash Script with Loop

```bash
#!/bin/bash

# Array of accounts to add
declare -a accounts=(
  '{"account_id":"gmail_01","email":"sales@gmail.com","provider":"gmail","client_id":"123456789-abc.apps.googleusercontent.com","client_secret":"GOCSPX-abc123def456","refresh_token":"1//0gABC123DEF456..."}'
  '{"account_id":"gmail_02","email":"support@gmail.com","provider":"gmail","client_id":"123456789-abc.apps.googleusercontent.com","client_secret":"GOCSPX-abc123def456","refresh_token":"1//0gXYZ789JKL012..."}'
  '{"account_id":"outlook_01","email":"sales@outlook.com","provider":"outlook","client_id":"xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx","refresh_token":"0.AYXXX..."}'
  '{"account_id":"outlook_02","email":"support@outlook.com","provider":"outlook","client_id":"xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx","refresh_token":"0.AYZZZ..."}'
)

echo "Adding ${#accounts[@]} accounts..."

for i in "${!accounts[@]}"; do
  account=${accounts[$i]}

  echo "[$(($i+1))/${#accounts[@]}] Adding account..."

  response=$(curl -s -X POST http://127.0.0.1:9091/admin/accounts \
    -H "Content-Type: application/json" \
    -d "$account")

  status=$(echo "$response" | jq -r '.status')
  message=$(echo "$response" | jq -r '.message')

  if [ "$status" = "success" ]; then
    email=$(echo "$account" | jq -r '.email')
    echo "[OK] $email - $message"
  else:
    echo "[ERROR] $message"
  fi
done

echo "Done!"
```

---

### Option 2: Python Script (Recommended)

```python
import requests
import json
from datetime import datetime

# Define accounts to add
ACCOUNTS = [
    {
        "account_id": "gmail_01",
        "email": "sales@gmail.com",
        "provider": "gmail",
        "client_id": "123456789-abc.apps.googleusercontent.com",
        "client_secret": "GOCSPX-abc123def456",
        "refresh_token": "1//0gABC123DEF456..."
    },
    {
        "account_id": "gmail_02",
        "email": "support@gmail.com",
        "provider": "gmail",
        "client_id": "123456789-abc.apps.googleusercontent.com",
        "client_secret": "GOCSPX-abc123def456",
        "refresh_token": "1//0gXYZ789JKL012..."
    },
    {
        "account_id": "gmail_03",
        "email": "noreply@gmail.com",
        "provider": "gmail",
        "client_id": "123456789-abc.apps.googleusercontent.com",
        "client_secret": "GOCSPX-abc123def456",
        "refresh_token": "1//0gMNO456PQR789..."
    },
    {
        "account_id": "outlook_01",
        "email": "sales@outlook.com",
        "provider": "outlook",
        "client_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
        "refresh_token": "0.AYXXX..."
    },
    {
        "account_id": "outlook_02",
        "email": "support@outlook.com",
        "provider": "outlook",
        "client_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
        "refresh_token": "0.AYZZZ..."
    }
]

API_URL = "http://127.0.0.1:9091/admin/accounts"
HEADERS = {"Content-Type": "application/json"}

def add_account(account):
    """Add single account via API"""
    try:
        response = requests.post(
            API_URL,
            json=account,
            headers=HEADERS,
            timeout=10
        )

        if response.status_code == 200:
            result = response.json()
            return result['status'] == 'success', result.get('message')
        else:
            return False, f"HTTP {response.status_code}: {response.text}"

    except Exception as e:
        return False, str(e)

def add_accounts_batch(accounts, verify=False):
    """Add multiple accounts"""
    print(f"\n{'='*70}")
    print(f"BATCH ADD ACCOUNTS - {len(accounts)} accounts")
    print(f"{'='*70}")
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    success_count = 0
    error_count = 0
    results = []

    for i, account in enumerate(accounts, 1):
        email = account.get('email')
        provider = account.get('provider')
        account_id = account.get('account_id')

        # Add verify flag if specified
        if verify:
            account['verify'] = True

        print(f"[{i}/{len(accounts)}] Adding: {email} ({provider})...", end=" ")

        success, message = add_account(account)

        if success:
            print(f"[OK]")
            success_count += 1
            results.append({
                'account_id': account_id,
                'email': email,
                'status': 'success',
                'message': message
            })
        else:
            print(f"[ERROR]")
            print(f"         {message}")
            error_count += 1
            results.append({
                'account_id': account_id,
                'email': email,
                'status': 'error',
                'message': message
            })

    # Print summary
    print(f"\n{'='*70}")
    print(f"SUMMARY")
    print(f"{'='*70}")
    print(f"Total:    {len(accounts)}")
    print(f"Success:  {success_count}")
    print(f"Errors:   {error_count}")
    print(f"Duration: {len(accounts)} accounts added")
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Print detailed results
    if results:
        print(f"{'='*70}")
        print(f"DETAILED RESULTS")
        print(f"{'='*70}")
        for result in results:
            status_symbol = "[OK]" if result['status'] == 'success' else "[ERROR]"
            print(f"{status_symbol} {result['email']:30} {result['message']}")

    return success_count, error_count

if __name__ == "__main__":
    success, errors = add_accounts_batch(ACCOUNTS)

    if errors == 0:
        print("\nAll accounts added successfully!")
        exit(0)
    else:
        print(f"\n{errors} account(s) failed to add.")
        exit(1)
```

---

### Option 3: PowerShell Script

```powershell
# Define accounts to add
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
        account_id = "gmail_02"
        email = "support@gmail.com"
        provider = "gmail"
        client_id = "123456789-abc.apps.googleusercontent.com"
        client_secret = "GOCSPX-abc123def456"
        refresh_token = "1//0gXYZ789JKL012..."
    },
    @{
        account_id = "outlook_01"
        email = "sales@outlook.com"
        provider = "outlook"
        client_id = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
        refresh_token = "0.AYXXX..."
    },
    @{
        account_id = "outlook_02"
        email = "support@outlook.com"
        provider = "outlook"
        client_id = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
        refresh_token = "0.AYZZZ..."
    }
)

$apiUrl = "http://127.0.0.1:9091/admin/accounts"
$successCount = 0
$errorCount = 0
$results = @()

Write-Host "=================================="
Write-Host "BATCH ADD ACCOUNTS"
Write-Host "=================================="
Write-Host "Total accounts: $($accounts.Count)`n"

foreach ($i in 0..($accounts.Count - 1)) {
    $account = $accounts[$i]
    $email = $account.email
    $provider = $account.provider
    $num = $i + 1

    Write-Host "[$num/$($accounts.Count)] Adding: $email ($provider)... " -NoNewline

    try {
        $body = $account | ConvertTo-Json

        $response = Invoke-WebRequest `
            -Uri $apiUrl `
            -Method POST `
            -Headers @{"Content-Type" = "application/json"} `
            -Body $body `
            -TimeoutSec 10

        $result = $response.Content | ConvertFrom-Json

        if ($result.status -eq "success") {
            Write-Host "[OK]" -ForegroundColor Green
            $successCount++
            $results += @{
                email = $email
                status = "success"
                message = $result.message
            }
        } else {
            Write-Host "[ERROR]" -ForegroundColor Red
            Write-Host "         $($result.message)" -ForegroundColor Yellow
            $errorCount++
            $results += @{
                email = $email
                status = "error"
                message = $result.message
            }
        }
    }
    catch {
        Write-Host "[ERROR]" -ForegroundColor Red
        Write-Host "         $($_.Exception.Message)" -ForegroundColor Yellow
        $errorCount++
    }
}

# Print summary
Write-Host "`n=================================="
Write-Host "SUMMARY"
Write-Host "=================================="
Write-Host "Total:   $($accounts.Count)"
Write-Host "Success: $successCount" -ForegroundColor Green
Write-Host "Errors:  $errorCount" -ForegroundColor Red
Write-Host ""

if ($errorCount -eq 0) {
    Write-Host "All accounts added successfully!" -ForegroundColor Green
} else {
    Write-Host "$errorCount account(s) failed to add." -ForegroundColor Yellow
}
```

---

### Option 4: JSON File + Batch Script

**accounts_to_add.json:**
```json
[
  {
    "account_id": "gmail_01",
    "email": "sales@gmail.com",
    "provider": "gmail",
    "client_id": "123456789-abc.apps.googleusercontent.com",
    "client_secret": "GOCSPX-abc123def456",
    "refresh_token": "1//0gABC123DEF456..."
  },
  {
    "account_id": "gmail_02",
    "email": "support@gmail.com",
    "provider": "gmail",
    "client_id": "123456789-abc.apps.googleusercontent.com",
    "client_secret": "GOCSPX-abc123def456",
    "refresh_token": "1//0gXYZ789JKL012..."
  },
  {
    "account_id": "gmail_03",
    "email": "noreply@gmail.com",
    "provider": "gmail",
    "client_id": "123456789-abc.apps.googleusercontent.com",
    "client_secret": "GOCSPX-abc123def456",
    "refresh_token": "1//0gMNO456PQR789..."
  },
  {
    "account_id": "outlook_01",
    "email": "sales@outlook.com",
    "provider": "outlook",
    "client_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "refresh_token": "0.AYXXX..."
  },
  {
    "account_id": "outlook_02",
    "email": "support@outlook.com",
    "provider": "outlook",
    "client_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "refresh_token": "0.AYZZZ..."
  }
]
```

**batch_add.py:**
```python
import json
import requests
from pathlib import Path

def load_accounts_from_file(filepath):
    """Load accounts from JSON file"""
    with open(filepath, 'r') as f:
        return json.load(f)

def add_account_batch_from_file(filepath):
    """Add accounts from JSON file"""
    accounts = load_accounts_from_file(filepath)

    print(f"\nLoading {len(accounts)} accounts from {filepath}...\n")

    api_url = "http://127.0.0.1:9091/admin/accounts"
    success = 0
    failed = 0

    for i, account in enumerate(accounts, 1):
        email = account.get('email')
        print(f"[{i}/{len(accounts)}] Adding {email}...", end=" ")

        try:
            response = requests.post(
                api_url,
                json=account,
                headers={"Content-Type": "application/json"},
                timeout=10
            )

            result = response.json()
            if result['status'] == 'success':
                print("[OK]")
                success += 1
            else:
                print(f"[ERROR] {result['message']}")
                failed += 1
        except Exception as e:
            print(f"[ERROR] {str(e)}")
            failed += 1

    print(f"\nDone: {success} success, {failed} failed")
    return success, failed

if __name__ == "__main__":
    success, failed = add_account_batch_from_file("accounts_to_add.json")
    exit(0 if failed == 0 else 1)
```

---

## Real-World Batch Examples

### Example 1: 10 Gmail Accounts (Same Client ID)

```python
import requests

# Same client ID for all (e.g., corporate Gmail app)
CLIENT_ID = "123456789-abc.apps.googleusercontent.com"
CLIENT_SECRET = "GOCSPX-abc123def456"

accounts = []
emails = [
    "sales@gmail.com",
    "support@gmail.com",
    "noreply@gmail.com",
    "billing@gmail.com",
    "info@gmail.com",
    "contact@gmail.com",
    "marketing@gmail.com",
    "admin@gmail.com",
    "team@gmail.com",
    "postmaster@gmail.com",
]

tokens = [
    "1//0gABC123DEF456...",
    "1//0gXYZ789JKL012...",
    "1//0gMNO456PQR789...",
    "1//0gSTU012VWX345...",
    "1//0gYZA678BCD901...",
    "1//0gEFG234HIJ567...",
    "1//0gKLM890NOP123...",
    "1//0gQRS456TUV789...",
    "1//0gWXY012ZAB345...",
    "1//0gCDE678FGH901...",
]

for i, (email, token) in enumerate(zip(emails, tokens), 1):
    account = {
        "account_id": f"gmail_{i:02d}",
        "email": email,
        "provider": "gmail",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": token
    }
    accounts.append(account)

# Add all accounts
for i, account in enumerate(accounts, 1):
    print(f"[{i}/{len(accounts)}] Adding {account['email']}...", end=" ")

    response = requests.post(
        "http://127.0.0.1:9091/admin/accounts",
        json=account,
        headers={"Content-Type": "application/json"}
    )

    if response.json()['status'] == 'success':
        print("[OK]")
    else:
        print("[ERROR]")
```

---

### Example 2: Mixed Providers (5 Gmail + 5 Outlook)

```python
import requests

API_URL = "http://127.0.0.1:9091/admin/accounts"

accounts = [
    # Gmail accounts
    {
        "account_id": "gmail_01",
        "email": "sales@gmail.com",
        "provider": "gmail",
        "client_id": "123456789-abc.apps.googleusercontent.com",
        "client_secret": "GOCSPX-abc123def456",
        "refresh_token": "1//0gABC123DEF456..."
    },
    {
        "account_id": "gmail_02",
        "email": "support@gmail.com",
        "provider": "gmail",
        "client_id": "123456789-abc.apps.googleusercontent.com",
        "client_secret": "GOCSPX-abc123def456",
        "refresh_token": "1//0gXYZ789JKL012..."
    },
    # ... 3 more Gmail accounts ...

    # Outlook accounts
    {
        "account_id": "outlook_01",
        "email": "sales@outlook.com",
        "provider": "outlook",
        "client_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
        "refresh_token": "0.AYXXX..."
    },
    {
        "account_id": "outlook_02",
        "email": "support@outlook.com",
        "provider": "outlook",
        "client_id": "yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy",
        "refresh_token": "0.AYZZZ..."
    },
    # ... 3 more Outlook accounts ...
]

success = 0
for i, account in enumerate(accounts, 1):
    response = requests.post(API_URL, json=account)
    if response.json()['status'] == 'success':
        success += 1
        print(f"[{i}/{len(accounts)}] {account['email']} - OK")
    else:
        print(f"[{i}/{len(accounts)}] {account['email']} - ERROR")

print(f"\nResult: {success}/{len(accounts)} success")
```

---

### Example 3: Batch with Retry Logic

```python
import requests
import time

def add_account_with_retry(account, max_retries=3, delay=2):
    """Add account with retry logic"""
    api_url = "http://127.0.0.1:9091/admin/accounts"

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(
                api_url,
                json=account,
                headers={"Content-Type": "application/json"},
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                if result['status'] == 'success':
                    return True, result['message']

            if attempt < max_retries:
                print(f"  Retry {attempt}/{max_retries - 1}...")
                time.sleep(delay)

        except Exception as e:
            if attempt < max_retries:
                print(f"  Retry {attempt}/{max_retries - 1}...")
                time.sleep(delay)
            else:
                return False, str(e)

    return False, "Max retries exceeded"

# Batch add with retries
accounts = [...]  # Your accounts list

for i, account in enumerate(accounts, 1):
    email = account['email']
    print(f"[{i}/{len(accounts)}] Adding {email}...", end=" ")

    success, message = add_account_with_retry(account)

    if success:
        print("[OK]")
    else:
        print(f"[ERROR] {message}")
```

---

## Batch Operations

### List All Accounts After Batch Add

```bash
curl -X GET http://127.0.0.1:9091/admin/accounts | jq '.'
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
      "account_id": "gmail_02",
      "email": "support@gmail.com",
      "provider": "gmail"
    },
    {
      "account_id": "outlook_01",
      "email": "sales@outlook.com",
      "provider": "outlook"
    }
  ]
}
```

---

### Test Batch with Proxy

**swaks (SMTP testing tool):**
```bash
#!/bin/bash

# Test all accounts with swaks
accounts=(
  "sales@gmail.com"
  "support@gmail.com"
  "sales@outlook.com"
  "support@outlook.com"
)

for email in "${accounts[@]}"; do
  echo "Testing $email..."

  swaks --server 127.0.0.1:2525 \
    --auth-user "$email" \
    --auth-password placeholder \
    --from "$email" \
    --to test@example.com \
    --body "Test from $email"

  if [ $? -eq 0 ]; then
    echo "  [OK] $email works"
  else
    echo "  [ERROR] $email failed"
  fi
done
```

---

## Performance Tips

### Batch Add 100+ Accounts Efficiently

```python
import requests
import concurrent.futures
import time

def add_account_fast(account):
    """Add single account (for parallel execution)"""
    try:
        response = requests.post(
            "http://127.0.0.1:9091/admin/accounts",
            json=account,
            timeout=10
        )
        return account['email'], response.json()['status'] == 'success'
    except:
        return account['email'], False

def batch_add_parallel(accounts, max_workers=5):
    """Add accounts in parallel (faster)"""
    print(f"Adding {len(accounts)} accounts in parallel (max {max_workers} workers)...")

    success = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(add_account_fast, acc) for acc in accounts]

        for i, future in enumerate(concurrent.futures.as_completed(futures), 1):
            email, result = future.result()
            status = "[OK]" if result else "[ERROR]"
            print(f"[{i}/{len(accounts)}] {email} {status}")
            if result:
                success += 1

    print(f"Done: {success}/{len(accounts)} success")

# Usage
accounts = [...]  # 100+ accounts
batch_add_parallel(accounts, max_workers=5)
```

---

## Summary

**Best Option by Use Case:**

| Scenario | Recommended |
|----------|-------------|
| Simple, few accounts | Bash loop or Python script |
| Many accounts (100+) | Python with parallel execution |
| Windows environment | PowerShell script |
| Load from file | JSON + Python batch script |
| Need retries | Python with retry logic |
| Scheduled adds | Cron job + Python script |
