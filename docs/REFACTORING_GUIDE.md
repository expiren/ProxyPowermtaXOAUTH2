# XOAUTH2 Proxy v2.0 - Refactoring Guide

## Architecture Overview

The refactored proxy uses a **modular, scalable architecture** designed to handle thousands of accounts and thousands of requests per second.

### Directory Structure

```
src/
├── config/                 # Configuration management
│   ├── settings.py        # Global settings
│   ├── loader.py          # Load accounts.json
│   └── validators.py      # Validation (future)
│
├── oauth2/                # OAuth2 token management
│   ├── models.py          # OAuthToken, TokenCache
│   ├── manager.py         # Token refresh with pooling & caching
│   ├── exceptions.py      # OAuth2 errors
│
├── accounts/              # Account management
│   ├── models.py          # AccountConfig dataclass
│   ├── manager.py         # Account store + email cache
│   ├── cache.py           # (future) persistent cache
│
├── smtp/                  # SMTP protocol
│   ├── constants.py       # SMTP codes, defaults
│   ├── handler.py         # SMTP protocol handler (async)
│   ├── upstream.py        # XOAUTH2 relay with pooling
│   ├── proxy.py           # SMTP server
│   ├── exceptions.py      # SMTP errors
│
├── metrics/               # Monitoring
│   ├── collector.py       # Prometheus metrics
│   ├── server.py          # HTTP metrics server
│
├── logging/               # Logging setup
│   └── setup.py           # Cross-platform logging
│
└── utils/                 # Utilities
    ├── connection_pool.py # SMTP connection pooling
    ├── http_pool.py       # HTTP session pooling
    ├── retry.py           # Exponential backoff
    ├── circuit_breaker.py # Circuit breaker pattern
    ├── rate_limiter.py    # Token bucket rate limiting
    └── exceptions.py      # Custom exceptions
```

## Key Performance Features

### 1. Connection Pooling

**SMTP Connection Pool** (`src/utils/connection_pool.py`):
- Reuses connections to Gmail/Outlook SMTP servers
- Configurable min/max pool sizes
- Automatic idle connection cleanup
- Reduces latency for subsequent messages

**HTTP Session Pool** (`src/utils/http_pool.py`):
- Persistent HTTP session for OAuth2 token refresh
- Connection pooling at urllib3 level
- Automatic retry on 5xx errors

### 2. Token Management

**Token Cache** (`src/oauth2/manager.py`):
- Caches tokens in memory with TTL
- Automatic refresh before expiry (5-min buffer)
- Cache hits reduce OAuth2 API calls
- Per-provider circuit breakers

**Token Refresh** (`src/oauth2/manager.py`):
- Async token refresh via HTTP pool
- Retry with exponential backoff
- Circuit breaker to prevent cascading failures
- Provider-specific logic (Gmail vs Outlook)

### 3. Account Management

**Email Lookup Cache** (`src/accounts/manager.py`):
- Fast in-memory lookup by email
- O(1) account resolution
- Zero-copy after initial load

**Hot-Reload** (`src/accounts/manager.py`):
- Reload accounts without restarting
- Preserves existing tokens
- Thread-safe with asyncio.Lock

### 4. Rate Limiting

**Token Bucket** (`src/utils/rate_limiter.py`):
- Per-account message rate limiting
- Configurable max_messages_per_hour
- Non-blocking checks
- Automatic refill

### 5. Resilience

**Circuit Breaker** (`src/utils/circuit_breaker.py`):
- Prevents cascading failures
- Opens after N failures
- Half-open state for recovery testing
- Per-provider isolation

**Retry Logic** (`src/utils/retry.py`):
- Exponential backoff with jitter
- Configurable retry counts
- Specific exception handling

## Module Responsibilities

### Config Module
- Load and validate accounts.json
- Smart config file discovery
- Environment variable overrides

### OAuth2 Module
- Token refresh with HTTP pooling
- Token caching with TTL
- Provider-specific authentication
- Circuit breaker per provider

### Account Module
- Account store with email cache
- Account lookup O(1)
- Hot-reload support
- Thread-safe access

### SMTP Module
- Async SMTP protocol handler
- XOAUTH2 authentication
- Message relay to Gmail/Outlook
- Connection pooling

### Metrics Module
- Prometheus metrics collection
- HTTP metrics server
- Per-account statistics

### Utils Module
- Connection pooling (SMTP & HTTP)
- Retry logic with backoff
- Circuit breaker pattern
- Rate limiting
- Custom exceptions

## Performance Targets

| Target | Value |
|--------|-------|
| Concurrent Accounts | 1000+ |
| Requests/Second | 1000+ |
| Message Latency (P95) | < 2 seconds |
| Memory (1000 accounts) | < 500 MB |
| CPU (1000 req/sec) | < 1 core |
| Token Cache Hit Rate | > 95% |
| Connection Reuse Rate | > 90% |

## Design Patterns Used

### 1. Singleton Pattern
- `HTTPSessionPool`: Single HTTP session with connection pooling
- `CircuitBreakerManager`: Single manager for all circuit breakers

