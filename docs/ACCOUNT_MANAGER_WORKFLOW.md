# Account Manager Workflow Guide

Complete guide for using `account_manager.py` - a standalone management application that runs on any server and manages XOAUTH2 Proxy accounts via HTTP API.

---

## 📋 Overview

The Account Manager is a **standalone CLI application** that can run on any server (local or remote) to manage accounts on your XOAUTH2 Proxy server through HTTP API endpoints.

**Key Features:**
- ✅ Interactive menu-driven interface
- ✅ Color-coded terminal output
- ✅ Connection testing before operations
- ✅ Full CRUD operations (Create, Read, Update, Delete)
- ✅ OAuth2 credential verification
- ✅ Auto-cleanup of invalid accounts
- ✅ Safety confirmations for dangerous operations
- ✅ Runs independently on any server

**Use Cases:**
- Manage accounts from admin workstation
- Remote account management from different server
- Automated account provisioning scripts
- Centralized account administration

---

## 🚀 Quick Start

### **1. Setup on Management Server**

```bash
# Copy account_manager.py to your management server
scp account_manager.py admin@management-server:/opt/xoauth2/

# SSH into management server
ssh admin@management-server

# Install Python 3.8+ if not available
sudo apt update && sudo apt install python3 python3-pip -y

# Install required dependency
pip3 install requests

# Make executable (optional)
chmod +x account_manager.py
```

### **2. Connect to Remote Proxy**

```bash
# Option 1: Direct URL argument
python3 account_manager.py --url http://192.168.1.100:9090

# Option 2: Environment variable
export XOAUTH2_PROXY_URL=http://192.168.1.100:9090
python3 account_manager.py

# Option 3: Use default (localhost) if running on same server
python3 account_manager.py
```

### **3. Verify Connection**

Choose option **7** from the menu to test connectivity:

```
[7] Test Connection
Testing connection to http://192.168.1.100:9090...
✓ Connection successful! Proxy is running.
```

---

## 📖 Complete Workflow

### **Workflow 1: Adding New Account**

This is the most common operation - adding a Gmail or Outlook account with OAuth2 credentials.

#### **Step 1: Launch Account Manager**

```bash
python3 account_manager.py --url http://192.168.1.100:9090
```

**You'll see:**
```
╔════════════════════════════════════════════╗
║    XOAUTH2 Proxy - Account Manager        ║
╚════════════════════════════════════════════╝

Connected to: http://192.168.1.100:9090

[1] List All Accounts
[2] Add New Account
[3] Delete Account
[4] Delete All Accounts
[5] Delete Invalid Accounts
[6] Change Proxy URL
[7] Test Connection
[0] Exit

Choose an option:
```

#### **Step 2: Select Add New Account**

Type `2` and press Enter.

#### **Step 3: Choose Provider**

```
Select provider:
[1] Gmail
[2] Outlook
Choose provider (1 or 2):
```

Type `1` for Gmail or `2` for Outlook.

#### **Step 4: Enter Email Address**

```
Enter email address: sales@gmail.com
```

#### **Step 5: Enter Client ID**

```
Enter Client ID: 123456789-abc.apps.googleusercontent.com
```

**Where to get this:**
- **Gmail**: Google Cloud Console → APIs & Services → Credentials
- **Outlook**: Azure Portal → App Registrations → Application (client) ID

#### **Step 6: Enter Client Secret (Gmail only)**

```
Enter Client Secret: GOCSPX-abc123def456
```

**Note:** Outlook may not require client_secret for some OAuth2 flows.

#### **Step 7: Enter Refresh Token**

```
Enter Refresh Token: 1//0gABC123DEF456...
```

**Where to get this:**
- Use OAuth2 Playground (Gmail)
- Use Microsoft Graph Explorer (Outlook)
- Or use OAuth2 authorization flow in your app

#### **Step 8: Verify Credentials (Optional but Recommended)**

```
Verify credentials before adding? (y/n): y

🔍 Verifying OAuth2 credentials...
✓ OAuth2 credentials verified successfully!
```

