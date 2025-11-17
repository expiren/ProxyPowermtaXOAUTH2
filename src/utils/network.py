"""Network utilities for IP validation and network interface checking"""

import logging
import socket
import subprocess
from typing import List, Optional

logger = logging.getLogger('xoauth2_proxy')


def get_server_ips() -> List[str]:
    """
    Get all IP addresses configured on the server

    Returns:
        List of IP addresses (IPv4 and IPv6)
    """
    ips = []

    try:
        # Get hostname
        hostname = socket.gethostname()

        # Get all IP addresses for this host
        addr_info = socket.getaddrinfo(hostname, None)

        for info in addr_info:
            ip = info[4][0]
            if ip not in ips:
                ips.append(ip)

        # Also add localhost addresses
        for localhost in ['127.0.0.1', '::1']:
            if localhost not in ips:
                ips.append(localhost)

        # Try to get IPs from network interfaces (more reliable)
        try:
            import netifaces
            for interface in netifaces.interfaces():
                addrs = netifaces.ifaddresses(interface)
                # IPv4
                if netifaces.AF_INET in addrs:
                    for addr in addrs[netifaces.AF_INET]:
                        ip = addr.get('addr')
                        if ip and ip not in ips:
                            ips.append(ip)
                # IPv6
                if netifaces.AF_INET6 in addrs:
                    for addr in addrs[netifaces.AF_INET6]:
                        ip = addr.get('addr')
                        if ip and ip not in ips:
                            # Remove zone ID from IPv6 addresses (e.g., fe80::1%eth0 -> fe80::1)
                            ip = ip.split('%')[0]
                            ips.append(ip)
        except ImportError:
            # netifaces not available, use ip addr command as fallback
            logger.debug("[NetUtils] netifaces not available, using ip addr command")
            try:
                result = subprocess.run(
                    ['ip', 'addr', 'show'],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                if result.returncode == 0:
                    # Parse output for inet and inet6 lines
                    for line in result.stdout.split('\n'):
                        line = line.strip()
                        if line.startswith('inet '):
                            # inet 192.168.1.100/24 ...
                            parts = line.split()
                            if len(parts) >= 2:
                                ip = parts[1].split('/')[0]
                                if ip not in ips:
                                    ips.append(ip)
                        elif line.startswith('inet6 '):
                            # inet6 fe80::1/64 ...
                            parts = line.split()
                            if len(parts) >= 2:
                                ip = parts[1].split('/')[0]
                                if ip not in ips:
                                    ips.append(ip)
            except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
                logger.debug(f"[NetUtils] Could not run 'ip addr show': {e}")

        logger.debug(f"[NetUtils] Found {len(ips)} IP addresses on server")
        return ips

    except Exception as e:
        logger.warning(f"[NetUtils] Error getting server IPs: {e}")
        return []


def validate_ip_address(ip: str) -> bool:
    """
    Validate if an IP address is properly formatted

    Args:
        ip: IP address string to validate

    Returns:
        True if valid IPv4 or IPv6 address, False otherwise
    """
    if not ip:
        return False

    try:
        # Try parsing as IPv4 or IPv6
        socket.inet_pton(socket.AF_INET, ip)
        return True
    except OSError:
        pass

    try:
        socket.inet_pton(socket.AF_INET6, ip)
        return True
    except OSError:
        pass

    return False


def is_ip_available_on_server(ip: str, cached_ips: Optional[List[str]] = None) -> bool:
    """
    Check if an IP address is configured on the server

    Args:
        ip: IP address to check
        cached_ips: Optional cached list of server IPs (to avoid repeated lookups)

    Returns:
        True if IP is available on server, False otherwise
    """
    if not validate_ip_address(ip):
        logger.warning(f"[NetUtils] Invalid IP address format: {ip}")
        return False

    # Get server IPs (use cached if provided)
    server_ips = cached_ips if cached_ips is not None else get_server_ips()

    # Check if IP is in the list
    is_available = ip in server_ips

    if not is_available:
        logger.warning(
            f"[NetUtils] IP {ip} not found on server. Available IPs: {', '.join(server_ips[:5])}"
            f"{' ...' if len(server_ips) > 5 else ''}"
        )

    return is_available


def test_source_ip_binding(ip: str, test_host: str = "8.8.8.8", test_port: int = 53) -> bool:
    """
    Test if we can bind to a specific source IP by creating a test connection

    Args:
        ip: Source IP to test
        test_host: Test destination host (default: Google DNS)
        test_port: Test destination port (default: 53/DNS)

    Returns:
        True if binding successful, False otherwise
    """
    try:
        # Create a socket and try to bind to the source IP
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)

        # Bind to source IP (port 0 = any available port)
        sock.bind((ip, 0))

        # Try to connect (just to test, we'll close immediately)
        try:
            sock.connect((test_host, test_port))
        except:
            pass  # Connection might fail, but binding worked

        sock.close()
        logger.debug(f"[NetUtils] Successfully tested binding to {ip}")
        return True

    except OSError as e:
        logger.error(f"[NetUtils] Failed to bind to {ip}: {e}")
        return False
