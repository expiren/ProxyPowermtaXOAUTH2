# Cross-Platform Setup Guide

**Version:** 1.0
**Status:** Windows, macOS, and Linux Supported
**Last Updated:** 2025-11-14

---

## Platform Support

✅ **Linux** (Primary)
- Log directory: `/var/log/xoauth2/`
- Config directory: `/etc/xoauth2/`
- Binary directory: `/opt/xoauth2/`

✅ **macOS** (Supported)
- Log directory: `/var/log/xoauth2/`
- Config directory: `/etc/xoauth2/` or `~/.xoauth2/`
- Binary directory: `/opt/xoauth2/` or `~/xoauth2/`

✅ **Windows** (Supported)
- Log directory: `%TEMP%\xoauth2_proxy\`
- Config directory: `C:\xoauth2\` or local directory
- Binary directory: `C:\Program Files\xoauth2\` or local directory

---

## Platform-Specific Log Paths

### Windows
```
%TEMP%\xoauth2_proxy\xoauth2_proxy.log
```

Example:
```
C:\Users\Administrator\AppData\Local\Temp\xoauth2_proxy\xoauth2_proxy.log
```

**Automatic Behavior:**
- If `%TEMP%` exists, logs go there
- If no write permission, logs go to current directory
- Directory created automatically if it doesn't exist

### Linux
```
/var/log/xoauth2/xoauth2_proxy.log
```

**Automatic Behavior:**
- Creates directory if it doesn't exist
- If no permission, falls back to current directory

### macOS
```
/var/log/xoauth2/xoauth2_proxy.log
```

**Automatic Behavior:**
- Same as Linux
- Can also use `~/xoauth2/` for user-specific logs

---

## Installation by Platform

### Windows Setup

**Step 1: Create directories**
```bash
# PowerShell
mkdir C:\xoauth2\config
mkdir C:\xoauth2\logs
```

**Step 2: Copy files**
```bash
copy xoauth2_proxy.py C:\xoauth2\
copy accounts.json C:\xoauth2\config\
copy pmta.cfg C:\path\to\pmta\config\
```

**Step 3: Run proxy**
```bash
# PowerShell
cd C:\xoauth2
python xoauth2_proxy.py --config config\accounts.json --host 127.0.0.1 --port 2525
```

**Step 4: Check logs**
```bash
# PowerShell
Get-Content -Path "$env:TEMP\xoauth2_proxy\xoauth2_proxy.log" -Tail 50
# or
tail -f "$env:TEMP\xoauth2_proxy\xoauth2_proxy.log"
```

**Step 5: Create Windows Service (Optional)**
```bash
# Install NSSM (Non-Sucking Service Manager)
choco install nssm

# Create service
nssm install XOAuth2Proxy "C:\Python312\python.exe" "C:\xoauth2\xoauth2_proxy.py --config C:\xoauth2\config\accounts.json"

# Start service
nssm start XOAuth2Proxy

# View logs
nssm status XOAuth2Proxy
```

### Linux Setup

**Step 1: Create directories**
```bash
sudo mkdir -p /var/log/xoauth2
sudo mkdir -p /etc/xoauth2
sudo mkdir -p /opt/xoauth2
```

**Step 2: Copy files**
```bash
sudo cp xoauth2_proxy.py /opt/xoauth2/
sudo cp accounts.json /etc/xoauth2/
sudo chmod 600 /etc/xoauth2/accounts.json
```

**Step 3: Create systemd service**
```bash
sudo tee /etc/systemd/system/xoauth2-proxy.service << 'EOF'
[Unit]
Description=XOAUTH2 SMTP Proxy
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/xoauth2
ExecStart=/usr/bin/python3 /opt/xoauth2/xoauth2_proxy.py --config /etc/xoauth2/accounts.json
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable xoauth2-proxy
sudo systemctl start xoauth2-proxy
```

**Step 4: Check logs**
```bash
tail -f /var/log/xoauth2/xoauth2_proxy.log
# or
journalctl -u xoauth2-proxy -f
```

### macOS Setup

**Step 1: Create directories**
```bash
mkdir -p /var/log/xoauth2
mkdir -p /etc/xoauth2
mkdir -p /opt/xoauth2
```

**Step 2: Copy files**
```bash
cp xoauth2_proxy.py /opt/xoauth2/
cp accounts.json /etc/xoauth2/
chmod 600 /etc/xoauth2/accounts.json
```

**Step 3: Create launchd service**
```bash
sudo tee /Library/LaunchDaemons/com.xoauth2.proxy.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.xoauth2.proxy</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>/opt/xoauth2/xoauth2_proxy.py</string>
    <string>--config</string>
    <string>/etc/xoauth2/accounts.json</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>/var/log/xoauth2/stdout.log</string>
  <key>StandardErrorPath</key>
  <string>/var/log/xoauth2/stderr.log</string>