**What happens:**
- App sends test request to Google/Microsoft OAuth2 endpoints
- Verifies refresh token can obtain access token
- Prevents adding accounts with bad credentials

#### **Step 9: Confirmation**

```
✓ Account sales@gmail.com added successfully!
Total accounts: 5

Press Enter to continue...
```

**Behind the scenes:**
- Account saved to accounts.json on proxy server
- Proxy automatically reloads accounts (zero downtime)
- Account immediately available for sending emails

#### **Complete Example Session:**

```
Choose an option: 2

=== Add New Account ===

Select provider:
[1] Gmail
[2] Outlook
Choose provider (1 or 2): 1

Enter email address: sales@gmail.com
Enter Client ID: 123456789-abc.apps.googleusercontent.com
Enter Client Secret: GOCSPX-abc123def456
Enter Refresh Token: 1//0gABC123DEF456GHI789...

Verify credentials before adding? (y/n): y

🔍 Verifying OAuth2 credentials...
✓ OAuth2 credentials verified successfully!

✓ Account sales@gmail.com added successfully!
Total accounts: 5

Press Enter to continue...
```

---

### **Workflow 2: Listing All Accounts**

View all configured accounts to verify they're registered correctly.

#### **Step 1: Select List All Accounts**

From main menu, type `1` and press Enter.

#### **Step 2: View Account List**

```
=== All Accounts (5 total) ===

Account 1:
  Email: sales@gmail.com
  Provider: gmail
  SMTP: smtp.gmail.com:587

Account 2:
  Email: support@outlook.com
  Provider: outlook
  SMTP: smtp.office365.com:587

Account 3:
  Email: marketing@gmail.com
  Provider: gmail
  SMTP: smtp.gmail.com:587

Account 4:
  Email: info@hotmail.com
  Provider: outlook
  SMTP: smtp.office365.com:587

Account 5:
  Email: notifications@gmail.com
  Provider: gmail
  SMTP: smtp.gmail.com:587

Press Enter to continue...
```

**What you can verify:**
- All accounts are registered
- Email addresses are correct
- Providers match expectations
- SMTP endpoints are correct

---

### **Workflow 3: Deleting Specific Account**

Remove a single account when no longer needed.

#### **Step 1: Select Delete Account**

From main menu, type `3` and press Enter.

#### **Step 2: Enter Email Address**

```
=== Delete Account ===

Enter email address to delete: sales@gmail.com
```

#### **Step 3: Confirmation**

```
✓ Account sales@gmail.com deleted successfully!
Total accounts remaining: 4

Press Enter to continue...
```

**Behind the scenes:**
- Account removed from accounts.json
- Proxy automatically reloads (zero downtime)
- Future auth attempts for this email will fail

#### **Error Handling:**

If account doesn't exist:
```
Enter email address to delete: nonexistent@gmail.com
✗ Account nonexistent@gmail.com not found
```

---

### **Workflow 4: Verifying Accounts (Auto-Clean Invalid)**

Automatically test all accounts and remove those with bad OAuth2 credentials.

**Use Cases:**
- Expired refresh tokens
- Revoked OAuth2 access
- Deleted Google/Microsoft apps
- Periodic maintenance

#### **Step 1: Select Delete Invalid Accounts**

From main menu, type `5` and press Enter.

#### **Step 2: Automatic Testing**

```
=== Delete Invalid Accounts ===

🔍 Testing all accounts for validity...
Testing account 1/5: sales@gmail.com... ✓ Valid
Testing account 2/5: support@outlook.com... ✗ Invalid (token expired)
Testing account 3/5: marketing@gmail.com... ✓ Valid
Testing account 4/5: info@hotmail.com... ✗ Invalid (revoked access)
Testing account 5/5: notifications@gmail.com... ✓ Valid
```

#### **Step 3: Results**

```
✓ Deleted 2 invalid accounts:
  - support@outlook.com
  - info@hotmail.com

Total accounts remaining: 3

Press Enter to continue...
```

**What happens:**
- Each account's OAuth2 credentials are tested
- Invalid accounts are automatically removed
- Proxy reloads with only valid accounts
- Email logs won't show failed auth errors

