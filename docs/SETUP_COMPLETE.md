# XOAUTH2 Proxy - Setup Complete

## What You Have

A **production-ready XOAUTH2 SMTP proxy** for PowerMTA v6 that handles:
- ✅ Real OAuth2 token refresh (Gmail & Outlook)
- ✅ XOAUTH2 authentication
- ✅ Multiple accounts with dedicated IPs
- ✅ Cross-platform support (Windows, Linux, macOS)
- ✅ Prometheus metrics monitoring
- ✅ Automatic account importing from CSV data

---

## Quick Start (3 Steps)

### Step 1: Import Your Accounts

Create a file with your account data:

```bash
# my_accounts.txt
pilareffiema0407@hotmail.com,acc1,M.C519_BAY.0.U.-Cuf!4ApwaD8lIRZ0...,9e5f94bc-e8a4-4e73-b8be-63364c29d753
user2@gmail.com,acc2,1//0gJA7asfdZKRE8z...,558976430978-xxxxxxx.apps.googleusercontent.com
user3@outlook.com,acc3,M.C538_BAY.0.U.-Cs20*HMW5C11W!...,9e5f94bc-e8a4-4e73-b8be-63364c29d753
```

Run the import script:

```bash
python import_accounts.py -i my_accounts.txt -o accounts.json
```

**Output:**
```
[1] Imported: pilareffiema0407@hotmail.com (account_id: acc1, provider: outlook)
[2] Imported: user2@gmail.com (account_id: acc2, provider: gmail)
[3] Imported: user3@outlook.com (account_id: acc3, provider: outlook)

[OK] Successfully imported 3 accounts
[OK] Validation passed: 3 unique accounts
[OK] Saved 3 accounts to accounts.json

Summary:
  Total accounts: 3
  Gmail accounts: 1
  Outlook accounts: 2
  IP range: 192.168.1.100 to 192.168.1.102
```

### Step 2: Start the Proxy

```bash
python xoauth2_proxy.py --config accounts.json
```

**Expected output:**
```
2025-11-14 16:56:55 - xoauth2_proxy - INFO - [OK] Loaded 3 accounts from accounts.json
2025-11-14 16:56:55 - xoauth2_proxy - INFO - Metrics server started on port 9090
2025-11-14 16:56:55 - xoauth2_proxy - INFO - XOAUTH2 proxy started successfully
```

The proxy is now listening on `127.0.0.1:2525` ✅

### Step 3: Configure PowerMTA

Generate PMTA configuration:

```bash
python generate_pmta_config.py accounts.json -o pmta_generated.cfg
```

Copy to PMTA:

```bash
# Linux
sudo cp pmta_generated.cfg /etc/pmta/pmta.cfg
sudo /etc/init.d/pmta reload

# Windows
copy pmta_generated.cfg "C:\Program Files\PowerMTA\pmta.cfg"
# Reload PMTA
```

---

## Files in This Package

### Main Application
- **`xoauth2_proxy.py`** - XOAUTH2 SMTP proxy (main application)
- **`import_accounts.py`** - CSV account importer (converts your data to accounts.json)
- **`generate_pmta_config.py`** - PMTA config generator

### Configuration
- **`accounts.json`** - Account configuration (generated from your data)
- **`pmta.cfg`** - PowerMTA configuration template

### Documentation
- **`QUICK_IMPORT_GUIDE.md`** - 3-step import guide
- **`IMPORT_ACCOUNTS_README.md`** - Detailed import script documentation
- **`QUICK_START.md`** - Proxy quick start guide
- **`CROSS_PLATFORM_SETUP.md`** - Platform-specific setup (Windows/Linux/macOS)
- **`OAUTH2_REAL_WORLD.md`** - OAuth2 implementation details
- **`DEPLOYMENT_GUIDE.md`** - Production deployment guide

### Test/Sample Files
- **`sample_accounts_data.txt`** - Sample account data format
- **`large_test_data.txt`** - 20-account test dataset
- **`test_accounts.json`** - Generated from sample data
- **`large_test_accounts.json`** - Generated from 20-account data

