"""SMTP protocol constants"""

# Circuit breaker defaults (used in circuit_breaker.py)
DEFAULT_CIRCUIT_BREAKER_THRESHOLD = 5  # failures before open
DEFAULT_CIRCUIT_BREAKER_TIMEOUT = 60  # seconds before half-open

# Retry policy defaults (used in retry.py)
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_BACKOFF_FACTOR = 2
DEFAULT_RETRY_MAX_DELAY = 30

# Connection pool defaults (used in connection_pool.py)
DEFAULT_POOL_MIN_SIZE = 5
DEFAULT_POOL_MAX_SIZE = 20
