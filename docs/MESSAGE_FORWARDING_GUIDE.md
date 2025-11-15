# Message Forwarding via XOAUTH2 Proxy

## How It Works Now

The proxy now **actually forwards messages** from PowerMTA to Gmail/Outlook SMTP servers using OAuth2:

```
PowerMTA (37.27.3.136)
    │ SMTP: AUTH + MAIL FROM + RCPT TO + DATA + message body
    ↓
XOAUTH2 Proxy (136.243.50.55:2525)
    ├─ Receives full message
    ├─ Authenticates sender: pilareffiema0407@hotmail.com
    ├─ Refreshes OAuth2 token
    └─ Connects to Gmail/Outlook SMTP + sends message
       ↓
Gmail/Outlook SMTP (smtp.office365.com:587 for Outlook)
    └─ Email delivered to recipient ✓
```

## Architecture

### What Changed

Before: Proxy only validated OAuth2 tokens (dry-run simulation)
Now: Proxy **forwards complete messages** to Gmail/Outlook SMTP servers

### The Flow Step by Step

1. **PowerMTA sends message to proxy**
   ```
   EHLO mx2.ajxtaueluy.uk.com
   AUTH PLAIN pilareffiema0407@hotmail.com placeholder
   MAIL FROM: <sender@example.com>
   RCPT TO: <recipient@gmail.com>
   DATA
   Subject: Test Email
   [message body]
   .
   ```

2. **Proxy authenticates sender**
   - Looks up "pilareffiema0407@hotmail.com" in accounts.json
   - Gets: provider="outlook", client_id, refresh_token
   - Refreshes OAuth2 token with Microsoft's endpoint
   - Receives: access_token, expires_in

3. **Proxy builds XOAUTH2 auth string**
   ```
   Plain: user=pilareffiema0407@hotmail.com\1auth=Bearer ACCESS_TOKEN\1\1
   Base64: dXNlcj1waWxhcmVmZmlybWE0MDdAaG90bWFpbC5jb20BYWN0aD1CZWFyZXIgQVNDSUlfVE9LRU4BAS8=
   ```

4. **Proxy connects to Outlook SMTP**
   ```
   Host: smtp.office365.com
   Port: 587
   TLS: STARTTLS
   ```

5. **Proxy authenticates with XOAUTH2**
   ```
   AUTH XOAUTH2 [base64 string from step 3]
   ```

6. **Proxy sends the message**
   ```
   MAIL FROM: <sender@example.com>
   RCPT TO: <recipient@gmail.com>
   DATA
   [same message body from PowerMTA]
   ```

7. **Proxy returns result to PowerMTA**
   ```
   Success: 250 2.0.0 OK
   Error: 454 4.7.0 Authentication failed
         450 4.4.2 Connection failed
         553 5.1.3 Invalid recipient
   ```

## Configuration (PowerMTA)

Your PowerMTA config already has the correct setup:

```cfg
<virtual-mta smtp-test-2>
    smtp-source-ip                     37.27.3.136
    host-name                          mx2.ajxtaueluy.uk.com
    <domain *>
        route                          136.243.50.55      # Proxy IP
        default-smtp-port              2525                # Proxy port
        use-starttls                   no                  # No TLS to proxy
        require-starttls               no
        use-unencrypted-plain-auth     yes                 # AUTH PLAIN
        auth-username                  "pilareffiema0407@hotmail.com"
        auth-password                  "placeholder"       # Any value works
    </domain>
</virtual-mta>
```

## Proxy Configuration

Start the proxy with:

```bash
# Standard (localhost only)
python xoauth2_proxy.py --config accounts.json

# Remote server (listen on all interfaces)
python xoauth2_proxy.py --config accounts.json --host 0.0.0.0 --port 2525

# Dry-run mode (test connections without sending)
python xoauth2_proxy.py --config accounts.json --dry-run

# Custom metrics port
python xoauth2_proxy.py --config accounts.json --metrics-port 9091
```

## Testing

### Test 1: Check Proxy Health

```bash
curl http://127.0.0.1:9090/health
# Response: {"status": "healthy"}
```

### Test 2: Check Metrics

```bash
curl http://127.0.0.1:9090/metrics | grep messages_total
# Shows: messages_total{account="pilareffiema0407@hotmail.com",result="success"} 1
```

### Test 3: View Logs

```bash
# Windows
Get-Content "$env:TEMP\xoauth2_proxy\xoauth2_proxy.log" -Tail 50 -Wait

# Linux/macOS
tail -f /var/log/xoauth2/xoauth2_proxy.log
```

### Test 4: Send Test Email via PowerMTA

Use swaks (SMTP testing tool):

```bash
swaks --server 136.243.50.55:2525 \
  --auth-user pilareffiema0407@hotmail.com \
  --auth-password placeholder \
  --from test@example.com \
  --to recipient@gmail.com \
  --subject "Test Email" \
  --body "Hello from proxy"
```

Expected output:
```
=== Trying 136.243.50.55:2525 ...
=== Connected to 136.243.50.55:2525.
<-  220 136.243.50.55 ESMTP service ready
 -> EHLO ...
<-  250 OK
 -> AUTH PLAIN ...
<-  235 2.7.0 Accepted
 -> MAIL FROM:<test@example.com>
<-  250 2.1.0 OK
 -> RCPT TO:<recipient@gmail.com>
<-  250 2.1.1 OK
 -> DATA
<-  354 Start mail input
 -> [message body]
 -> .
<-  250 2.0.0 OK
```

