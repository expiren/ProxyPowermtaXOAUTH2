# Quick Account Manager Guide

**Quick reference for managing XOAUTH2 Proxy accounts from another server.**

---

## Setup (5 minutes)

### 1. Copy to Management Server

```bash
# From your local machine, copy account_manager.py to management server
scp account_manager.py admin@management-server:/opt/xoauth2/

# SSH into management server
ssh admin@management-server
cd /opt/xoauth2
```

### 2. Install Python & Dependencies

```bash
# Ubuntu/Debian
sudo apt update && sudo apt install python3 python3-pip -y
pip3 install requests

# CentOS/RHEL
sudo yum install python3 python3-pip -y
pip3 install requests

# Check installation
python3 --version  # Should be 3.8+
```

### 3. Run Account Manager

```bash
# Replace with your proxy server IP
python3 account_manager.py --url http://192.168.1.100:9090
```

---

## Quick Workflows

### Add New Gmail Account

```
1. Launch: python3 account_manager.py --url http://YOUR_PROXY_IP:9090
2. Choose: [2] Add New Account
3. Provider: [1] Gmail
4. Email: sales@gmail.com
5. Client ID: 123456789-abc.apps.googleusercontent.com
6. Client Secret: GOCSPX-abc123def456
7. Refresh Token: 1//0gABC123DEF456...
8. Verify: y (recommended)
9. Done! Account added and immediately available
```

### Add New Outlook Account

```
1. Launch: python3 account_manager.py --url http://YOUR_PROXY_IP:9090
2. Choose: [2] Add New Account
3. Provider: [2] Outlook
4. Email: support@outlook.com
5. Client ID: abc-123-def-456
6. Client Secret: (press Enter to skip for some OAuth2 flows)
7. Refresh Token: 0.AXoA...
8. Verify: y (recommended)
9. Done! Account added and immediately available
```

### List All Accounts

```
1. Launch: python3 account_manager.py --url http://YOUR_PROXY_IP:9090
2. Choose: [1] List All Accounts
3. View all configured accounts with details
```

### Delete Specific Account

```
1. Launch: python3 account_manager.py --url http://YOUR_PROXY_IP:9090
2. Choose: [3] Delete Account
3. Email: old@gmail.com
4. Done! Account removed immediately
```

### Auto-Clean Invalid Accounts

```
1. Launch: python3 account_manager.py --url http://YOUR_PROXY_IP:9090
2. Choose: [5] Delete Invalid Accounts
3. Wait for testing (tests OAuth2 credentials)
4. View results - invalid accounts automatically removed
```

### Delete All Accounts

```
1. Launch: python3 account_manager.py --url http://YOUR_PROXY_IP:9090
2. Choose: [4] Delete All Accounts
3. Confirm: yes
4. Confirm again: DELETE ALL
5. Done! All accounts removed
```

---

## Connection Options

### Option 1: Command Line Argument (Recommended)

```bash
python3 account_manager.py --url http://192.168.1.100:9090
```

### Option 2: Environment Variable

```bash
# Set once
export XOAUTH2_PROXY_URL=http://192.168.1.100:9090

# Run without --url
python3 account_manager.py
```

### Option 3: Change URL from Menu

```
1. Launch: python3 account_manager.py
2. Choose: [6] Change Proxy URL
3. Enter: http://192.168.1.100:9090
4. Done! Now connected to new proxy
```

---

## Testing Connection

Always test connection before performing operations:

```
1. Launch: python3 account_manager.py --url http://YOUR_PROXY_IP:9090
2. Choose: [7] Test Connection
3. View result:
   ✓ Connection successful! (proxy is running)
   ✗ Connection failed (check firewall/proxy status)
```

---

## Troubleshooting

### Connection Failed

**Problem:** `✗ Connection failed: Connection refused`

**Solutions:**
```bash
# Check if proxy is running
curl http://YOUR_PROXY_IP:9090/health

# Check firewall (on proxy server)
sudo ufw status
sudo ufw allow 9090

# Or use SSH tunnel
ssh -L 9090:localhost:9090 user@proxy-server
# Then connect to: http://localhost:9090
```

