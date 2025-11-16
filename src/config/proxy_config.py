"""Comprehensive proxy configuration from config.json"""

import json
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

from src.utils.exceptions import ConfigError

logger = logging.getLogger('xoauth2_proxy')


@dataclass
class ConnectionPoolConfig:
    """Connection pool configuration"""
    max_connections_per_account: int = 40
    max_messages_per_connection: int = 50
    connection_max_age_seconds: int = 300
    connection_idle_timeout_seconds: int = 60
    connection_acquire_timeout_seconds: int = 5

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConnectionPoolConfig':
        """Create from dictionary"""
        return cls(
            max_connections_per_account=data.get('max_connections_per_account', 40),
            max_messages_per_connection=data.get('max_messages_per_connection', 50),
            connection_max_age_seconds=data.get('connection_max_age_seconds', 300),
            connection_idle_timeout_seconds=data.get('connection_idle_timeout_seconds', 60),
            connection_acquire_timeout_seconds=data.get('connection_acquire_timeout_seconds', 5),
        )


@dataclass
class RateLimitConfig:
    """Rate limiting configuration"""
    enabled: bool = True
    messages_per_hour: int = 10000
    messages_per_minute_per_connection: int = 25
    burst_size: int = 50

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RateLimitConfig':
        """Create from dictionary"""
        return cls(
            enabled=data.get('enabled', True),
            messages_per_hour=data.get('messages_per_hour', 10000),
            messages_per_minute_per_connection=data.get('messages_per_minute_per_connection', 25),
            burst_size=data.get('burst_size', 50),
        )