---

## Your Workflow

### 1. Import Accounts

**Input:** Your account data (comma-separated)
```
email,account_id,refresh_token,client_id
```

**Command:**
```bash
python import_accounts.py -i your_data.txt -o accounts.json
```

**Output:** `accounts.json` with full account configuration

### 2. Start Proxy

```bash
python xoauth2_proxy.py --config accounts.json
```

### 3. Connect PMTA

PMTA routes to proxy on `127.0.0.1:2525` using the email address as username.

### 4. Monitor

Check proxy health:
```bash
curl http://127.0.0.1:9090/health
```

View metrics:
```bash
curl http://127.0.0.1:9090/metrics
```

View logs:
```bash
# Windows
Get-Content "$env:TEMP\xoauth2_proxy\xoauth2_proxy.log" -Tail 50

# Linux/macOS
tail -f /var/log/xoauth2/xoauth2_proxy.log
```

---

## Key Features

### 1. Automatic Account Generation

Your input:
```
email@example.com,account_id,refresh_token_xyz,client_id_123
```

Generated automatically:
- ✅ IP Address (192.168.1.100, 192.168.1.101, ...)
- ✅ VMTA Name (vmta-account_id)
- ✅ Provider (Gmail or Outlook, detected from email domain)
- ✅ OAuth Endpoints (correct for each provider)
- ✅ Rate limits (10 concurrent, 10k/hour)

### 2. Multi-Provider Support

| Provider | Email Domain | OAuth Endpoint | Client Secret |
|----------|---|---|---|
| Gmail | gmail.com, googlemail.com | smtp.gmail.com:587 | Required |
| Outlook | outlook.com, hotmail.com, live.com, msn.com | smtp.office365.com:587 | Not used |

### 3. Real OAuth2 Token Refresh

- Automatic hourly token refresh
- 5-minute buffer before expiration
- Error recovery with automatic retry
- Prometheus metrics tracking

### 4. Monitoring & Observability

Prometheus metrics available at `http://127.0.0.1:9090/metrics`:

```
smtp_connections_total - Total SMTP connections
auth_attempts_total - Auth attempts by result
token_refresh_total - Token refresh attempts
token_age_seconds - Current token age
messages_total - Messages processed
```

### 5. Cross-Platform

- **Windows**: Logs to `%TEMP%\xoauth2_proxy\`
- **Linux**: Logs to `/var/log/xoauth2/`
- **macOS**: Logs to `/var/log/xoauth2/` (or user directory)

---

## Command Reference

### Import Accounts

```bash
# From file
python import_accounts.py -i data.txt -o accounts.json

# From stdin (paste data)
python import_accounts.py -o accounts.json

# Custom IP range
python import_accounts.py -i data.txt -o accounts.json --start-ip 10.0.0.1

# Validate only
python import_accounts.py -i data.txt --validate-only

# Skip errors
python import_accounts.py -i data.txt -o accounts.json --skip-errors
```

### Start Proxy

```bash
# Normal operation
python xoauth2_proxy.py --config accounts.json

# Dry-run mode (don't send)
python xoauth2_proxy.py --config accounts.json --dry-run

# Custom port
python xoauth2_proxy.py --config accounts.json --port 2526

# Custom metrics port
python xoauth2_proxy.py --config accounts.json --metrics-port 9091

# All options
python xoauth2_proxy.py \
  --config accounts.json \
  --host 127.0.0.1 \
  --port 2525 \
  --metrics-port 9090 \
  --dry-run \
  --global-concurrency 100
```

### Generate PMTA Config

```bash
# Basic generation
python generate_pmta_config.py accounts.json -o pmta_generated.cfg

# With validation
python generate_pmta_config.py accounts.json -o pmta_generated.cfg --validate-only

# With reload
python generate_pmta_config.py accounts.json -o pmta_generated.cfg --reload

# Custom proxy
python generate_pmta_config.py accounts.json -o pmta.cfg \
  --proxy-host 10.0.0.5 \
  --proxy-port 2525 \
  --max-smtp-out 20 \
  --max-connections 10
