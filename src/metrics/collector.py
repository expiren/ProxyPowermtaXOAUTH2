"""Prometheus metrics collection for XOAUTH2 Proxy"""

from prometheus_client import Counter, Gauge, Histogram


class MetricsCollector:
    """Prometheus metrics collection"""

    # SMTP Connection metrics
    smtp_connections_total = Counter(
        'smtp_connections_total',
        'Total SMTP connections received',
        ['account', 'result']
    )
    smtp_connections_active = Gauge(
        'smtp_connections_active',
        'Active SMTP connections',
        ['account']
    )
    smtp_commands_total = Counter(
        'smtp_commands_total',
        'Total SMTP commands processed',
        ['account', 'command']
    )

    # Authentication metrics
    auth_attempts_total = Counter(
        'auth_attempts_total',
        'Total AUTH attempts',
        ['account', 'result']
    )
    auth_duration_seconds = Histogram(
        'auth_duration_seconds',
        'AUTH operation duration',
        ['account']
    )

    # Token metrics
    token_refresh_total = Counter(
        'token_refresh_total',
        'Total token refresh attempts',
        ['account', 'result']
    )
    token_refresh_duration_seconds = Histogram(
        'token_refresh_duration_seconds',
        'Token refresh duration',
        ['account']
    )
    token_age_seconds = Gauge(
        'token_age_seconds',
        'Current token age in seconds',
        ['account']
    )

    # Upstream XOAUTH2 metrics
    upstream_auth_total = Counter(
        'upstream_auth_total',
        'Upstream XOAUTH2 authentication attempts',
        ['account', 'result']
    )
    upstream_auth_duration_seconds = Histogram(
        'upstream_auth_duration_seconds',
        'Upstream XOAUTH2 auth duration',
        ['account']
    )

    # Message metrics
    messages_total = Counter(
        'messages_total',
        'Total messages processed',
        ['account', 'result']
    )
    messages_duration_seconds = Histogram(
        'messages_duration_seconds',
        'Message delivery duration',
        ['account']
    )

    # Concurrency metrics
    concurrent_messages = Gauge(
        'concurrent_messages',
        'Current concurrent messages',
        ['account']
    )
    concurrent_limit_exceeded = Counter(
        'concurrent_limit_exceeded',
        'Times concurrency limit exceeded',
        ['account']
    )

    # Dry-run metrics
    dry_run_messages = Counter(
        'dry_run_messages_total',
        'Messages processed in dry-run mode',
        ['account']
    )

    # Error metrics
    errors_total = Counter(
        'errors_total',
        'Total errors',
        ['account', 'error_type']
    )

    @staticmethod
    def get_metrics() -> dict:
        """Get all metrics as dictionary"""
        return {
            'smtp_connections_total': MetricsCollector.smtp_connections_total,
            'smtp_connections_active': MetricsCollector.smtp_connections_active,
            'auth_attempts_total': MetricsCollector.auth_attempts_total,
            'token_refresh_total': MetricsCollector.token_refresh_total,
            'messages_total': MetricsCollector.messages_total,
            'errors_total': MetricsCollector.errors_total,
        }