### 2. Connection Pool Pattern
- `SMTPConnectionPool`: Reuses SMTP connections
- `HTTPSessionPool`: Reuses HTTP connections

### 3. Circuit Breaker Pattern
- `CircuitBreaker`: Prevents cascading failures
- States: CLOSED → OPEN → HALF_OPEN → CLOSED

### 4. Token Bucket Pattern
- `TokenBucket`: Rate limiting with refill
- Allows bursty traffic up to capacity

### 5. Cache-Aside Pattern
- `OAuth2Manager`: Check cache, fetch if miss, update cache
- `AccountManager`: Email lookup cache

## Scalability Considerations

### For 1000+ Accounts
- In-memory account store: ~1 MB per 100 accounts
- Per-account concurrency limits: No global bottleneck
- Email lookup cache: O(1) access

### For 1000+ Requests/Second
- Async/await throughout: Non-blocking I/O
- Connection pooling: Reuse connections
- Token caching: Reduce OAuth2 calls
- Circuit breaker: Quick failures, fast recovery

### Memory Optimization
- Dataclasses: Minimal memory footprint
- Email cache: Only stores references
- Token cache: LRU with TTL (future)
- Metrics: Streaming update, no full history

### CPU Optimization
- Async I/O: Single thread handles many connections
- Connection reuse: Avoid TLS handshakes
- Token caching: Reduce crypto operations
- Fast path: Email cache for account lookup

## Configuration

### Via Environment Variables
```bash
export XOAUTH2_HOST=0.0.0.0
export XOAUTH2_PORT=2525
export XOAUTH2_METRICS_PORT=9090
export XOAUTH2_GLOBAL_CONCURRENCY=1000
export XOAUTH2_DRY_RUN=false
```

### Via Command-line
```bash
python xoauth2_proxy.py \
  --config accounts.json \
  --host 0.0.0.0 \
  --port 2525 \
  --global-concurrency 1000
```

## Testing

### Unit Tests
```bash
pytest src/                    # Test all modules
pytest src/oauth2/             # Test OAuth2 only
pytest src/accounts/           # Test accounts
```

### Integration Tests
```bash
pytest tests/integration/      # Full flow tests
```

### Load Testing
```bash
locust -f tests/load/           # 1000+ concurrent
ab -n 10000 -c 1000            # Benchmark
```

## Migration from v1.x

### What's Different
- **Modular**: Code split into logical modules
- **Performant**: Connection pooling, caching, circuit breaker
- **Scalable**: Designed for 1000+ accounts, 1000+ req/sec
- **Maintainable**: Clear separation of concerns
- **Testable**: Each module can be tested independently

### Configuration
- **No change**: accounts.json format stays the same
- **New**: Environment variable overrides

### Compatibility
- **API**: Same CLI arguments
- **Format**: Same XOAUTH2 protocol
- **Metrics**: Enhanced Prometheus metrics

## Future Enhancements

### Phase 2
- [ ] LRU token cache with TTL
- [ ] Database persistence for tokens
- [ ] Metrics history and trends
- [ ] Admin REST API
- [ ] Multi-region support

### Phase 3
- [ ] Kubernetes integration
- [ ] Helm charts
- [ ] Distributed rate limiting
- [ ] Load balancing
- [ ] Failover support

## Debugging

### Enable Debug Logging
```bash
export LOGLEVEL=DEBUG
python xoauth2_proxy.py --config accounts.json
```

### Monitor Metrics
```bash
watch -n 1 'curl -s http://127.0.0.1:9090/metrics | grep messages_'
```

### Check Circuit Breaker Status
```bash
curl -s http://127.0.0.1:9090/metrics | grep circuit_breaker
```

### Trace Token Refresh
```bash
tail -f logs | grep "Token refresh"
```

## Contributing

### Code Style
- Type hints on all functions
- Docstrings on public methods
- Async/await for I/O
- Exception handling on all paths

### Adding a Module
1. Create module in `src/`
2. Add exceptions in `module/exceptions.py`
3. Add dataclasses in `module/models.py`
4. Add logic in `module/manager.py`
5. Add tests in `tests/unit/module/`
6. Update `src/__init__.py`

## Performance Tuning

### Token Refresh
- Increase `token_cache_ttl` for more hits
- Increase `token_refresh_buffer` to pre-refresh earlier

### Connection Pooling
- Increase `pool_max_size` for more concurrent connections
- Decrease `pool_idle_timeout` to clean up faster

### Rate Limiting
- Adjust `max_messages_per_hour` per account type

### Concurrency
- Increase `global_concurrency_limit` for higher throughput
- Set `max_concurrent_per_account` for fair distribution

## Monitoring Checklist

- [ ] Connection pool: Active connections < max_size
- [ ] Token cache: Hit rate > 95%
- [ ] Circuit breaker: All CLOSED (no failures)
- [ ] Rate limiter: No rate limit errors
- [ ] Message latency: P95 < 2 seconds
- [ ] Memory: Stable, not growing
- [ ] CPU: < 1 core per 500 req/sec

---

**Status**: v2.0 Production Ready ✅

The refactored proxy is designed to handle enterprise-scale deployments with thousands of accounts and thousands of requests per second.