```

---

## Testing

### Test 1: Proxy Health

```bash
curl http://127.0.0.1:9090/health
# Response: {"status": "healthy"}
```

### Test 2: Metrics

```bash
curl http://127.0.0.1:9090/metrics
# Shows Prometheus metrics
```

### Test 3: SMTP Connection

```bash
# Using swaks
swaks --server 127.0.0.1:2525 \
  --auth-user email@gmail.com \
  --auth-password placeholder \
  --from test@example.com \
  --to verify@gmail.com
# Expected: 250 2.0.0 OK
```

### Test 4: Logs

```bash
# Windows
Get-Content "$env:TEMP\xoauth2_proxy\xoauth2_proxy.log" -Tail 20

# Linux/macOS
tail -20 /var/log/xoauth2/xoauth2_proxy.log
```

---

## Data Format

Your account data should be comma-separated:

```
email,account_id,refresh_token,client_id[,timestamp[,hostname]]
```

**Required (4 fields minimum):**
1. `email` - Email address
2. `account_id` - Unique identifier
3. `refresh_token` - OAuth2 refresh token
4. `client_id` - OAuth2 client ID

**Optional (ignored):**
5. `timestamp` - Any timestamp format
6. `hostname` - Any hostname/label

**Example:**
```
pilareffiema0407@hotmail.com,pilare_acc1,M.C519_BAY.0.U.-Cuf!4ApwaD8lIRZ0...,9e5f94bc-e8a4-4e73-b8be-63364c29d753,2025-09-24T00:00:00.0000000Z,localhost
```

---

## Troubleshooting

### Import Script Issues

**"No accounts imported"**
- Check file exists and has data
- Ensure lines have 4+ comma-separated fields

**"Duplicate emails"**
- Check for repeated email addresses in your data

**"Invalid format"**
- Verify format: `email,account_id,refresh_token,client_id`

### Proxy Issues

**"Port already in use"**
- Change port: `--port 2526`
- Or kill existing process: `pkill -f xoauth2_proxy`

**"Config file not found"**
- Use absolute path: `python xoauth2_proxy.py --config /full/path/to/accounts.json`
- Or use relative: `python xoauth2_proxy.py --config ./accounts.json`

**"ModuleNotFoundError"**
- Install dependencies: `pip install prometheus-client requests`

### PMTA Issues

**"Cannot connect to proxy"**
- Check proxy is running: `curl http://127.0.0.1:9090/health`
- Check port: `netstat -an | grep 2525`
- Check firewall: Allow 127.0.0.1:2525

**"Auth failed"**
- Check email in accounts.json matches PMTA auth-username
- Check token is valid in accounts.json
- Check proxy logs for detailed error

---

## Next Steps

1. **Prepare your data** - List all accounts in CSV format
2. **Import accounts** - Run import script
3. **Start proxy** - Launch xoauth2_proxy.py
4. **Configure PMTA** - Generate and update PMTA config
5. **Test** - Send test emails through PMTA
6. **Monitor** - Watch metrics and logs
7. **Deploy** - Set up as service (see DEPLOYMENT_GUIDE.md)

---

## Support & Documentation

- **Quick Start:** `QUICK_START.md`
- **Import Guide:** `QUICK_IMPORT_GUIDE.md` or `IMPORT_ACCOUNTS_README.md`
- **OAuth2 Details:** `OAUTH2_REAL_WORLD.md`
- **Platform Setup:** `CROSS_PLATFORM_SETUP.md`
- **Deployment:** `DEPLOYMENT_GUIDE.md`

---

## System Requirements

- **Python:** 3.8+ (tested with 3.12)
- **OS:** Windows, Linux, or macOS
- **Network:** Access to OAuth2 endpoints (Google, Microsoft)
- **Ports:** 2525 (proxy), 9090 (metrics)

## Dependencies

```bash
pip install prometheus-client requests
```

---

**Status:** ✅ Ready for Production

All components tested and working. Your proxy is ready to handle real OAuth2 traffic!
