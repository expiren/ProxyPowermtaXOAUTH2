"""Async HTTP metrics server for Prometheus"""

import asyncio
import logging
import json
from aiohttp import web
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

logger = logging.getLogger('xoauth2_proxy')


class MetricsServer:
    """Async HTTP server for Prometheus metrics (fully async, no thread pool!)"""

    def __init__(self, host: str = '0.0.0.0', port: int = 9090):
        self.host = host
        self.port = port
        self.app = None
        self.runner = None
        self.site = None

    async def start(self):
        """Start metrics server (fully async)"""
        # Create aiohttp application
        self.app = web.Application()

        # Add routes
        self.app.router.add_get('/metrics', self._handle_metrics)
        self.app.router.add_get('/health', self._handle_health)
        self.app.router.add_get('/', self._handle_root)

        # Create runner (allows manual lifecycle control)
        self.runner = web.AppRunner(self.app, access_log=None)
        await self.runner.setup()

        # Create site (binds to host:port)
        self.site = web.TCPSite(self.runner, self.host, self.port)
        await self.site.start()

        logger.info(f"[MetricsServer] Started on http://{self.host}:{self.port}")

    async def stop(self):
        """Stop metrics server (fully async)"""
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()
        logger.info("[MetricsServer] Stopped")

    async def _handle_metrics(self, request: web.Request) -> web.Response:
        """Handle /metrics endpoint"""
        # Generate Prometheus metrics (CPU-bound but fast <10ms)
        metrics_data = generate_latest()
        return web.Response(
            body=metrics_data,
            content_type=CONTENT_TYPE_LATEST
        )

    async def _handle_health(self, request: web.Request) -> web.Response:
        """Handle /health endpoint"""
        health = {'status': 'healthy'}
        return web.json_response(health)

    async def _handle_root(self, request: web.Request) -> web.Response:
        """Handle / endpoint"""
        welcome = (
            'XOAUTH2 Proxy Metrics Server\n\n'
            'Endpoints:\n'
            '- /metrics (Prometheus metrics)\n'
            '- /health (Health check)\n'
        )
        return web.Response(text=welcome, content_type='text/plain')

    def __str__(self) -> str:
        """String representation"""
        return f"MetricsServer(http://{self.host}:{self.port})"
