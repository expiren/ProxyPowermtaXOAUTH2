"""HTTP metrics server for Prometheus"""

import asyncio
import logging
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

logger = logging.getLogger('xoauth2_proxy')


class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP request handler for metrics"""

    def do_GET(self):
        """Handle GET request"""
        if self.path == '/metrics':
            # Return Prometheus metrics
            metrics_data = generate_latest()
            self.send_response(200)
            self.send_header('Content-type', CONTENT_TYPE_LATEST)
            self.send_header('Content-Length', len(metrics_data))
            self.end_headers()
            self.wfile.write(metrics_data)

        elif self.path == '/health':
            # Return health status
            health = {'status': 'healthy'}
            health_json = json.dumps(health).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Content-Length', len(health_json))
            self.end_headers()
            self.wfile.write(health_json)

        elif self.path == '/':
            # Welcome message
            welcome = b'XOAUTH2 Proxy Metrics Server\n\nEndpoints:\n- /metrics (Prometheus metrics)\n- /health (Health check)\n'
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.send_header('Content-Length', len(welcome))
            self.end_headers()
            self.wfile.write(welcome)

        else:
            self.send_response(404)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Not found')

    def log_message(self, format, *args):
        """Override to use logger instead of print"""
        logger.debug(f"[MetricsServer] {format % args}")


class MetricsServer:
    """HTTP server for Prometheus metrics"""

    def __init__(self, host: str = '0.0.0.0', port: int = 9090):
        self.host = host
        self.port = port
        self.server = None

    async def start(self):
        """Start metrics server"""
        loop = asyncio.get_running_loop()

        # Create HTTP server
        self.server = HTTPServer((self.host, self.port), MetricsHandler)

        # Run server in thread pool
        await loop.run_in_executor(None, self.server.serve_forever)

    async def stop(self):
        """Stop metrics server"""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            logger.info("[MetricsServer] Stopped")

    def __str__(self) -> str:
        """String representation"""
        return f"MetricsServer(http://{self.host}:{self.port})"
