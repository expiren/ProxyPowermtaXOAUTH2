# Quick Start Guide

**For the impatient** 🚀

---

## Simplest Way to Run

### Step 1: Copy all files to one directory

```bash
# Your directory should contain:
xoauth2_proxy.py       # The proxy
accounts.json          # Configuration
pmta.cfg               # PMTA config (optional for testing proxy)
```

### Step 2: Run the proxy

```bash
# Windows
python xoauth2_proxy.py --config accounts.json

# Linux/macOS
python3 xoauth2_proxy.py --config accounts.json
```

That's it! The proxy will:
- ✅ Find `accounts.json` in the current directory
- ✅ Create logs automatically
- ✅ Start listening on 127.0.0.1:2525
- ✅ Export metrics on 127.0.0.1:9090

---

## How Config File Search Works

The proxy searches for your config file in this order:

1. **Exact path you provide**
   ```bash
   python3 xoauth2_proxy.py --config /path/to/accounts.json
   ```

2. **Current directory** (if relative path)
   ```bash
   python3 xoauth2_proxy.py --config accounts.json
   ```

3. **Current directory with `./` prefix**
   ```bash
   python3 xoauth2_proxy.py --config ./accounts.json
   ```

4. **Standard locations** (auto-searched):
   - Windows: `C:\xoauth2\accounts.json`, `%TEMP%\xoauth2_proxy\accounts.json`
   - Linux/macOS: `/var/log/xoauth2/accounts.json`, `~/.xoauth2/accounts.json`

### Example

If you're in `C:\project\` and `accounts.json` is there:

```bash
cd C:\project
python xoauth2_proxy.py --config accounts.json
# ✅ Works! Finds C:\project\accounts.json
```

---

## Log File Locations

The proxy automatically creates log files in:

### Windows
```
C:\Users\YOUR_USER\AppData\Local\Temp\xoauth2_proxy\xoauth2_proxy.log
```

### Linux
```
/var/log/xoauth2/xoauth2_proxy.log
```

### macOS
```
/var/log/xoauth2/xoauth2_proxy.log
```

Or in the current directory if no permission to create above.

---

## Testing

Once running, test in another terminal:

### Test 1: Health Check
```bash
curl http://127.0.0.1:9090/health
# Expected: {"status": "healthy"}
```

### Test 2: Metrics
```bash
curl http://127.0.0.1:9090/metrics
# Expected: Prometheus metrics
```

### Test 3: AUTH (if swaks installed)
```bash
swaks --server 127.0.0.1:2525 \
  --auth-user gmail.account1@gmail.com \
  --auth-password placeholder \
  --from test@example.com \
  --to verify@gmail.com
# Expected: 250 2.0.0 OK
```

---

## Common Commands

### Start in foreground (for testing)
```bash
python3 xoauth2_proxy.py --config accounts.json
```

### Start in background (Linux/macOS)
```bash
nohup python3 xoauth2_proxy.py --config accounts.json &
```

### Start on Windows with pythonw (no console)
```bash
pythonw xoauth2_proxy.py --config accounts.json
```

### View logs (Windows)
```bash
# PowerShell
Get-Content -Path "$env:TEMP\xoauth2_proxy\xoauth2_proxy.log" -Tail 50

# Command Prompt
type "%TEMP%\xoauth2_proxy\xoauth2_proxy.log"
```

### View logs (Linux/macOS)
```bash
tail -f /var/log/xoauth2/xoauth2_proxy.log
# or
cat /var/log/xoauth2/xoauth2_proxy.log
```

### Stop the proxy
```bash
# Linux/macOS
pkill -f xoauth2_proxy

# Windows (if running in console)
Ctrl+C

# Windows (if running as service)
# See CROSS_PLATFORM_SETUP.md
```

---

## File Not Found Errors

### Error: "Config file not found: /etc/xoauth2/accounts.json"

**Solution 1: Use --config argument**
```bash
python3 xoauth2_proxy.py --config ./accounts.json
```

**Solution 2: Copy file to expected location**
```bash
# Linux/macOS
sudo mkdir -p /etc/xoauth2
sudo cp accounts.json /etc/xoauth2/
python3 xoauth2_proxy.py
```

**Solution 3: Run from same directory**
```bash
# Make sure accounts.json is in the same directory
python3 xoauth2_proxy.py --config accounts.json
```

---

## Startup Messages

### Success
```
2025-11-14 10:15:30 - xoauth2_proxy - INFO - XOAUTH2 Proxy starting on Linux - Logs: /var/log/xoauth2/xoauth2_proxy.log
2025-11-14 10:15:30 - xoauth2_proxy - INFO - Loaded 20 accounts from /project/accounts.json
2025-11-14 10:15:30 - xoauth2_proxy - INFO - ✓ Loaded 20 accounts from /project/accounts.json
2025-11-14 10:15:30 - xoauth2_proxy - INFO - Metrics server started on port 9090
2025-11-14 10:15:30 - xoauth2_proxy - INFO - XOAUTH2 proxy started successfully
```

### Error
```
2025-11-14 10:15:30 - xoauth2_proxy - ERROR - Config file not found: /etc/xoauth2/accounts.json

Searched in the following locations:
  1. /etc/xoauth2/accounts.json
  2. /project/accounts.json
  3. /home/user/.xoauth2/accounts.json

Current directory: /project

Files in current directory:
  - accounts.json

Usage: python xoauth2_proxy.py --config ./accounts.json
   or: python xoauth2_proxy.py --config accounts.json
```

---

## What Next?

1. **Test Auth**: `swaks --server 127.0.0.1:2525 --auth-user gmail.account1@gmail.com ...`
2. **Check Logs**: `tail -f /var/log/xoauth2/xoauth2_proxy.log`
3. **Monitor Metrics**: `curl http://127.0.0.1:9090/metrics`
4. **Configure PMTA**: Edit `pmta.cfg` with your settings
5. **Deploy**: See `DEPLOYMENT_GUIDE.md`

---

## Troubleshooting Checklist

- [ ] `accounts.json` exists in current directory or specified path
- [ ] JSON is valid (test with `python -m json.tool accounts.json`)
- [ ] Port 2525 is not already in use
- [ ] Dependencies installed (`pip install prometheus-client requests`)
- [ ] Check logs for detailed error messages
- [ ] Try with `--config ./accounts.json` if using relative path

---

**Now go build something awesome!** 🚀

