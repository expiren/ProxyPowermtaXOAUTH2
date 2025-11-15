# Import Accounts Script

## Overview

The `import_accounts.py` script converts account data in CSV format into the `accounts.json` configuration file for the XOAUTH2 proxy.

## Data Format

Your account data should be in comma-separated format:

```
email,account_id,refresh_token,client_id,timestamp,hostname
```

**Required fields:**
- `email` - Email address (e.g., `pilareffiema0407@hotmail.com`)
- `account_id` - Unique account identifier (e.g., `pilare_acc1`)
- `refresh_token` - OAuth2 refresh token (long string starting with `M.C...` for Outlook or `1//...` for Gmail)
- `client_id` - OAuth2 client ID (UUID format for Outlook)

**Optional fields:**
- `timestamp` - Last refresh time (ignored by importer)
- `hostname` - Hostname (ignored by importer)

## Example Data

```
pilareffiema0407@hotmail.com,pilare_acc1,M.C519_BAY.0.U.-Cuf!4ApwaD8lIRZ0tUolkrH1L8ZYlRhnqvr09NNipvtQgSV00YM*wb0PhghbIcMeNta2bPpS45tBqAv7C5aj7haniH0J9cxKVVagIg16criZcxQrhAb6XXARazSXNWfotKce8WfnN2rlTM5*mdLe5dVOlfgDGw4rXJEqAqGq9hNQ4veC7K!DfSrOibD6DgjRnib1RY922DTf1QzSUuV71lz4Pm5r5LhdJxsV4dugeceI0P*apnf6C1S*CX6gY3bHqIlA*Ulo39WjwaOE*gwKoXEUQZizlINuTftvoWuOn!yUExXzftGiu*qXfBuc33PiRpJdc*y484m4UqsyqXWB7P!KqSI*5btuPmKeDJN1wzpzzalwJeAvIh!yzCfxNSx3!aWJE1dcrVpohwUJgexvlF4nTJ9TbDIY8EehFEeIMw*9uqfIwuoc2tCk9DVfd*8r!g$$,9e5f94bc-e8a4-4e73-b8be-63364c29d753,2025-09-24T00:00:00.0000000Z,localhost
user2@gmail.com,gmail_acc1,1//0gJA7asfdZKRE8z...your_gmail_refresh_token_1,558976430978-xxxxxxxxxxxxxxx.apps.googleusercontent.com,2025-09-24T00:00:00.0000000Z,localhost
user3@outlook.com,outlook_acc1,M.C538_BAY.0.U.-Cs20*HMW5C11W!...,9e5f94bc-e8a4-4e73-b8be-63364c29d753,2025-09-24T00:00:00.0000000Z,localhost
```

## Usage

### Option 1: Import from File

Create a text file with account data (one per line):

```bash
python import_accounts.py -i accounts_data.txt -o accounts.json
```

### Option 2: Import from Stdin (Paste Data)

```bash
python import_accounts.py -o accounts.json
# Paste data, then Ctrl+D (on Linux/macOS) or Ctrl+Z + Enter (on Windows)
```

### Option 3: Custom IP Range

```bash
python import_accounts.py -i data.txt -o accounts.json --start-ip 10.0.0.1
```

By default, IPs start at `192.168.1.100` and increment for each account.

## Features

### Automatic Provider Detection

The script automatically detects the OAuth2 provider based on email domain:

| Domain | Provider | OAuth Endpoint |
|--------|----------|---|
| `gmail.com`, `googlemail.com` | Gmail | `smtp.gmail.com:587` |
| `outlook.com`, `hotmail.com`, `live.com`, `msn.com` | Outlook | `smtp.office365.com:587` |

### Automatic Field Generation

The script generates the following fields automatically:

- **IP Address**: Incremented from start IP (default: 192.168.1.100)
- **VMTA Name**: Generated from account_id (e.g., `vmta-pilare_acc1`)
- **Provider**: Detected from email domain
- **OAuth Endpoint**: Set based on provider type
- **OAuth Token URL**: Set based on provider type
- **Client Secret**: Empty for Outlook, generated for Gmail (if needed)

