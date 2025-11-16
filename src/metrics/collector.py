"""Prometheus metrics collection for XOAUTH2 Proxy"""

from prometheus_client import Counter, Gauge, Histogram


class MetricsCollector:
    """Prometheus metrics collection"""

    # SMTP Connection metrics (account label removed to reduce cardinality)
    smtp_connections_total = Counter(
        'smtp_connections_total',
        'Total SMTP connections received',
        ['result']  # Only result, not account (1000 accounts = 1000x cardinality!)
    )
    smtp_connections_active = Gauge(
        'smtp_connections_active',
        'Active SMTP connections'
        # No labels - single gauge for all accounts (use separate dict for per-account tracking)
    )
    smtp_commands_total = Counter(
        'smtp_commands_total',
        'Total SMTP commands processed',
        ['command']  # Only command, not account
    )

    # Authentication metrics (account label removed to reduce cardinality)
    auth_attempts_total = Counter(
        'auth_attempts_total',
        'Total AUTH attempts',
        ['result']  # Only result, not account
    )
    auth_duration_seconds = Histogram(
        'auth_duration_seconds',
        'AUTH operation duration'
        # No labels - aggregate across all accounts
    )

    # Token metrics (account label removed to reduce cardinality)
    token_refresh_total = Counter(
        'token_refresh_total',
        'Total token refresh attempts',
        ['result']  # Only result, not account
    )
    token_refresh_duration_seconds = Histogram(
        'token_refresh_duration_seconds',
        'Token refresh duration'
        # No labels - aggregate across all accounts
    )
    # token_age_seconds removed - not useful at global level
    # For per-account token age, use internal dict tracking instead

    # Upstream XOAUTH2 metrics (account label removed to reduce cardinality)
    upstream_auth_total = Counter(
        'upstream_auth_total',
        'Upstream XOAUTH2 authentication attempts',
        ['result']  # Only result, not account
    )
    upstream_auth_duration_seconds = Histogram(
        'upstream_auth_duration_seconds',
        'Upstream XOAUTH2 auth duration'
        # No labels - aggregate across all accounts
    )

    # Message metrics (account label removed to reduce cardinality)
    messages_total = Counter(
        'messages_total',
        'Total messages processed',
        ['result']  # Only result, not account
    )
    messages_duration_seconds = Histogram(
        'messages_duration_seconds',
        'Message delivery duration'
        # No labels - aggregate across all accounts
    )

    # Concurrency metrics (account label removed to reduce cardinality)
    concurrent_messages = Gauge(
        'concurrent_messages',
        'Current concurrent messages'
        # No labels - total across all accounts (use internal dict for per-account)
    )
    concurrent_limit_exceeded = Counter(
        'concurrent_limit_exceeded',
        'Times concurrency limit exceeded'
        # No labels - total across all accounts
    )

    # Dry-run metrics (account label removed to reduce cardinality)
    dry_run_messages = Counter(
        'dry_run_messages_total',
        'Messages processed in dry-run mode'
        # No labels - total across all accounts
    )

    # Error metrics (account label removed to reduce cardinality)
    errors_total = Counter(
        'errors_total',
        'Total errors',
        ['error_type']  # Only error_type, not account
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
