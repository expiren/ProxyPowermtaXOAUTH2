#!/usr/bin/env python3
"""
Test burst connections to proxy - simulates 1000 simultaneous connections
"""
import socket
import time
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

def test_connection(conn_num):
    """Test a single connection to the proxy"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)

        # Connect to proxy
        sock.connect(('127.0.0.1', 2525))

        # Read greeting
        greeting = sock.recv(1024)

        # Send QUIT
        sock.sendall(b'QUIT\r\n')
        response = sock.recv(1024)

        sock.close()
        return (conn_num, True, "OK")

    except socket.error as e:
        return (conn_num, False, str(e))
    except Exception as e:
        return (conn_num, False, str(e))

def main():
    num_connections = int(sys.argv[1]) if len(sys.argv) > 1 else 1000

    print(f"Testing {num_connections} simultaneous connections to proxy...")
    print(f"Time: {time.strftime('%H:%M:%S')}")
    print("")

    start_time = time.time()
    successful = 0
    failed = 0
    errors = {}

    # Launch all connections simultaneously
    with ThreadPoolExecutor(max_workers=num_connections) as executor:
        futures = [executor.submit(test_connection, i) for i in range(num_connections)]

        # Collect results
        for future in as_completed(futures):
            conn_num, success, msg = future.result()

            if success:
                successful += 1
                if successful % 100 == 0:
                    print(f"  {successful} connections successful...")
            else:
                failed += 1
                error_type = msg.split(':')[0] if ':' in msg else msg
                errors[error_type] = errors.get(error_type, 0) + 1

    duration = time.time() - start_time

    print("")
    print("=== Results ===")
    print(f"Total:      {num_connections}")
    print(f"Successful: {successful} ({successful*100//num_connections}%)")
    print(f"Failed:     {failed} ({failed*100//num_connections if num_connections > 0 else 0}%)")
    print(f"Duration:   {duration:.2f}s")
    print(f"Rate:       {num_connections/duration:.0f} conn/sec")

    if errors:
        print("")
        print("=== Errors ===")
        for error_type, count in sorted(errors.items(), key=lambda x: x[1], reverse=True):
            print(f"  {error_type}: {count}")

    if failed > 0:
        print("")
        print("⚠️  Some connections failed!")
        print("   Check proxy logs: tail -f /var/log/xoauth2/xoauth2_proxy.log")
        return 1
    else:
        print("")
        print("✅ All connections successful!")
        return 0

if __name__ == '__main__':
    sys.exit(main())
