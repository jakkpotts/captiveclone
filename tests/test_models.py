"""
Tests for the core models.
"""

import pytest

from captiveclone.core.models import WirelessNetwork, CaptivePortal


def test_wireless_network_str():
    """Test the string representation of a WirelessNetwork."""
    network = WirelessNetwork(
        ssid="Test Network",
        bssid="00:11:22:33:44:55",
        channel=6,
        encryption=True,
        signal_strength=-70,
        has_captive_portal=True
    )
    
    # Test string representation
    network_str = str(network)
    assert "Test Network" in network_str
    assert "00:11:22:33:44:55" in network_str
    assert "6" in network_str
    assert "Encrypted" in network_str
    assert "Has captive portal" in network_str
    assert "-70 dBm" in network_str


def test_wireless_network_defaults():
    """Test default values for a WirelessNetwork."""
    network = WirelessNetwork(
        ssid="Test Network",
        bssid="00:11:22:33:44:55"
    )
    
    assert network.ssid == "Test Network"
    assert network.bssid == "00:11:22:33:44:55"
    assert network.channel is None
    assert network.encryption is False
    assert network.signal_strength is None
    assert network.has_captive_portal is False


def test_captive_portal_str():
    """Test the string representation of a CaptivePortal."""
    network = WirelessNetwork(
        ssid="Test Network",
        bssid="00:11:22:33:44:55"
    )
    
    portal = CaptivePortal(
        network=network,
        requires_authentication=True,
        login_url="http://captive.portal/login",
        redirect_url="http://captive.portal/welcome"
    )
    
    # Test string representation
    portal_str = str(portal)
    assert "Test Network" in portal_str
    assert "Requires authentication" in portal_str
    assert "http://captive.portal/login" in portal_str
    assert "http://captive.portal/welcome" in portal_str


def test_captive_portal_defaults():
    """Test default values for a CaptivePortal."""
    network = WirelessNetwork(
        ssid="Test Network",
        bssid="00:11:22:33:44:55"
    )
    
    portal = CaptivePortal(
        network=network
    )
    
    assert portal.network == network
    assert portal.requires_authentication is False
    assert portal.login_url is None
    assert portal.redirect_url is None
    assert portal.form_fields is None 