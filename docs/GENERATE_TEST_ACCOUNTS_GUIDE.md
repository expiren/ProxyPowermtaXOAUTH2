# Generate Test Accounts Guide

**Purpose**: Generate `accounts.json` with test accounts for SMTP load testing

---

## Quick Start

### Option 1: Generate Default Test Accounts (Fastest)

```bash
python generate_test_accounts.py --skip-input
```

This creates `accounts.json` with 4 default test accounts:
- 2 Gmail accounts
- 2 Outlook accounts

**Output**:
```
✓ Accounts saved to: /path/to/accounts.json
```

### Option 2: Interactive Mode (Recommended)

```bash
python generate_test_accounts.py
```

Follow the prompts:
1. Choose to use defaults or create custom accounts
2. If custom, enter each account's credentials
3. Review the summary
4. Save to file

### Option 3: Show What Would Be Generated

```bash
python generate_test_accounts.py --show-defaults
```

Shows the 4 default accounts without saving anything.

---

## Generated Accounts

### Default Test Accounts

The generator creates these 4 test accounts:

```json
[
  {
    "account_id": "gmail_test_01",
    "email": "test.account1@gmail.com",
    "provider": "gmail",
    "oauth_endpoint": "smtp.gmail.com:587",
    "oauth_token_url": "https://oauth2.googleapis.com/token",
    "client_id": "YOUR_GMAIL_CLIENT_ID.apps.googleusercontent.com",
    "client_secret": "YOUR_GMAIL_CLIENT_SECRET",
    "refresh_token": "YOUR_GMAIL_REFRESH_TOKEN",
    "ip_address": "",
    "vmta_name": "vmta-gmail-test-01"
  },
  {
    "account_id": "gmail_test_02",
    "email": "test.account2@gmail.com",
    "provider": "gmail",
    ...similar to above...
  },
  {
    "account_id": "outlook_test_01",
    "email": "test.account1@outlook.com",
    "provider": "outlook",
    "oauth_endpoint": "smtp.office365.com:587",
    "oauth_token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
    "client_id": "YOUR_OUTLOOK_CLIENT_ID",
    "refresh_token": "YOUR_OUTLOOK_REFRESH_TOKEN",
    "ip_address": "",
    "vmta_name": "vmta-outlook-test-01"
  },
  {
    "account_id": "outlook_test_02",
    ...similar to above...
  }
]
```

---

## Using Generated Accounts with Load Tests

### Step 1: Generate Accounts

```bash
# Create accounts.json with default test accounts
python generate_test_accounts.py --skip-input
```

### Step 2: Replace Placeholder Credentials

Edit `accounts.json` and replace:
- `YOUR_GMAIL_CLIENT_ID` → Your actual Gmail client ID
- `YOUR_GMAIL_CLIENT_SECRET` → Your actual Gmail client secret
- `YOUR_GMAIL_REFRESH_TOKEN` → Your actual Gmail refresh token
- `YOUR_OUTLOOK_CLIENT_ID` → Your actual Outlook client ID
- `YOUR_OUTLOOK_REFRESH_TOKEN` → Your actual Outlook refresh token

### Step 3: Start Proxy

```bash
python xoauth2_proxy_v2.py --config accounts.json --port 2525
```

### Step 4: Run Load Tests

```bash
# Quick test
python test_smtp_scenarios.py --scenario quick

# Or use specific account
python test_smtp_load.py --num-emails 100 --from test.account1@gmail.com
```

---

## Command-Line Options

```
--output FILE
    Output file path
    Default: accounts.json
    Example: python generate_test_accounts.py --output test_accounts.json

--skip-input
    Use default accounts without prompting
    Default: false (interactive mode)
    Example: python generate_test_accounts.py --skip-input

--show-defaults
    Show default accounts and exit (no file created)
    Default: false
    Example: python generate_test_accounts.py --show-defaults

--verify
    Verify accounts can connect to proxy after generating
    Requires proxy running on port 2525
    Default: false
    Example: python generate_test_accounts.py --verify
```

---

## Examples

### Generate to Default Location

```bash
python generate_test_accounts.py --skip-input
# Creates: accounts.json
```

### Generate to Custom Location

```bash
python generate_test_accounts.py --skip-input --output test_accounts.json
# Creates: test_accounts.json
```

### Interactive Mode

```bash
python generate_test_accounts.py
# Prompts for each account
```