@dataclass
class RetryConfig:
    """Retry configuration"""
    max_attempts: int = 2
    backoff_factor: float = 2.0
    max_delay_seconds: int = 30
    jitter_enabled: bool = True

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RetryConfig':
        """Create from dictionary"""
        return cls(
            max_attempts=data.get('max_attempts', 2),
            backoff_factor=data.get('backoff_factor', 2.0),
            max_delay_seconds=data.get('max_delay_seconds', 30),
            jitter_enabled=data.get('jitter_enabled', True),
        )


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration"""
    enabled: bool = True
    failure_threshold: int = 5
    recovery_timeout_seconds: int = 60
    half_open_max_calls: int = 2

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CircuitBreakerConfig':
        """Create from dictionary"""
        return cls(
            enabled=data.get('enabled', True),
            failure_threshold=data.get('failure_threshold', 5),
            recovery_timeout_seconds=data.get('recovery_timeout_seconds', 60),
            half_open_max_calls=data.get('half_open_max_calls', 2),
        )


@dataclass
class ProviderConfig:
    """Provider-specific configuration"""
    connection_pool: ConnectionPoolConfig
    rate_limiting: RateLimitConfig
    retry: RetryConfig
    circuit_breaker: CircuitBreakerConfig

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProviderConfig':
        """Create from dictionary"""
        return cls(
            connection_pool=ConnectionPoolConfig.from_dict(data.get('connection_pool', {})),
            rate_limiting=RateLimitConfig.from_dict(data.get('rate_limiting', {})),
            retry=RetryConfig.from_dict(data.get('retry', {})),
            circuit_breaker=CircuitBreakerConfig.from_dict(data.get('circuit_breaker', {})),
        )


@dataclass
class GlobalConfig:
    """Global proxy configuration"""
    max_concurrent_connections: int = 1000
    global_concurrency_limit: int = 100
    backpressure_queue_size: int = 1000
    connection_backlog: int = 100
    oauth2_timeout: int = 10
    smtp_timeout: int = 30
    connection_acquire_timeout: int = 5

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GlobalConfig':
        """Create from dictionary"""
        concurrency = data.get('concurrency', {})
        timeouts = data.get('timeouts', {})

        return cls(
            max_concurrent_connections=concurrency.get('max_concurrent_connections', 1000),
            global_concurrency_limit=concurrency.get('global_concurrency_limit', 100),
            backpressure_queue_size=concurrency.get('backpressure_queue_size', 1000),
            connection_backlog=concurrency.get('connection_backlog', 100),
            oauth2_timeout=timeouts.get('oauth2_timeout', 10),
            smtp_timeout=timeouts.get('smtp_timeout', 30),
            connection_acquire_timeout=timeouts.get('connection_acquire_timeout', 5),
        )


@dataclass
class FeatureFlags:
    """Feature flags"""
    smtp_pipelining: bool = True
    connection_pooling: bool = True
    xoauth2_verification: bool = False
    backpressure_control: bool = True
    rate_limiting: bool = True
    circuit_breaker: bool = True
    metrics_enabled: bool = True

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FeatureFlags':
        """Create from dictionary"""
        return cls(
            smtp_pipelining=data.get('smtp_pipelining', True),
            connection_pooling=data.get('connection_pooling', True),
            xoauth2_verification=data.get('xoauth2_verification', False),
            backpressure_control=data.get('backpressure_control', True),
            rate_limiting=data.get('rate_limiting', True),
            circuit_breaker=data.get('circuit_breaker', True),
            metrics_enabled=data.get('metrics_enabled', True),
        )


class ProxyConfig:
    """Main proxy configuration"""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path
        self.global_config: GlobalConfig = GlobalConfig()
        self.providers: Dict[str, ProviderConfig] = {}
        self.features: FeatureFlags = FeatureFlags()
        self.metrics_port: int = 9090

        if config_path and config_path.exists():
            self.load(config_path)
        else:
            # Load defaults
            self._load_defaults()

    def load(self, config_path: Path):
        """Load configuration from JSON file"""
        if not config_path.exists():
            logger.warning(f"[ProxyConfig] Config file not found: {config_path}, using defaults")
            self._load_defaults()
            return

        try:
            with open(config_path, 'r') as f:
                data = json.load(f)

            # Load global config
            if 'global' in data:
                self.global_config = GlobalConfig.from_dict(data['global'])

            # Load provider configs
            if 'providers' in data:
                for provider_name, provider_data in data['providers'].items():
                    self.providers[provider_name] = ProviderConfig.from_dict(provider_data)

            # Load feature flags
            if 'features' in data:
                self.features = FeatureFlags.from_dict(data['features'])

            # Load monitoring config
            if 'monitoring' in data:
                self.metrics_port = data['monitoring'].get('metrics_port', 9090)

            logger.info(
                f"[ProxyConfig] Loaded configuration from {config_path} "
                f"(providers: {list(self.providers.keys())})"
            )

        except json.JSONDecodeError as e:
            raise ConfigError(f"Invalid JSON in {config_path}: {e}")
        except Exception as e:
            raise ConfigError(f"Error loading config: {e}")

    def _load_defaults(self):
        """Load default provider configurations"""
        logger.info("[ProxyConfig] Loading default provider configurations")

        # Default Gmail config
        self.providers['gmail'] = ProviderConfig(
            connection_pool=ConnectionPoolConfig(
                max_connections_per_account=40,
                max_messages_per_connection=50,
                connection_max_age_seconds=600,
                connection_idle_timeout_seconds=120,
            ),
            rate_limiting=RateLimitConfig(
                messages_per_hour=10000,
                messages_per_minute_per_connection=25,
                burst_size=50,
            ),
            retry=RetryConfig(max_attempts=2, backoff_factor=2.0),
            circuit_breaker=CircuitBreakerConfig(failure_threshold=5),
        )

        # Default Outlook config
        self.providers['outlook'] = ProviderConfig(
            connection_pool=ConnectionPoolConfig(
                max_connections_per_account=30,
                max_messages_per_connection=40,
                connection_max_age_seconds=300,
                connection_idle_timeout_seconds=60,
            ),
            rate_limiting=RateLimitConfig(
                messages_per_hour=10000,
                messages_per_minute_per_connection=15,
                burst_size=30,
            ),
            retry=RetryConfig(max_attempts=2, backoff_factor=2.0),
            circuit_breaker=CircuitBreakerConfig(failure_threshold=5),
        )

        # Default fallback config
        self.providers['default'] = ProviderConfig(
            connection_pool=ConnectionPoolConfig(
                max_connections_per_account=30,
                max_messages_per_connection=50,
            ),
            rate_limiting=RateLimitConfig(messages_per_hour=5000),
            retry=RetryConfig(max_attempts=2),
            circuit_breaker=CircuitBreakerConfig(failure_threshold=5),
        )

    def get_provider_config(self, provider: str) -> ProviderConfig:
        """Get provider configuration (with fallback to default)"""
        provider_key = provider.lower()
        return self.providers.get(provider_key, self.providers.get('default', self.providers['gmail']))

    def to_dict(self) -> Dict[str, Any]:
        """Export configuration as dictionary"""
        return {
            'global': self.global_config.__dict__,
            'providers': {
                name: {
                    'connection_pool': cfg.connection_pool.__dict__,
                    'rate_limiting': cfg.rate_limiting.__dict__,
                    'retry': cfg.retry.__dict__,
                    'circuit_breaker': cfg.circuit_breaker.__dict__,
                }
                for name, cfg in self.providers.items()
            },
            'features': self.features.__dict__,
            'metrics_port': self.metrics_port,
        }
