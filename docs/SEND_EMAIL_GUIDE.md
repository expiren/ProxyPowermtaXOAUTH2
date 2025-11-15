# Sending Emails Through PowerMTA + XOAUTH2 Proxy

## Architecture

```
Your Code (send_email.py)
    ↓ (SMTP on port 25)
PowerMTA (127.0.0.1:25 or remote server IP)
    ├─ Receives SMTP connection
    ├─ Receives EHLO, AUTH PLAIN, MAIL FROM, etc.
    └─ Routes AUTH to proxy on port 2525
       ↓
XOAUTH2 Proxy (127.0.0.1:2525)
    ├─ Validates email against accounts.json
    ├─ Refreshes OAuth2 token if needed
    ├─ Returns 235 OK to PowerMTA
    └─ PowerMTA continues with message
       ↓
PowerMTA forwards to Gmail/Outlook SMTP servers
    ↓
Email delivered
```

## Key Points

1. **Your code connects to PowerMTA**, NOT the proxy
2. **PowerMTA port**: 25 (SMTP) or 587 (SMTP+TLS)
3. **Proxy port**: 2525 (internal, PowerMTA uses it for AUTH validation only)
4. **Sender email**: Must be one of your configured accounts in `accounts.json`
5. **Password**: Can be anything (PowerMTA validates via OAuth2 proxy)

## Usage Examples

### Example 1: Send Test Email (Local PowerMTA)

```bash
python send_email.py \
  --from user1@gmail.com \
  --to recipient@example.com \
  --subject "Test Email" \
  --body "Hello, this is a test email"
```

**Expected output:**
```
[*] Loading accounts from accounts.json...
[OK] Found account: user1@gmail.com (provider: gmail)
[*] Connecting to 127.0.0.1:25...
[*] Server response: (250, b'127.0.0.1')
[*] Capabilities: ['AUTH LOGIN PLAIN', 'SIZE ...']
[*] Authenticating as user1@gmail.com...
[OK] Authentication successful
[*] Sending email from user1@gmail.com to recipient@example.com...
[OK] Email sent successfully
```

### Example 2: Send to Remote PowerMTA Server

If PowerMTA is on a different server (e.g., 37.27.3.136):

```bash
python send_email.py \
  --host 37.27.3.136 \
  --port 25 \
  --from pilareffiema0407@hotmail.com \
  --to test@example.com \
  --subject "Remote Server Test" \
  --body "Testing with remote PowerMTA"
```

### Example 3: Send HTML Email

```bash
python send_email.py \
  --from user2@outlook.com \
  --to recipient@example.com \
  --subject "HTML Email Test" \
  --body "<h1>Hello</h1><p>This is HTML content</p>" \
  --html
```

### Example 4: Test Connection (Dry-Run)

Test that everything works without actually sending:

```bash
python send_email.py \
  --from user1@gmail.com \
  --to recipient@example.com \
  --subject "Test" \
  --body "Test" \
  --dry-run
```

### Example 5: Custom Account Config Location

```bash
python send_email.py \
  --config /path/to/my_accounts.json \
  --from user1@gmail.com \
  --to recipient@example.com \
  --subject "Test" \
  --body "Test"
```

## Command-Line Options

```bash
python send_email.py --help

options:
  --host HOST              PowerMTA server address (default: 127.0.0.1)
  --port PORT              PowerMTA SMTP port (default: 25)
  --config CONFIG          Path to accounts.json (default: accounts.json)
  --from SENDER_EMAIL      Sender email address (REQUIRED)
  --to RECIPIENT_EMAIL     Recipient email address (REQUIRED)
  --subject SUBJECT        Email subject (REQUIRED)
  --body BODY              Email body text (REQUIRED)
  --html                   Treat body as HTML (optional)
  --dry-run                Test without sending (optional)
```

## Troubleshooting

### "Cannot connect to 127.0.0.1:25"

**Problem**: PowerMTA is not running or not listening on port 25

**Solution**:
```bash
# Check if PowerMTA is running
netstat -an | grep :25

# Or on Windows
netstat -an | findstr :25

# Start PowerMTA (if stopped)
# Linux
sudo /etc/init.d/pmta start

# Windows
# Start the PowerMTA service from Services
```

### "Authentication failed"

**Problem**: Email not found in accounts.json

**Solution**:
```bash
# List available accounts
python -c "import json; acc = json.load(open('accounts.json')); print('\n'.join([a['email'] for a in acc['accounts']]))"

# Make sure you use the exact email from the list
python send_email.py --from user1@gmail.com ...
```

### "User account is in service abuse mode"