</dict>
</plist>
EOF

sudo launchctl load /Library/LaunchDaemons/com.xoauth2.proxy.plist
```

**Step 4: Check logs**
```bash
tail -f /var/log/xoauth2/xoauth2_proxy.log
```

---

## Command-Line Arguments by Platform

### Windows
```bash
# Full path recommended
python C:\xoauth2\xoauth2_proxy.py `
  --config C:\xoauth2\config\accounts.json `
  --host 127.0.0.1 `
  --port 2525 `
  --metrics-port 9090
```

### Linux/macOS
```bash
# Can use relative or absolute paths
python3 /opt/xoauth2/xoauth2_proxy.py \
  --config /etc/xoauth2/accounts.json \
  --host 127.0.0.1 \
  --port 2525 \
  --metrics-port 9090
```

---

## Logging Behavior

### Automatic Log Path Detection

**Windows:**
1. Try to create `%TEMP%\xoauth2_proxy\`
2. If permission denied, use current directory
3. If that fails, output to console only

**Linux/macOS:**
1. Try to create `/var/log/xoauth2/`
2. If permission denied, use current directory
3. If that fails, output to console only

### Log Output

The proxy always logs to BOTH:
1. **File**: Platform-specific location (see above)
2. **Console**: Standard output (useful for debugging)

### Startup Message

```
2025-11-14 10:15:30 - xoauth2_proxy - INFO - XOAUTH2 Proxy starting on Linux - Logs: /var/log/xoauth2/xoauth2_proxy.log
2025-11-14 10:15:30 - xoauth2_proxy - INFO - XOAUTH2 proxy started successfully
```

Shows which OS and where logs are being written.

---

## Testing by Platform

### Windows
```bash
# PowerShell
python xoauth2_proxy.py --config accounts.json

# In another PowerShell window
swaks --server 127.0.0.1:25 `
  --auth-user gmail.account1@gmail.com `
  --auth-password placeholder `
  --from test@example.com `
  --to verify@gmail.com

# View logs
Get-Content -Path "$env:TEMP\xoauth2_proxy\xoauth2_proxy.log" -Tail 20
```

### Linux
```bash
# Start in foreground for testing
python3 /opt/xoauth2/xoauth2_proxy.py --config /etc/xoauth2/accounts.json

# In another terminal
swaks --server 127.0.0.1:25 \
  --auth-user gmail.account1@gmail.com \
  --auth-password placeholder \
  --from test@example.com \
  --to verify@gmail.com

# View logs
tail -f /var/log/xoauth2/xoauth2_proxy.log
```

### macOS
```bash
# Same as Linux, but may use Python 3 installed via Homebrew
python3 /opt/xoauth2/xoauth2_proxy.py --config /etc/xoauth2/accounts.json

# Test
swaks --server 127.0.0.1:25 \
  --auth-user gmail.account1@gmail.com \
  --auth-password placeholder \
  --from test@example.com \
  --to verify@gmail.com

# View logs
tail -f /var/log/xoauth2/xoauth2_proxy.log
```

---

## Troubleshooting by Platform

### Windows - No Log File Created

**Problem:** Logs don't appear in `%TEMP%\xoauth2_proxy\`

**Solutions:**
1. Check `%TEMP%` is set: `echo %TEMP%` in PowerShell
2. Check current directory for logs: `Get-ChildItem .\xoauth2_proxy.log`
3. Run proxy with verbose output to see where logs go
4. Check file permissions on `%TEMP%` directory

### Windows - Port Already in Use

**Problem:** `Address already in use` error on port 2525

**Solutions:**
```bash
# Find what's using port 2525
netstat -ano | findstr :2525

# Kill the process
taskkill /PID <PID> /F