### Validation

The script validates:
- No duplicate email addresses
- No duplicate account IDs
- All required fields present

## Example Output

```
Importing accounts...
[1] Imported: pilareffiema0407@hotmail.com (account_id: pilare_acc1, provider: outlook)
[2] Imported: user2@gmail.com (account_id: gmail_acc1, provider: gmail)
[3] Imported: user3@outlook.com (account_id: outlook_acc1, provider: outlook)
[4] Imported: user4@hotmail.com (account_id: hotmail_acc1, provider: outlook)

[OK] Successfully imported 4 accounts
[OK] Validation passed: 4 unique accounts
[OK] Saved 4 accounts to accounts.json

Summary:
  Total accounts: 4
  Gmail accounts: 1
  Outlook accounts: 3
  IP range: 192.168.1.100 to 192.168.1.103
```

## Generated accounts.json Structure

For each account, the script generates:

```json
{
  "account_id": "pilare_acc1",
  "email": "pilareffiema0407@hotmail.com",
  "ip_address": "192.168.1.100",
  "vmta_name": "vmta-pilare_acc1",
  "provider": "outlook",
  "client_id": "9e5f94bc-e8a4-4e73-b8be-63364c29d753",
  "client_secret": "",
  "refresh_token": "M.C519_BAY.0.U.-Cuf!4ApwaD8lIRZ0...",
  "oauth_endpoint": "smtp.office365.com:587",
  "oauth_token_url": "https://login.live.com/oauth20_token.srf",
  "max_concurrent_messages": 10,
  "max_messages_per_hour": 10000
}
```

## Advanced Usage

### Skip Errors and Continue

If some lines have errors, skip them and continue:

```bash
python import_accounts.py -i data.txt -o accounts.json --skip-errors
```

### Validate Only (Don't Save)

```bash
python import_accounts.py -i data.txt --validate-only
```

### Get Help

```bash
python import_accounts.py --help
```

## Workflow

1. **Prepare Data File**
   ```bash
   # Create accounts_data.txt with your account data
   cat > accounts_data.txt << EOF
   email1@gmail.com,acc1,refresh_token_1,client_id_1
   email2@outlook.com,acc2,refresh_token_2,client_id_2
   EOF
   ```

2. **Import to accounts.json**
   ```bash
   python import_accounts.py -i accounts_data.txt -o accounts.json
   ```

3. **Verify Generated File**
   ```bash
   # Check that accounts.json looks correct
   cat accounts.json | python -m json.tool | head -30
   ```

4. **Use with Proxy**
   ```bash
   # Start proxy with imported accounts
   python xoauth2_proxy.py --config accounts.json
   ```

5. **Update PMTA Config**
   ```bash
   # Generate PMTA routes from imported accounts
   python generate_pmta_config.py accounts.json -o pmta_generated.cfg
   ```

## Troubleshooting

### Error: "Invalid format. Expected at least 4 fields"

**Problem**: Line doesn't have enough comma-separated fields.

**Solution**: Check that all lines have at least 4 fields (email, account_id, refresh_token, client_id).

### Error: "Duplicate emails"

**Problem**: Same email appears in multiple lines.

**Solution**: Ensure each email address is unique.

### Error: "Duplicate account IDs"

**Problem**: Same account_id appears in multiple lines.

**Solution**: Ensure each account_id is unique.

### Generated file doesn't look right

**Problem**: accounts.json has unexpected values.

**Solution**: Check that your input data is in the correct format with proper comma separation.

## Notes

- Comments in data files start with `#` and are ignored
- Empty lines are ignored
- The script preserves all account data exactly as provided
- Timestamps and hostnames from your data are not used (they can be there for your records)
- IP addresses are auto-generated and assigned sequentially

## Security

- Never commit `accounts.json` to version control (contains refresh tokens)
- Protect the file with appropriate file permissions
- The refresh tokens in your data are real OAuth2 tokens - keep them private
- Consider using environment variables for sensitive data in production
