"""
Tests for the NetworkScanner class.
"""

import unittest
from unittest.mock import patch, MagicMock, PropertyMock
import pytest

from captiveclone.core.scanner import NetworkScanner
from captiveclone.core.models import WirelessNetwork
from captiveclone.utils.exceptions import InterfaceError


class TestNetworkScanner(unittest.TestCase):
    """Test cases for the NetworkScanner class."""
    
    @patch('captiveclone.core.scanner.netifaces')
    @patch('captiveclone.hardware.adapter.WirelessAdapter')
    def setUp(self, mock_adapter, mock_netifaces):
        """Set up test environment."""
        # Mock interfaces
        mock_netifaces.interfaces.return_value = ['lo', 'eth0', 'wlan0']
        
        # Mock adapter
        self.mock_adapter_instance = MagicMock()
        mock_adapter.return_value = self.mock_adapter_instance
        
        # Create scanner instance
        self.scanner = NetworkScanner(interface='wlan0', timeout=1)
    
    def test_initialization(self):
        """Test scanner initialization."""
        self.assertEqual(self.scanner.interface, 'wlan0')
        self.assertEqual(self.scanner.timeout, 1)
        self.assertEqual(self.scanner.networks, {})
        self.assertIsNotNone(self.scanner.adapter)
    
    @patch('captiveclone.core.scanner.netifaces')
    def test_invalid_interface(self, mock_netifaces):
        """Test that an invalid interface raises an error."""
        mock_netifaces.interfaces.return_value = ['lo', 'eth0']
        
        with self.assertRaises(InterfaceError):
            NetworkScanner(interface='wlan0')
    
    @patch('captiveclone.core.scanner.sniff')
    def test_scan_basic(self, mock_sniff):
        """Test basic scanning functionality."""
        # Mock set_monitor_mode to return True
        self.mock_adapter_instance.set_monitor_mode.return_value = True
        
        # Mock sniff to avoid actual packet capturing
        mock_sniff.return_value = None
        
        # Mock _detect_captive_portals to avoid trying to connect to networks
        with patch.object(NetworkScanner, '_detect_captive_portals') as mock_detect:
            mock_detect.return_value = None
            
            # Run scan
            networks = self.scanner.scan()
            
            # Verify behavior
            self.mock_adapter_instance.set_monitor_mode.assert_called_with(True)
            mock_sniff.assert_called_once()
            mock_detect.assert_called_once()
            
            # Should return an empty list as we didn't mock any packets
            self.assertEqual(networks, [])
    
    def test_process_packet_not_beacon(self):
        """Test processing a non-beacon packet."""
        # Create a mock packet that's not a Dot11Beacon
        mock_packet = MagicMock()
        mock_packet.haslayer.return_value = False
        
        # Process the packet
        self.scanner._process_packet(mock_packet)
        
        # No networks should be created
        self.assertEqual(len(self.scanner.networks), 0)
    
    @patch('captiveclone.core.scanner.Dot11')
    @patch('captiveclone.core.scanner.Dot11Beacon')
    @patch('captiveclone.core.scanner.Dot11Elt')
    def test_process_beacon_packet(self, mock_dot11elt, mock_dot11beacon, mock_dot11):
        """Test processing a beacon packet."""
        # Create mock packet components
        mock_packet = MagicMock()
        mock_packet.haslayer.side_effect = lambda x: True
        
        # Mock Dot11 layer with a MAC address
        mock_dot11_layer = MagicMock()
        mock_dot11_layer.addr2 = '00:11:22:33:44:55'
        mock_packet.__getitem__.side_effect = lambda x: (
            mock_dot11_layer if x == mock_dot11 else 
            MagicMock()
        )
        
        # Mock Dot11Elt for SSID and channel
        mock_elt_ssid = MagicMock()
        mock_elt_ssid.ID = 0
        mock_elt_ssid.info = b'TestNetwork'
        
        mock_elt_channel = MagicMock()
        mock_elt_channel.ID = 3
        mock_elt_channel.info = bytes([6])  # Channel 6
        
        # Setup the packet to return our mock elements
        def mock_haslayer_side_effect(layer):
            if layer == mock_dot11.Beacon:
                return True
            if layer == mock_dot11elt:
                return True
            return False
        
        mock_packet.haslayer.side_effect = mock_haslayer_side_effect
        
        # Setup to return different Dot11Elt based on the count during iteration
        mock_get_dot11elt = MagicMock()
        mock_get_dot11elt.__getitem__.side_effect = [mock_elt_ssid, mock_elt_channel]
        mock_packet.__getitem__.side_effect = lambda x: (
            mock_dot11_layer if x == mock_dot11 else
            mock_get_dot11elt if x == mock_dot11elt else
            MagicMock()
        )
        
        # Mock the capability bits to indicate encryption
        mock_beacon = MagicMock()
        type(mock_beacon).cap = PropertyMock(return_value=MagicMock(privacy=True))
        mock_packet.__getitem__.side_effect = lambda x: (
            mock_dot11_layer if x == mock_dot11 else
            mock_beacon if x == mock_dot11beacon else
            mock_get_dot11elt if x == mock_dot11elt else
            MagicMock()
        )
        
        # Process the packet
        with patch.object(NetworkScanner, '_get_signal_strength', return_value=-70):
            self.scanner._process_packet(mock_packet)
        
        # One network should be created
        self.assertEqual(len(self.scanner.networks), 1)
        
        # Verify network details
        network = list(self.scanner.networks.values())[0]
        self.assertEqual(network.ssid, 'TestNetwork')
        self.assertEqual(network.bssid, '00:11:22:33:44:55')
        self.assertEqual(network.channel, 6)
        self.assertTrue(network.encryption)
        self.assertEqual(network.signal_strength, -70)
        self.assertFalse(network.has_captive_portal)
    
    @patch('captiveclone.core.scanner.socket')
    @patch('captiveclone.core.scanner.requests.Session')
    def test_check_for_captive_portal_redirect(self, mock_session, mock_socket):
        """Test captive portal detection with redirect."""
        # Mock DNS resolution success
        mock_socket.gethostbyname.return_value = '8.8.8.8'
        
        # Mock session and response for captive portal redirect
        mock_session_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 302
        mock_response.headers = {'Location': 'http://captive.portal/login'}
        mock_session_instance.get.return_value = mock_response
        mock_session.return_value = mock_session_instance
        
        # Mock _portal_requires_authentication to return True
        with patch.object(NetworkScanner, '_portal_requires_authentication', return_value=True):
            result = self.scanner._check_for_captive_portal()
        
        # Check result
        self.assertIsNotNone(result)
        portal_url, requires_auth, redirect_url = result
        self.assertEqual(portal_url, 'http://captive.portal/login')
        self.assertTrue(requires_auth)
        self.assertIsNone(redirect_url)
    
    @patch('captiveclone.core.scanner.socket')
    @patch('captiveclone.core.scanner.requests.Session')
    def test_check_for_captive_portal_no_portal(self, mock_session, mock_socket):
        """Test captive portal detection with no portal."""
        # Mock DNS resolution success
        mock_socket.gethostbyname.return_value = '8.8.8.8'
        
        # Mock session and response for direct connection (no captive portal)
        mock_session_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 204  # Success for generate_204
        mock_response.headers = {}
        mock_session_instance.get.return_value = mock_response
        mock_session.return_value = mock_session_instance
        
        result = self.scanner._check_for_captive_portal()
        
        # Should return None for no captive portal
        self.assertIsNone(result)
    
    @patch('captiveclone.core.scanner.requests')
    def test_portal_requires_authentication(self, mock_requests):
        """Test detection of authentication requirements in captive portal."""
        # Mock response with login form
        mock_response = MagicMock()
        mock_response.text = """
            <html>
                <body>
                    <form>
                        <input type="text" name="username">
                        <input type="password" name="password">
                        <button type="submit">Login</button>
                    </form>
                </body>
            </html>
        """
        mock_requests.get.return_value = mock_response
        
        result = self.scanner._portal_requires_authentication('http://test.portal')
        
        # Should detect authentication requirement
        self.assertTrue(result)
    
    @patch('captiveclone.core.scanner.requests')
    def test_portal_no_authentication(self, mock_requests):
        """Test detection of no authentication requirements in captive portal."""
        # Mock response with just an "Accept" button
        mock_response = MagicMock()
        mock_response.text = """
            <html>
                <body>
                    <h1>Welcome to WiFi</h1>
                    <p>Click the button to connect</p>
                    <form>
                        <button type="submit">Accept Terms</button>
                    </form>
                </body>
            </html>
        """
        mock_requests.get.return_value = mock_response
        
        result = self.scanner._portal_requires_authentication('http://test.portal')
        
        # Should not detect authentication requirement
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main() 