**Problem**: OAuth2 account (Outlook) is temporarily blocked

**Solution**:
- Wait 24-48 hours and try again
- Or create a new test account with valid OAuth2 credentials
- Or temporarily disable rate limiting in PowerMTA

### "SMTP error: 550 Relaying denied"

**Problem**: PowerMTA is rejecting the message

**Solution**:
- Check PowerMTA configuration allows your IP
- Verify route configuration in pmta.cfg
- Check PowerMTA logs:
  ```bash
  # Linux
  tail -f /var/log/pmta/log

  # Windows
  # Check PowerMTA event viewer
  ```

## Python Integration

You can also import and use `send_email()` function in your code:

```python
from send_email import send_email

# Send email
success = send_email(
    smtp_host='127.0.0.1',
    smtp_port=25,
    sender_email='user1@gmail.com',
    recipient_email='recipient@example.com',
    subject='Test Subject',
    body='Test body text',
    html=False,
    dry_run=False
)

if success:
    print("Email sent!")
else:
    print("Failed to send email")
```

## Batch Sending Example

```python
from send_email import send_email
import json

# Load accounts
with open('accounts.json') as f:
    accounts = json.load(f)

# List of recipients
recipients = [
    'user1@example.com',
    'user2@example.com',
    'user3@example.com',
]

# Send from first account
sender = accounts['accounts'][0]['email']

# Send to each recipient
for recipient in recipients:
    print(f"Sending to {recipient}...")
    success = send_email(
        smtp_host='127.0.0.1',
        smtp_port=25,
        sender_email=sender,
        recipient_email=recipient,
        subject='Batch Test Email',
        body='This is a batch email',
    )
    if not success:
        print(f"  FAILED: {recipient}")
```

## Flow Diagram with Actual SMTP Commands

```
Client                    PowerMTA                    Proxy
  |                          |                          |
  |--- SMTP CONNECT -------->|                          |
  |<--- 220 Banner ----------|                          |
  |                          |                          |
  |--- EHLO hostname ------->|                          |
  |<--- 250 OK + Caps -------|                          |
  |                          |                          |
  |--- AUTH PLAIN ---------->|                          |
  |                          |--- AUTH PLAIN (fwd) ---->|
  |                          |<--- 235 OK (if valid) ---|
  |<--- 235 OK (success) ----|                          |
  |                          |                          |
  |--- MAIL FROM:<> ------->|                          |
  |<--- 250 OK --------------|                          |
  |                          |                          |
  |--- RCPT TO:<> -------->|                          |
  |<--- 250 OK --------------|                          |
  |                          |                          |
  |--- DATA ------------->|                          |
  |--- Message body ------>|                          |
  |--- . (CRLF.CRLF) ------>|                          |
  |<--- 250 OK --------------|                          |
  |                          |                          |
  |--- QUIT ------------->|                          |
  |<--- 221 Bye -----------|                          |
  |                          |                          |
  |                          |-- SEND to Gmail/Outlook ->|
  |                          |                          |
```

## Performance Notes

- **Connection pooling**: Each `send_email.py` call creates a new SMTP connection
- **For high volume**: Keep SMTP connection open and send multiple messages
- **Rate limiting**: PowerMTA enforces `max_messages_per_hour` per account (default: 10,000)
- **Concurrency**: PowerMTA enforces `max_concurrent_messages` per VMTA (default: 10)

## Real-World Example: Send Welcome Emails

```python
import csv
from send_email import send_email

# CSV file: users.csv
# email,name
# user1@example.com,Alice
# user2@example.com,Bob

sender = 'noreply@company.com'

with open('users.csv') as f:
    reader = csv.DictReader(f)
    for row in reader:
        recipient = row['email']
        name = row['name']

        body = f"Hello {name},\n\nWelcome to our service!"

        success = send_email(
            smtp_host='127.0.0.1',
            smtp_port=25,
            sender_email=sender,
            recipient_email=recipient,
            subject=f'Welcome {name}',
            body=body,
        )

        status = "✓ OK" if success else "✗ FAILED"
        print(f"{status}: {recipient}")
```

## Next Steps

1. **Start the proxy**: `python xoauth2_proxy.py --config accounts.json`
2. **Start PowerMTA**: Ensure it's running and configured
3. **Test with dry-run**: `python send_email.py ... --dry-run`
4. **Send test email**: `python send_email.py ... ` (without --dry-run)
5. **Check logs**: Monitor PowerMTA and proxy logs for details

---

**Summary**: Your code connects to **PowerMTA port 25**, not the proxy! PowerMTA handles the OAuth2 validation by routing AUTH requests to the proxy on port 2525.