### Test 5: Check Proxy Logs for Success

Look for:
```
[pilareffiema0407@hotmail.com] Connecting to smtp.office365.com:587 (OUTLOOK) for 1 recipients
[pilareffiema0407@hotmail.com] Authenticating with XOAUTH2...
[pilareffiema0407@hotmail.com] XOAUTH2 auth response: 235
[pilareffiema0407@hotmail.com] Sending message to ['recipient@gmail.com']...
[pilareffiema0407@hotmail.com] Message sent successfully to 1 recipients
[pilareffiema0407@hotmail.com] Relayed message successfully
```

## Error Messages and Troubleshooting

### "Token refresh failed with status 400"

**Problem**: OAuth2 credentials are invalid
**Solution**: Regenerate the refresh token and update accounts.json

**Log**:
```
[pilareffiema0407@hotmail.com] Token refresh failed with status 400:
{"error":"invalid_grant","error_description":"...service abuse mode..."}
```

### "XOAUTH2 authentication failed: 454"

**Problem**: OAuth2 token is invalid for this account
**Solution**: Check that the access token matches the account provider

**Log**:
```
[pilareffiema0407@hotmail.com] XOAUTH2 auth response: 454
[pilareffiema0407@hotmail.com] XOAUTH2 authentication failed: (454, b'4.7.0 ...')
```

### "Connection timeout"

**Problem**: Cannot reach Gmail/Outlook SMTP server
**Solution**: Check firewall/network, verify port 587 is open

**Log**:
```
[pilareffiema0407@hotmail.com] Connection timeout
```

### "Some recipients rejected: recipient@invalid.com: (550, ...)"

**Problem**: One or more recipients don't exist
**Solution**: Check recipient email addresses

**Log**:
```
[pilareffiema0407@hotmail.com] Some recipients rejected:
{'recipient@invalid.com': (550, b'5.1.2 The email account does not exist...')}
```

## Performance & Limits

### Rate Limits (from accounts.json)

```json
{
  "max_concurrent_messages": 10,
  "max_messages_per_hour": 10000
}
```

- **Concurrent**: Max 10 messages being sent at same time
- **Per hour**: Max 10,000 messages per hour per account

### Response Times

- Typical: 1-3 seconds per message
- First message of session: +1s (token refresh + connection)
- Subsequent messages: ~1s (connection reuse potential)

## Advanced Configuration

### Custom IP Range (when creating accounts.json)

```bash
python import_accounts.py -i data.txt -o accounts.json --start-ip 192.168.10.1
```

### Update Accounts (reload without restarting)

On Linux/macOS:
```bash
kill -HUP $(pgrep -f xoauth2_proxy)
```

Or restart the proxy:
```bash
# Kill old process
pkill -f xoauth2_proxy

# Start new one
python xoauth2_proxy.py --config accounts.json
```

### Monitor in Real-Time

```bash
# Terminal 1: Watch logs
tail -f /var/log/xoauth2/xoauth2_proxy.log | grep "Sending message"

# Terminal 2: Watch metrics
watch -n 1 'curl -s http://127.0.0.1:9090/metrics | grep messages_'
```

## How Message Content is Preserved

The proxy preserves the entire message from PowerMTA:

```
From PowerMTA          → To Gmail/Outlook
────────────────────────────────────────
MAIL FROM: sender      → MAIL FROM: sender (preserved)
RCPT TO: recipient     → RCPT TO: recipient (preserved)
DATA                   → DATA (preserved)
├─ Subject: Test       ├─ Subject: Test
├─ Body: ...           ├─ Body: ...
└─ Headers: ...        └─ Headers: ...
```

The proxy acts as a **message relay** - it doesn't modify the message, only adds XOAUTH2 authentication on top.

## Integration with Your Application

1. **Your application** → PowerMTA (port 25)
2. **PowerMTA** → Proxy (port 2525, via route config)
3. **Proxy** → Gmail/Outlook SMTP

Your application code doesn't change - it still sends to PowerMTA as usual:

```python
# Your code stays the same
import smtplib

server = smtplib.SMTP('127.0.0.1', 25)  # PowerMTA (not the proxy!)
server.sendmail('sender@example.com', 'recipient@gmail.com', message)
server.quit()
```

PowerMTA handles routing to the proxy, which handles OAuth2 authentication and forwarding.

## Success Indicators

Check if everything is working:

### Indicator 1: Proxy Metrics

```bash
curl http://127.0.0.1:9090/metrics | grep messages_total
```

Should show increasing counts:
```
messages_total{account="pilareffiema0407@hotmail.com",result="success"} 5
```

### Indicator 2: Logs Show Message Flow

```bash
[pilareffiema0407@hotmail.com] Processing message for 1 recipients
[pilareffiema0407@hotmail.com] Connecting to smtp.office365.com:587 (OUTLOOK)
[pilareffiema0407@hotmail.com] Message sent successfully
[pilareffiema0407@hotmail.com] Relayed message successfully
```

### Indicator 3: Email Arrives

Check that emails are actually delivered to the recipient inbox.

## Next Steps

1. Start proxy: `python xoauth2_proxy.py --config accounts.json --host 0.0.0.0`
2. Send test email via PowerMTA
3. Check logs: tail -f logs
4. Check metrics: curl http://127.0.0.1:9090/metrics
5. Monitor email delivery

That's it! Your proxy now forwards messages end-to-end.
