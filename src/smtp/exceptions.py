"""SMTP-specific exceptions"""

from src.utils.exceptions import ProxyException


class SMTPError(ProxyException):
    """Base SMTP error"""
    def __init__(self, code: int = 450, message: str = "SMTP Error"):
        self.code = code
        self.message = message
        super().__init__(f"{code} {message}")


class SMTPAuthenticationError(SMTPError):
    """SMTP authentication failed"""
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(454, message)


class SMTPConnectionError(SMTPError):
    """Cannot connect to SMTP server"""
    def __init__(self, message: str = "Connection failed"):
        super().__init__(450, message)


class SMTPRelayError(SMTPError):
    """Message relay failed"""
    def __init__(self, message: str = "Relay failed"):
        super().__init__(452, message)


class InvalidRecipient(SMTPError):
    """Invalid recipient"""
    def __init__(self, message: str = "Invalid recipient"):
        super().__init__(553, message)


class SMTPTimeout(SMTPError):
    """SMTP timeout"""
    def __init__(self, message: str = "SMTP timeout"):
        super().__init__(450, message)
