"""SMTP protocol constants"""

# SMTP Response Codes
SMTP_CODES = {
    # Success codes
    220: "Service ready",
    221: "Service closing",
    235: "Authentication successful",
    250: "Requested mail action ok",

    # Client input errors
    354: "Start mail input",

    # Temporary errors
    421: "Service not available",
    450: "Requested action not taken",
    451: "Requested action aborted",
    452: "Insufficient storage",
    454: "Temporary service unavailable",

    # Permanent errors
    500: "Syntax error",
    502: "Command not implemented",
    503: "Bad sequence of commands",
    504: "Parameter not implemented",
    550: "Requested action not taken",
    551: "User not local",
    552: "Message exceeds storage limit",
    553: "Requested action not taken - invalid recipient",
    554: "Transaction failed",
}

# SMTP States
SMTP_STATES = {
    'INITIAL': 'initial',
    'HELO_RECEIVED': 'helo_received',
    'AUTH_RECEIVED': 'auth_received',
    'MAIL_RECEIVED': 'mail_received',
    'RCPT_RECEIVED': 'rcpt_received',
    'DATA_RECEIVING': 'data_receiving',
}

# SMTP Commands
SMTP_COMMANDS = {
    'HELO': 'HELO',
    'EHLO': 'EHLO',
    'AUTH': 'AUTH',
    'MAIL': 'MAIL',
    'RCPT': 'RCPT',
    'DATA': 'DATA',
    'RSET': 'RSET',
    'VRFY': 'VRFY',
    'HELP': 'HELP',
    'NOOP': 'NOOP',
    'QUIT': 'QUIT',
}

# Server capabilities
SERVER_CAPABILITIES = [
    'AUTH LOGIN PLAIN',
    'SIZE 104857600',  # 100MB
    '8BITMIME',
    'PIPELINING',
    'ENHANCEDSTATUSCODES',
]

# Configuration defaults
DEFAULT_SMTP_PORT = 2525
DEFAULT_HOST = '127.0.0.1'
DEFAULT_TIMEOUT = 15
DEFAULT_MAX_CONCURRENT = 100
DEFAULT_GLOBAL_CONCURRENCY = 100

# Token refresh defaults
TOKEN_REFRESH_BUFFER_SECONDS = 300  # 5 minutes
TOKEN_REFRESH_TIMEOUT = 10

# Retry policy defaults
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_BACKOFF_FACTOR = 2
DEFAULT_RETRY_MAX_DELAY = 30

# Rate limiting defaults
DEFAULT_RATE_LIMIT_BUCKET_SIZE = 100
DEFAULT_RATE_LIMIT_REFILL_RATE = 10  # tokens per second

# Connection pool defaults
DEFAULT_POOL_MIN_SIZE = 5
DEFAULT_POOL_MAX_SIZE = 20
DEFAULT_POOL_TIMEOUT = 5

# Circuit breaker defaults
DEFAULT_CIRCUIT_BREAKER_THRESHOLD = 5  # failures before open
DEFAULT_CIRCUIT_BREAKER_TIMEOUT = 60  # seconds before half-open