#### **If All Valid:**

```
=== Delete Invalid Accounts ===

🔍 Testing all accounts for validity...
Testing account 1/5: sales@gmail.com... ✓ Valid
Testing account 2/5: support@outlook.com... ✓ Valid
Testing account 3/5: marketing@gmail.com... ✓ Valid
Testing account 4/5: info@hotmail.com... ✓ Valid
Testing account 5/5: notifications@gmail.com... ✓ Valid

✓ No invalid accounts found. All accounts are healthy!

Press Enter to continue...
```

---

### **Workflow 5: Deleting All Accounts**

Remove all accounts at once (useful for migrations or testing).

**⚠️ WARNING: This is a destructive operation!**

#### **Step 1: Select Delete All Accounts**

From main menu, type `4` and press Enter.

#### **Step 2: First Confirmation**

```
=== Delete All Accounts ===

⚠️  WARNING: This will delete ALL accounts!
Are you sure? (yes/no):
```

Type `yes` exactly (case-sensitive).

#### **Step 3: Second Confirmation**

```
⚠️  This action cannot be undone!
Type 'DELETE ALL' to confirm:
```

Type `DELETE ALL` exactly (case-sensitive).

#### **Step 4: Deletion**

```
✓ All accounts deleted (5 accounts removed)
Total accounts remaining: 0

Press Enter to continue...
```

**Behind the scenes:**
- All accounts removed from accounts.json
- Proxy reloads with empty account list
- No emails can be sent until new accounts added

#### **Cancellation:**

At any confirmation prompt, type anything else to cancel:
```
Are you sure? (yes/no): no
✗ Cancelled
```

---

### **Workflow 6: Connection Testing**

Verify connectivity to proxy server before performing operations.

#### **Step 1: Select Test Connection**

From main menu, type `7` and press Enter.

#### **Step 2: Test Result**

**Success:**
```
=== Test Connection ===

Testing connection to http://192.168.1.100:9090...
✓ Connection successful! Proxy is running.

Press Enter to continue...
```

**Failure:**
```
=== Test Connection ===

Testing connection to http://192.168.1.100:9090...
✗ Connection failed: HTTPConnectionPool(host='192.168.1.100', port=9090): Max retries exceeded

Possible issues:
- Proxy server is not running
- Firewall blocking port 9090
- Incorrect proxy URL

Press Enter to continue...
```

---

### **Workflow 7: Changing Proxy URL**

Switch to different proxy server without restarting the app.

#### **Step 1: Select Change Proxy URL**

From main menu, type `6` and press Enter.

#### **Step 2: Enter New URL**

```
=== Change Proxy URL ===

Current URL: http://192.168.1.100:9090
Enter new proxy URL (or press Enter to cancel): http://10.0.0.50:9090
```

#### **Step 3: Confirmation**

```
✓ Proxy URL changed to: http://10.0.0.50:9090

Press Enter to continue...
```

**Next operations will use new URL.**

---

## 🔄 Common Workflows

### **Daily Maintenance Workflow**

```bash
# 1. Test connection
python3 account_manager.py --url http://proxy:9090
# Choose [7] Test Connection

# 2. Check account health
# Choose [5] Delete Invalid Accounts

# 3. List remaining accounts
# Choose [1] List All Accounts
```

### **New Account Setup Workflow**

```bash
# 1. Test connection
# Choose [7] Test Connection

# 2. Add account with verification
# Choose [2] Add New Account
# Verify credentials: yes

# 3. Confirm added
# Choose [1] List All Accounts
```

### **Migration Workflow**

```bash
# 1. Export old accounts (if needed)
# Choose [1] List All Accounts (save output)

# 2. Delete all accounts
# Choose [4] Delete All Accounts

# 3. Add new accounts one by one
# Choose [2] Add New Account (repeat)

# 4. Verify all added
# Choose [1] List All Accounts
```

### **Troubleshooting Workflow**

```bash
# 1. Test connection
# Choose [7] Test Connection

# 2. List accounts to identify issues
# Choose [1] List All Accounts

# 3. Clean invalid accounts
# Choose [5] Delete Invalid Accounts

# 4. Re-add problematic accounts
# Choose [2] Add New Account
```

