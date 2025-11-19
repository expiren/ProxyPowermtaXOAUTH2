"""Network utilities for IP validation and network interface checking"""

import ipaddress
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


def is_reserved_ip(ip: str) -> bool:
    """
    Check if an IP address is in a reserved/private range and should NOT be used
    for outbound internet SMTP connections.

    Reserved ranges filtered:

    IPv4:
    - 0.0.0.0/8         - Current network
    - 10.0.0.0/8        - Private network
    - 100.64.0.0/10     - Shared address space (CGN)
    - 127.0.0.0/8       - Loopback
    - 169.254.0.0/16    - Link-local
    - 172.16.0.0/12     - Private network
    - 192.0.2.0/24      - Documentation
    - 192.168.0.0/16    - Private network
    - 198.18.0.0/15     - Benchmark testing
    - 198.51.100.0/24   - Documentation
    - 203.0.113.0/24    - Documentation
    - 224.0.0.0/4       - Multicast
    - 240.0.0.0/4       - Reserved
    - 255.255.255.255/32 - Broadcast

    IPv6:
    - ::/128            - Unspecified
    - ::1/128           - Loopback
    - fe80::/10         - Link-local
    - fc00::/7          - Unique local address (private)
    - ff00::/8          - Multicast
    - 2001:db8::/32     - Documentation

    Args:
        ip: IP address string to check

    Returns:
        True if IP is reserved/private and should be skipped, False if public
    """
    try:
        ip_obj = ipaddress.ip_address(ip)

        # IPv4 reserved ranges
        if isinstance(ip_obj, ipaddress.IPv4Address):
            reserved_ranges = [
                ipaddress.ip_network('0.0.0.0/8'),          # Current network
                ipaddress.ip_network('10.0.0.0/8'),         # Private
                ipaddress.ip_network('100.64.0.0/10'),      # Shared address space
                ipaddress.ip_network('127.0.0.0/8'),        # Loopback
                ipaddress.ip_network('169.254.0.0/16'),     # Link-local
                ipaddress.ip_network('172.16.0.0/12'),      # Private
                ipaddress.ip_network('192.0.2.0/24'),       # Documentation
                ipaddress.ip_network('192.168.0.0/16'),     # Private
                ipaddress.ip_network('198.18.0.0/15'),      # Benchmark testing
                ipaddress.ip_network('198.51.100.0/24'),    # Documentation
                ipaddress.ip_network('203.0.113.0/24'),     # Documentation
                ipaddress.ip_network('224.0.0.0/4'),        # Multicast
                ipaddress.ip_network('240.0.0.0/4'),        # Reserved
                ipaddress.ip_network('255.255.255.255/32'), # Broadcast
            ]

            for network in reserved_ranges:
                if ip_obj in network:
                    logger.debug(f"[NetUtils] IP {ip} is in reserved range {network}")
                    return True

        # IPv6 reserved ranges
        elif isinstance(ip_obj, ipaddress.IPv6Address):
            reserved_ranges = [
                ipaddress.ip_network('::/128'),         # Unspecified
                ipaddress.ip_network('::1/128'),        # Loopback
                ipaddress.ip_network('fe80::/10'),      # Link-local
                ipaddress.ip_network('fc00::/7'),       # Unique local (private)
                ipaddress.ip_network('ff00::/8'),       # Multicast
                ipaddress.ip_network('2001:db8::/32'),  # Documentation
            ]

            for network in reserved_ranges:
                if ip_obj in network:
                    logger.debug(f"[NetUtils] IP {ip} is in reserved range {network}")
                    return True

        # If we get here, IP is public and usable
        return False

    except ValueError as e:
        # Invalid IP format
        logger.warning(f"[NetUtils] Invalid IP address format: {ip} - {e}")
        return True  # Treat invalid IPs as "reserved" (skip them)


def get_public_server_ips(use_ipv6: bool = False) -> List[str]:
    """
    Get all PUBLIC (non-reserved) IP addresses configured on the server.
    Filters out private, loopback, link-local, and other reserved ranges.

    Args:
        use_ipv6: Include IPv6 addresses (default: False)

    Returns:
        List of public IP addresses suitable for outbound SMTP
    """
    all_ips = get_server_ips()
    public_ips = []

    for ip in all_ips:
        # Skip reserved IPs
        if is_reserved_ip(ip):
            continue

        # Skip IPv6 if disabled
        if ':' in ip and not use_ipv6:
            logger.debug(f"[NetUtils] Skipping IPv6 (use_ipv6=false): {ip}")
            continue

        public_ips.append(ip)

    logger.info(f"[NetUtils] Found {len(public_ips)} public IP(s) out of {len(all_ips)} total")
    return public_ips
