# Quick Import Guide

## 3-Step Process to Generate accounts.json from Your Data

### Step 1: Prepare Your Data

Create a file with account data (one per line):

**File: `my_accounts.txt`**
```
pilareffiema0407@hotmail.com,account1,M.C519_BAY.0.U.-Cuf!4ApwaD8lIRZ0...,9e5f94bc-e8a4-4e73-b8be-63364c29d753
user2@gmail.com,account2,1//0gJA7asfdZKRE8z...,558976430978-xxxxxxx.apps.googleusercontent.com
user3@outlook.com,account3,M.C538_BAY.0.U.-Cs20*HMW5C11W!...,9e5f94bc-e8a4-4e73-b8be-63364c29d753
user4@hotmail.com,account4,M.R3_BAY.0.U.-Cs20*...,9e5f94bc-e8a4-4e73-b8be-63364c29d754
```

**Format:** `email,account_id,refresh_token,client_id`

**Notes:**
- Only these 4 fields are required
- You can include additional fields (timestamp, hostname) - they will be ignored
- One account per line
- Lines starting with `#` are comments
- Empty lines are ignored

### Step 2: Run the Import Script

```bash
python import_accounts.py -i my_accounts.txt -o accounts.json
```

**Output:**
```
Importing accounts...
[1] Imported: pilareffiema0407@hotmail.com (account_id: account1, provider: outlook)
[2] Imported: user2@gmail.com (account_id: account2, provider: gmail)
[3] Imported: user3@outlook.com (account_id: account3, provider: outlook)
[4] Imported: user4@hotmail.com (account_id: account4, provider: outlook)

[OK] Successfully imported 4 accounts
[OK] Validation passed: 4 unique accounts
[OK] Saved 4 accounts to accounts.json

Summary:
  Total accounts: 4
  Gmail accounts: 1
  Outlook accounts: 3
  IP range: 192.168.1.100 to 192.168.1.103
```

### Step 3: Use with Proxy

```bash
python xoauth2_proxy.py --config accounts.json
```

That's it! The proxy will load your imported accounts and start listening on 127.0.0.1:2525.

## What Gets Generated Automatically

For each account, the script generates:

| Field | Generated From | Example |
|-------|---|---|
| `ip_address` | Sequential from 192.168.1.100 | 192.168.1.100, 192.168.1.101... |
| `vmta_name` | account_id | vmta-account1 |
| `provider` | Email domain | gmail (for gmail.com), outlook (for hotmail.com) |
| `oauth_endpoint` | Provider type | smtp.gmail.com:587 or smtp.office365.com:587 |
| `oauth_token_url` | Provider type | https://oauth2.googleapis.com/token or https://login.live.com/oauth20_token.srf |
| `client_secret` | Empty for Outlook | "" |
| `max_concurrent_messages` | Default | 10 |
| `max_messages_per_hour` | Default | 10000 |

## Different Starting IP Address

If you want IPs to start from a different address:

```bash
python import_accounts.py -i my_accounts.txt -o accounts.json --start-ip 10.0.0.1
```

## Read from Clipboard/Stdin

If you want to paste data directly:

```bash
python import_accounts.py -o accounts.json
# Paste your account data
# Press Ctrl+D (or Ctrl+Z+Enter on Windows) when done
```

## Full Option List

```bash
python import_accounts.py --help
```

## Common Examples

### Example 1: 10 Outlook Accounts

**Data file: `outlook_accounts.txt`**
```
outlook1@outlook.com,ole1,M.C519_BAY.0.U.-Cuf!4ApwaD8lIRZ0...,9e5f94bc-e8a4-4e73-b8be-63364c29d753
outlook2@outlook.com,ole2,M.C519_BAY.0.U.-Cuf!4ApwaD8lIRZ0...,9e5f94bc-e8a4-4e73-b8be-63364c29d754
outlook3@outlook.com,ole3,M.C519_BAY.0.U.-Cuf!4ApwaD8lIRZ0...,9e5f94bc-e8a4-4e73-b8be-63364c29d755
...
```

**Import:**
```bash
python import_accounts.py -i outlook_accounts.txt -o accounts.json
```

### Example 2: Mixed Gmail & Outlook

**Data file: `mixed_accounts.txt`**
```
gmail1@gmail.com,gmail_acc1,1//0gJA7asfdZKRE8z...,558976430978-xxxxxxx.apps.googleusercontent.com
outlook1@outlook.com,ole_acc1,M.C519_BAY.0.U.-Cuf!4ApwaD8lIRZ0...,9e5f94bc-e8a4-4e73-b8be-63364c29d753
gmail2@gmail.com,gmail_acc2,1//0gJA7asfdZKRE8z...,558976430978-yyyyyyy.apps.googleusercontent.com
```

**Import:**
```bash
python import_accounts.py -i mixed_accounts.txt -o accounts.json
```

**Result:**
- 2 Gmail accounts configured with Google OAuth2 endpoints
- 1 Outlook account configured with Microsoft OAuth2 endpoints

### Example 3: Custom IP Range

```bash
python import_accounts.py -i accounts.txt -o accounts.json --start-ip 192.168.10.1
```

## Validate Without Saving

If you just want to check if the data is valid:

```bash
python import_accounts.py -i accounts.txt --validate-only
```

## Next Steps

1. **Use with Proxy:**
   ```bash
   python xoauth2_proxy.py --config accounts.json
   ```

2. **Generate PMTA Config:**
   ```bash
   python generate_pmta_config.py accounts.json -o pmta_generated.cfg
   ```

3. **Test Connection:**
   ```bash
   curl http://127.0.0.1:9090/health
   ```

## Troubleshooting

### "No accounts imported"
- Check that your input file has data
- Make sure lines have 4+ comma-separated fields
- Avoid lines starting with # (they're comments)

### "Duplicate emails"
- Check that no email appears twice in your data file

### "Invalid format"
- Make sure each line has at least: `email,account_id,refresh_token,client_id`
- Check for proper comma separation

### Can't find input file
```bash
# Make sure the file exists
ls -la my_accounts.txt

# Use absolute path if needed
python import_accounts.py -i /full/path/to/my_accounts.txt -o accounts.json
```

## Tips

- **Keep backup:** Save your original data file separately
- **Check before using:** Always validate before putting accounts into production
- **Update accounts.json:** To add more accounts later, create a new data file and re-import
- **Monitor IP conflicts:** Make sure the IP range you use doesn't conflict with existing network IPs