---

## 🛠️ Advanced Usage

### **1. Scripted Account Addition**

Create a script to add accounts programmatically:

```python
#!/usr/bin/env python3
import requests

PROXY_URL = "http://192.168.1.100:9090"

accounts = [
    {
        "email": "sales@gmail.com",
        "provider": "gmail",
        "client_id": "123456789-abc.apps.googleusercontent.com",
        "client_secret": "GOCSPX-abc123",
        "refresh_token": "1//0gABC123...",
        "verify": True
    },
    {
        "email": "support@outlook.com",
        "provider": "outlook",
        "client_id": "abc-123-def-456",
        "refresh_token": "0.AXoA...",
        "verify": True
    }
]

for account in accounts:
    response = requests.post(f"{PROXY_URL}/admin/accounts", json=account)
    if response.status_code == 200:
        result = response.json()
        print(f"✓ Added: {account['email']}")
    else:
        error = response.json()
        print(f"✗ Failed: {account['email']} - {error.get('error')}")
```

### **2. Cron Job for Auto-Cleanup**

Clean invalid accounts daily:

```bash
# Create cleanup script
cat > /opt/xoauth2/cleanup_accounts.sh <<'EOF'
#!/bin/bash
PROXY_URL="http://192.168.1.100:9090"
curl -s -X DELETE "${PROXY_URL}/admin/accounts/invalid" | jq
EOF

chmod +x /opt/xoauth2/cleanup_accounts.sh

# Add to crontab (runs daily at 3 AM)
crontab -e
# Add: 0 3 * * * /opt/xoauth2/cleanup_accounts.sh >> /var/log/xoauth2_cleanup.log 2>&1
```

### **3. Environment-Based Configuration**

Use environment variables for different environments:

```bash
# Production
export XOAUTH2_PROXY_URL=http://prod-proxy:9090
python3 account_manager.py

# Staging
export XOAUTH2_PROXY_URL=http://staging-proxy:9090
python3 account_manager.py

# Development
export XOAUTH2_PROXY_URL=http://localhost:9090
python3 account_manager.py
```

### **4. Batch Operations**

Delete multiple specific accounts:

```bash
#!/bin/bash
PROXY_URL="http://192.168.1.100:9090"

accounts_to_delete=(
    "old1@gmail.com"
    "old2@outlook.com"
    "test@gmail.com"
)

for email in "${accounts_to_delete[@]}"; do
    echo "Deleting: $email"
    curl -s -X DELETE "${PROXY_URL}/admin/accounts/${email}"
    echo ""
done
```

---

## 🔒 Security Best Practices

### **1. Network Security**

```bash
# Use firewall to restrict Admin API access
sudo ufw allow from 10.0.0.0/8 to any port 9090
sudo ufw deny 9090

# Or use SSH tunnel for remote access
ssh -L 9090:localhost:9090 user@proxy-server
# Then connect to: http://localhost:9090
```

### **2. Sensitive Data Handling**

```bash
# Never commit credentials to git
echo "accounts.json" >> .gitignore

# Use environment variables for automation
export GMAIL_CLIENT_ID="..."
export GMAIL_CLIENT_SECRET="..."
export GMAIL_REFRESH_TOKEN="..."

# Or use secrets management
# AWS Secrets Manager, HashiCorp Vault, etc.
```

### **3. Audit Logging**

Monitor all account changes:

```bash
# Tail proxy logs
tail -f /var/log/xoauth2/xoauth2_proxy.log | grep "Account.*added\|deleted"

# Output:
# [AdminServer] Account sales@gmail.com added successfully (5 total)
# [AdminServer] Account old@gmail.com deleted successfully (4 remaining)
```

---

## 🐛 Troubleshooting

### **Issue 1: Connection Refused**

```
✗ Connection failed: Connection refused
```

**Solutions:**
- Verify proxy server is running: `ps aux | grep xoauth2_proxy`
- Check proxy is listening: `netstat -tlnp | grep 9090`
- Test with curl: `curl http://proxy-server:9090/health`
- Check firewall: `sudo ufw status`

