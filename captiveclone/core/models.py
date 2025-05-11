"""
Data models for CaptiveClone core functionality.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class WirelessNetwork:
    """Represents a wireless network."""
    
    ssid: str
    bssid: str
    channel: Optional[int] = None
    encryption: bool = False
    signal_strength: Optional[int] = None
    has_captive_portal: bool = False
    
    def __str__(self) -> str:
        """Return a string representation of the network."""
        encryption_str = "Encrypted" if self.encryption else "Open"
        portal_str = "Has captive portal" if self.has_captive_portal else "No captive portal"
        signal_str = f"{self.signal_strength} dBm" if self.signal_strength else "Unknown"
        
        return (
            f"SSID: {self.ssid} | "
            f"BSSID: {self.bssid} | "
            f"Channel: {self.channel or 'Unknown'} | "
            f"Security: {encryption_str} | "
            f"{portal_str} | "
            f"Signal: {signal_str}"
        )


@dataclass
class CaptivePortal:
    """Represents a captive portal from a network."""
    
    network: WirelessNetwork
    requires_authentication: bool = False
    login_url: Optional[str] = None
    redirect_url: Optional[str] = None
    form_fields: Optional[dict] = None
    
    def __str__(self) -> str:
        """Return a string representation of the captive portal."""
        auth_str = "Requires authentication" if self.requires_authentication else "No authentication required"
        
        return (
            f"Portal for {self.network.ssid} | "
            f"{auth_str} | "
            f"Login URL: {self.login_url or 'Unknown'} | "
            f"Redirect URL: {self.redirect_url or 'None'}"
        ) 