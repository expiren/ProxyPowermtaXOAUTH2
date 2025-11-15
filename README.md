# XOAUTH2 Proxy for PowerMTA & Outlook/Gmail SMTP

A Python-based SMTP proxy that bridges PowerMTA with Office 365/Outlook and Gmail SMTP servers using OAuth2 authentication (XOAUTH2 protocol).

## Features

- OAuth2 token management with automatic refresh
- Full XOAUTH2 SMTP authentication protocol
- Complete SMTP command support
- Asynchronous I/O with asyncio
- Connection pooling and rate limiting
- Prometheus metrics monitoring
- Comprehensive logging

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Edit `accounts.json` with your email accounts and OAuth2 credentials.

## Running the Proxy

```bash
python xoauth2_proxy_v2.py --config accounts.json --port 2525 --host 0.0.0.0
```

## Command Line Options

- `--config`: Path to accounts.json (default: accounts.json)
- `--port`: SMTP listening port (default: 2525)
- `--host`: Bind address (default: 127.0.0.1)
- `--dry-run`: Test mode without relaying messages

## Testing

Configure PowerMTA to use the proxy:
- Host: localhost or proxy IP
- Port: 2525 (or configured port)
- Username: Your email address
- Password: Any value (OAuth2 token is used instead)

## Monitoring

Prometheus metrics available at `http://localhost:9090/metrics`

Key metrics:
- `smtp_commands_total` - SMTP commands processed
- `auth_attempts_total` - Authentication attempts
- `messages_total` - Messages relayed

## Architecture

```
PowerMTA/Client
    ↓
XOAUTH2 Proxy
    ├─ OAuth2Manager (Token refresh)
    ├─ SMTPProxyHandler (Protocol)
    └─ UpstreamRelay (SMTP forwarding)
    ↓
Outlook/Gmail SMTP
```

## Security

⚠️ DO NOT commit accounts.json to version control
- It contains sensitive refresh tokens
- .gitignore already excludes it
- Use environment variables in production

## License

MIT License

## Support

For issues, check logs at `/tmp/xoauth2_proxy/xoauth2_proxy.log`