### **Issue 2: Invalid Credentials**

```
✗ Failed to verify OAuth2 credentials
```

**Solutions:**
- Regenerate refresh token from OAuth2 provider
- Verify client_id and client_secret are correct
- Check OAuth2 app is not disabled/deleted
- Ensure correct scopes are authorized

### **Issue 3: Account Not Found**

```
✗ Account example@gmail.com not found
```

**Solutions:**
- List all accounts to verify spelling: Option [1]
- Check if account was already deleted
- Ensure you're connected to correct proxy server

### **Issue 4: Permission Denied**

```
✗ Error: Permission denied
```

**Solutions:**
- Check file permissions on proxy server: `ls -l accounts.json`
- Ensure proxy process has write access
- Run proxy with appropriate user permissions

---

## 📊 Response Reference

### **Success Responses**

| Operation | Response |
|-----------|----------|
| Add Account | `{"success": true, "message": "Account added", "total_accounts": 5}` |
| Delete Account | `{"success": true, "message": "Account deleted", "total_accounts": 4}` |
| Delete All | `{"success": true, "message": "All accounts deleted (5 removed)", "total_accounts": 0}` |
| Delete Invalid | `{"success": true, "deleted_count": 2, "deleted_accounts": ["..."], "total_accounts": 3}` |
| List Accounts | `{"success": true, "accounts": [...], "total": 5}` |

### **Error Responses**

| Status | Error |
|--------|-------|
| 400 | Invalid email format |
| 400 | Missing required fields |
| 400 | OAuth2 verification failed |
| 404 | Account not found |
| 500 | Server error (check proxy logs) |

---

## 📞 Related Documentation

- **HTTP API Reference:** `docs/ADMIN_API.md`
- **Remote Account Management:** `docs/REMOTE_ACCOUNT_MANAGEMENT.md`
- **Delete Operations:** `docs/DELETE_ACCOUNTS_GUIDE.md`
- **OAuth2 Setup:** `docs/GMAIL_OUTLOOK_SETUP.md`
- **Add Account Tool:** `docs/ADD_ACCOUNT_GUIDE.md`

---

## 📝 Quick Command Reference

```bash
# Launch account manager
python3 account_manager.py --url http://proxy:9090

# Test connection
curl http://proxy:9090/health

# List accounts via API
curl http://proxy:9090/admin/accounts

# Add account via API
curl -X POST http://proxy:9090/admin/accounts -H "Content-Type: application/json" -d '{...}'

# Delete account via API
curl -X DELETE http://proxy:9090/admin/accounts/email@gmail.com

# Delete invalid accounts via API
curl -X DELETE http://proxy:9090/admin/accounts/invalid

# Delete all accounts via API
curl -X DELETE "http://proxy:9090/admin/accounts?confirm=true"
```

---

## ✅ Workflow Checklist

Use this checklist for complete account lifecycle management:

**Initial Setup:**
- [ ] Install account_manager.py on management server
- [ ] Install Python 3.8+ and requests library
- [ ] Configure XOAUTH2_PROXY_URL environment variable
- [ ] Test connection to proxy server

**Adding Accounts:**
- [ ] Obtain OAuth2 credentials from Google/Microsoft
- [ ] Launch account manager
- [ ] Choose "Add New Account"
- [ ] Enter email, client_id, client_secret, refresh_token
- [ ] Verify credentials (recommended)
- [ ] Confirm account added successfully

**Verification:**
- [ ] List all accounts to confirm
- [ ] Test sending email through PowerMTA
- [ ] Check proxy logs for successful auth

**Maintenance:**
- [ ] Schedule daily invalid account cleanup
- [ ] Monitor proxy logs for auth failures
- [ ] Re-add accounts if credentials expire

**Removal:**
- [ ] Delete specific accounts when no longer needed
- [ ] Or use "Delete Invalid" for automatic cleanup
- [ ] Verify remaining accounts still work

---

**Account Manager Version:** 1.0
**Last Updated:** November 2024
**Tested On:** Python 3.8+, Linux/macOS/Windows