### Invalid Credentials

**Problem:** `✗ Failed to verify OAuth2 credentials`

**Solutions:**
- Regenerate refresh token from Google/Microsoft
- Verify client_id and client_secret are correct
- Check OAuth2 app is not disabled
- Ensure correct scopes are authorized

### Permission Denied

**Problem:** `✗ Error: Permission denied`

**Solutions:**
```bash
# Check file permissions on proxy server
ls -l accounts.json

# Fix permissions
chmod 644 accounts.json
chown xoauth2:xoauth2 accounts.json
```

---

## Security Best Practices

### 1. Use SSH Tunnel for Remote Access

```bash
# On management server
ssh -L 9090:localhost:9090 user@proxy-server

# Then connect to localhost
python3 account_manager.py --url http://localhost:9090
```

### 2. Restrict Admin API with Firewall

```bash
# On proxy server - only allow management server IP
sudo ufw allow from 10.0.0.50 to any port 9090
sudo ufw deny 9090
```

### 3. Use Environment Variables

```bash
# Store credentials in environment (not in shell history)
read -s GMAIL_REFRESH_TOKEN
export GMAIL_REFRESH_TOKEN

# Or use secrets file
echo "export GMAIL_REFRESH_TOKEN=..." > ~/.xoauth2_secrets
chmod 600 ~/.xoauth2_secrets
source ~/.xoauth2_secrets
```

---

## API Endpoints Reference

The account manager uses these HTTP endpoints:

| Operation | Endpoint | Method |
|-----------|----------|--------|
| List accounts | `/admin/accounts` | GET |
| Add account | `/admin/accounts` | POST |
| Delete account | `/admin/accounts/{email}` | DELETE |
| Delete all | `/admin/accounts?confirm=true` | DELETE |
| Delete invalid | `/admin/accounts/invalid` | DELETE |
| Health check | `/health` | GET |

**Base URL:** `http://YOUR_PROXY_IP:9090`

---

## Automated Account Management

### Script to Add Multiple Accounts

```python
#!/usr/bin/env python3
import requests
import sys

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
    try:
        response = requests.post(f"{PROXY_URL}/admin/accounts", json=account, timeout=10)
        if response.status_code == 200:
            print(f"✓ Added: {account['email']}")
        else:
            error = response.json()
            print(f"✗ Failed: {account['email']} - {error.get('error')}")
    except Exception as e:
        print(f"✗ Error: {account['email']} - {e}")
```

### Daily Invalid Account Cleanup

```bash
#!/bin/bash
PROXY_URL="http://192.168.1.100:9090"

# Cleanup invalid accounts
curl -s -X DELETE "${PROXY_URL}/admin/accounts/invalid" | jq

# Add to crontab (daily at 3 AM)
# crontab -e
# 0 3 * * * /opt/xoauth2/cleanup_accounts.sh >> /var/log/xoauth2_cleanup.log 2>&1
```

---

## Complete Documentation

For detailed workflows and advanced usage, see:
- **docs/ACCOUNT_MANAGER_WORKFLOW.md** - Complete workflow guide
- **docs/REMOTE_ACCOUNT_MANAGEMENT.md** - Remote management examples
- **docs/DELETE_ACCOUNTS_GUIDE.md** - Deletion operations
- **docs/ADMIN_API.md** - Complete API reference

---

## Summary

**account_manager.py** is a standalone CLI application that manages XOAUTH2 Proxy accounts from any server using HTTP API endpoints.

**Key Points:**
- ✅ Runs independently on any server
- ✅ No installation on proxy server required
- ✅ Interactive menu-driven interface
- ✅ Full CRUD operations
- ✅ OAuth2 credential verification
- ✅ Auto-cleanup of invalid accounts
- ✅ Zero downtime (automatic hot-reload)

**Quick Start:**
```bash
# Copy to management server
scp account_manager.py admin@server:/opt/xoauth2/

# Install dependency
pip3 install requests

# Run
python3 account_manager.py --url http://proxy-ip:9090
```

**Support:** Check logs at `/var/log/xoauth2/xoauth2_proxy.log` on proxy server