### Show Defaults Without Saving

```bash
python generate_test_accounts.py --show-defaults
# Displays accounts but doesn't create file
```

### Generate and Verify

```bash
python generate_test_accounts.py --skip-input --verify
# Creates accounts.json and tests connection to proxy
# (requires proxy running on port 2525)
```

---

## Getting Real OAuth2 Credentials

### For Gmail

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project
3. Enable Gmail API
4. Create OAuth2 credentials (Desktop app)
5. Run OAuth2 authorization flow to get refresh token
6. Copy credentials to accounts.json:
   - client_id
   - client_secret
   - refresh_token

### For Outlook

1. Go to [Azure Portal](https://portal.azure.com)
2. Register a new application
3. Create credentials
4. Authorize the app to get refresh token
5. Copy credentials to accounts.json:
   - client_id
   - refresh_token

---

## Account Fields Explained

| Field | Required | Purpose |
|-------|----------|---------|
| `account_id` | Yes | Unique identifier for the account |
| `email` | Yes | Email address (must be valid) |
| `provider` | Yes | "gmail" or "outlook" |
| `oauth_endpoint` | Yes | SMTP server endpoint |
| `oauth_token_url` | Yes | OAuth2 token refresh URL |
| `client_id` | Yes | OAuth2 client ID |
| `client_secret` | Gmail only | OAuth2 client secret (required for Gmail) |
| `refresh_token` | Yes | OAuth2 refresh token |
| `ip_address` | No | IP address for sending (auto-assigned if blank) |
| `vmta_name` | Yes | Virtual MTA name (for PowerMTA integration) |

---

## Creating Custom Accounts

If you want to create your own test accounts without defaults:

```bash
python generate_test_accounts.py
```

Then select "No" when prompted for defaults and enter each account:
- Email address
- Provider (gmail/outlook)
- Client ID
- Refresh token
- Client secret (Gmail only)
- IP address (optional)

---

## Troubleshooting

### "ERROR: Invalid email address"
Make sure you enter a valid email format: `user@domain.com`

### "ERROR: Client secret required for Gmail"
Gmail accounts require both client_id AND client_secret.
Outlook accounts only need client_id and refresh_token.

### "WARNING: Field contains placeholder"
You haven't replaced the `YOUR_*` placeholders with real credentials.
Edit the accounts.json file and replace them.

### File Already Exists
If accounts.json already exists, you'll be prompted:
```
accounts.json already exists. Overwrite? (y/n):
```

Answer "y" to overwrite or "n" to keep the existing file.

---

## Using Generated Accounts in Load Tests

### Test with Specific Account

```bash
# Use gmail_test_01 account
python test_smtp_load.py \
    --num-emails 100 \
    --concurrent 10 \
    --from test.account1@gmail.com
```

### Test with Different Account

```bash
# Use outlook_test_01 account
python test_smtp_load.py \
    --num-emails 100 \
    --concurrent 10 \
    --from test.account1@outlook.com
```

### Rotate Through Multiple Accounts

```bash
# Test 1: Gmail
python test_smtp_load.py --from test.account1@gmail.com --num-emails 100

# Test 2: Gmail (different)
python test_smtp_load.py --from test.account2@gmail.com --num-emails 100

# Test 3: Outlook
python test_smtp_load.py --from test.account1@outlook.com --num-emails 100
```

---

## Next Steps

After generating accounts.json:

1. **Replace placeholder credentials**
   ```bash
   vim accounts.json  # or your editor
   # Replace YOUR_* placeholders with real OAuth2 tokens
   ```

2. **Start the proxy**
   ```bash
   python xoauth2_proxy_v2.py --config accounts.json --port 2525
   ```

3. **Run quick test**
   ```bash
   python test_smtp_scenarios.py --scenario quick
   ```

4. **Check results**
   - Should see "Success: 100%" if credentials are valid
   - If failures, check that credentials are correct

---

## Summary

**Quick Setup**:
```bash
# 1. Generate test accounts
python generate_test_accounts.py --skip-input

# 2. Edit accounts.json with real credentials
vim accounts.json

# 3. Start proxy
python xoauth2_proxy_v2.py --config accounts.json --port 2525

# 4. Run load test
python test_smtp_scenarios.py --scenario quick
```

This creates a ready-to-use test accounts file with 4 test accounts (2 Gmail, 2 Outlook) that you can use immediately with the load testing tools!
