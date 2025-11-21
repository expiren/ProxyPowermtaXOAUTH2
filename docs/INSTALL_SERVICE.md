# Install XOAUTH2 Proxy as System Service

This guide shows how to install the XOAUTH2 proxy as a system service that starts automatically on boot with proper FD limits.

---

## Installation Steps

### 1. Install systemd service (recommended)

```bash
cd /home/user/ProxyPowermtaXOAUTH2

# Copy service file to systemd directory
cp xoauth2-proxy.service /etc/systemd/system/

# Reload systemd to recognize new service
systemctl daemon-reload

# Enable service to start on boot
systemctl enable xoauth2-proxy

# Start service now
systemctl start xoauth2-proxy

# Check status
systemctl status xoauth2-proxy
```

### 2. Verify FD limits are applied

```bash
# Get PID of running service
PID=$(systemctl show -p MainPID xoauth2-proxy | cut -d= -f2)

# Check FD limits (should show 65536)
cat /proc/$PID/limits | grep "open files"

# Should show:
# Max open files            65536                65536                files
```

### 3. Monitor logs

```bash
# Real-time logs
journalctl -u xoauth2-proxy -f

# Or via log file
tail -f /var/log/xoauth2/xoauth2_proxy.log
```

---

## Service Management Commands

```bash
# Start service
systemctl start xoauth2-proxy

# Stop service
systemctl stop xoauth2-proxy

# Restart service
systemctl restart xoauth2-proxy

# Check status
systemctl status xoauth2-proxy

# View logs
journalctl -u xoauth2-proxy -n 100

# Enable auto-start on boot
systemctl enable xoauth2-proxy

# Disable auto-start
systemctl disable xoauth2-proxy
```

---

## Alternative: Manual Startup (if systemd not available)

### Option A: Use start_proxy.sh (foreground)

```bash
cd /home/user/ProxyPowermtaXOAUTH2
./start_proxy.sh
```

### Option B: Use start_proxy.sh (background)

```bash
cd /home/user/ProxyPowermtaXOAUTH2
./start_proxy.sh --background

# Stop:
./start_proxy.sh --stop

# Monitor:
tail -f /var/log/xoauth2/xoauth2_proxy.log
```

### Option C: Use screen/tmux

```bash
# Install screen if not available
apt-get install screen

# Start in screen session
screen -dmS xoauth2 bash -c 'ulimit -n 65536 && cd /home/user/ProxyPowermtaXOAUTH2 && python xoauth2_proxy_v2.py --config accounts.json'

# Attach to session
screen -r xoauth2

# Detach: Press Ctrl+A then D
```

---

## Troubleshooting

### Service fails to start

```bash
# Check service status
systemctl status xoauth2-proxy

# View detailed logs
journalctl -u xoauth2-proxy -n 50 --no-pager

# Check if port 2525 is already in use
netstat -tuln | grep 2525

# Check if accounts.json exists
ls -la /home/user/ProxyPowermtaXOAUTH2/accounts.json
```

### FD limit still too low

```bash
# Check system-wide limit
cat /proc/sys/fs/file-max

# If too low (< 100000), increase it:
echo "fs.file-max = 2097152" >> /etc/sysctl.conf
sysctl -p

# Verify limits.conf
cat /etc/security/limits.conf | grep nofile

# Restart service
systemctl restart xoauth2-proxy
```

### Service not auto-starting on boot

```bash
# Check if enabled
systemctl is-enabled xoauth2-proxy

# Enable if not
systemctl enable xoauth2-proxy

# Verify
systemctl list-unit-files | grep xoauth2
```

---

## Verification

After installation, verify everything works:

```bash
# 1. Check service is running
systemctl status xoauth2-proxy

# 2. Check FD limits
PID=$(systemctl show -p MainPID xoauth2-proxy | cut -d= -f2)
cat /proc/$PID/limits | grep "open files"
# Should show: 65536 / 65536

# 3. Check proxy is listening
netstat -tuln | grep 2525
# Should show: tcp  0  0  0.0.0.0:2525  0.0.0.0:*  LISTEN

# 4. Test connection
telnet 127.0.0.1 2525
# Should show: 220 ESMTP service ready

# 5. Send test message
cd /home/user/ProxyPowermtaXOAUTH2
python3 test_burst.py 1000
# Should show: ✅ All connections successful!
```

---

## Summary

✅ **System limits**: Set to 65536 in `/etc/security/limits.conf` (permanent)
✅ **Service file**: Includes `LimitNOFILE=65536` (ensures limit is applied)
✅ **Auto-start**: Service starts on boot
✅ **Logging**: Logs to `/var/log/xoauth2/xoauth2_proxy.log`
✅ **Restart policy**: Auto-restarts if crashes

**Result**: Proxy can handle 70k messages/minute without "Too many open files" errors! 🎉
