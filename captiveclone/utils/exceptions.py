"""
Custom exceptions for CaptiveClone.
"""


class CaptiveCloneError(Exception):
    """Base exception for all CaptiveClone errors."""
    pass


class InterfaceError(CaptiveCloneError):
    """Raised when there's an issue with a network interface."""
    pass


class AdapterError(CaptiveCloneError):
    """Raised when there's an issue with a wireless adapter or its capabilities."""
    pass


class ConfigError(CaptiveCloneError):
    """Raised when there's an issue with configuration."""
    pass


class DatabaseError(CaptiveCloneError):
    """Raised when there's an issue with the database."""
    pass


class ScanError(CaptiveCloneError):
    """Raised when there's an issue with network scanning."""
    pass


class CaptivePortalError(CaptiveCloneError):
    """Raised when there's an issue with captive portal detection or analysis."""
    pass


class CloneGenerationError(CaptiveCloneError):
    """Raised when there's an issue with portal clone generation."""
    pass


class HardwareError(CaptiveCloneError):
    """Raised when there's an issue with hardware components."""
    pass


class SecurityError(CaptiveCloneError):
    """Raised when there's a security-related issue."""
    pass


class APError(CaptiveCloneError):
    """Raised when there's an issue with access point creation or management."""
    pass


class DeauthError(CaptiveCloneError):
    """Raised when there's an issue with deauthentication."""
    pass


class CaptureError(CaptiveCloneError):
    """Raised when there's an issue with credential capture."""
    pass 