# Or use different port
python xoauth2_proxy.py --config accounts.json --port 2526
```

### Linux - Permission Denied Creating Log Directory

**Problem:** `PermissionError: [Errno 13] Permission denied`

**Solutions:**
```bash
# Fix permissions
sudo mkdir -p /var/log/xoauth2
sudo chown $USER:$USER /var/log/xoauth2
sudo chmod 755 /var/log/xoauth2

# Or run proxy in current directory
python3 xoauth2_proxy.py --config accounts.json
# Logs will be in ./xoauth2_proxy.log
```

### macOS - Python3 Not Found

**Problem:** `python3: command not found`

**Solutions:**
```bash
# Install Python via Homebrew
brew install python@3.11

# Verify installation
python3 --version

# Use full path
/usr/local/bin/python3 /opt/xoauth2/xoauth2_proxy.py --config /etc/xoauth2/accounts.json
```

---

## Environment-Specific Configuration

### Development (Any Platform)

```bash
# Use current directory for logs and config
mkdir config logs
cp accounts.json config/
python3 xoauth2_proxy.py --config config/accounts.json
# Logs go to: ./xoauth2_proxy.log
```

### Production Linux

```bash
# Use standard system directories
sudo python3 /opt/xoauth2/xoauth2_proxy.py --config /etc/xoauth2/accounts.json
# Logs go to: /var/log/xoauth2/xoauth2_proxy.log
```

### Production Windows

```bash
# Create Windows Service (see section above)
# Service runs in background and logs to %TEMP%\xoauth2_proxy\
```

### Production macOS

```bash
# Use launchd service (see section above)
# Service runs in background and logs to /var/log/xoauth2/
```

---

## Verified Configurations

✅ **Windows 10/11**
- Python 3.10+
- Logs: `%TEMP%\xoauth2_proxy\xoauth2_proxy.log`
- PMTA: Works with local proxy

✅ **Ubuntu 20.04/22.04**
- Python 3.8+
- Logs: `/var/log/xoauth2/xoauth2_proxy.log`
- PMTA: Works with local proxy

✅ **CentOS/RHEL 8+**
- Python 3.6+
- Logs: `/var/log/xoauth2/xoauth2_proxy.log`
- PMTA: Works with local proxy

✅ **macOS 11+**
- Python 3.9+ (via Homebrew)
- Logs: `/var/log/xoauth2/xoauth2_proxy.log`
- PMTA: Works with local proxy

---

## Common Issues Across Platforms

### Issue: Cannot connect to proxy

```
ConnectionRefusedError: [Errno 111] Connection refused
```

**Diagnosis:**
```bash
# Check if proxy is running
ps aux | grep xoauth2_proxy  # Linux/macOS
tasklist | findstr python    # Windows

# Check if port is listening
netstat -tlnp | grep 2525    # Linux
netstat -ano | findstr :2525 # Windows
ss -tlnp | grep 2525         # Linux (alternative)
```

**Solution:**
```bash
# Ensure proxy is running
python3 xoauth2_proxy.py --config accounts.json &

# Verify listening
curl http://127.0.0.1:9090/health
```

### Issue: Permission denied reading config

```
PermissionError: [Errno 13] Permission denied: '.../accounts.json'
```

**Solution:**
```bash
# Check permissions
ls -la accounts.json

# Fix permissions
chmod 600 accounts.json
chmod 644 accounts.json  # If group needs to read
```

### Issue: ModuleNotFoundError

```
ModuleNotFoundError: No module named 'prometheus_client'
```

**Solution:**
```bash
# Install dependencies
pip install prometheus-client requests

# Or for Python3 specifically
pip3 install prometheus-client requests
```

---

## Success Indicators

✅ **Proxy Started Successfully**
```
XOAUTH2 Proxy starting on Linux - Logs: /var/log/xoauth2/xoauth2_proxy.log
XOAUTH2 proxy started successfully
```

✅ **Port is Listening**
```bash
netstat -tlnp | grep 2525
# Shows: tcp 0 0 127.0.0.1:2525 0.0.0.0:* LISTEN
```

✅ **Health Check Works**
```bash
curl http://127.0.0.1:9090/health
# Returns: {"status": "healthy"}
```

✅ **AUTH Works**
```bash
swaks --server 127.0.0.1:2525 \
  --auth-user gmail.account1@gmail.com \
  --auth-password placeholder \
  --from test@example.com \
  --to verify@gmail.com
# Returns: 250 2.0.0 OK
```

---

**Status:** Cross-Platform Ready ✅
**Platforms Tested:** Windows, Linux, macOS

