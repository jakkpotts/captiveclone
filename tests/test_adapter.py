"""
Tests for the WirelessAdapter class.
"""

import unittest
from unittest.mock import patch, MagicMock, mock_open
import os

import pyric.pyw as pyw
import netifaces

from captiveclone.hardware.adapter import WirelessAdapter
from captiveclone.utils.exceptions import InterfaceError, AdapterError


class TestWirelessAdapter(unittest.TestCase):
    """Test cases for the WirelessAdapter class."""
    
    @patch('captiveclone.hardware.adapter.netifaces')
    @patch('captiveclone.hardware.adapter.pyw')
    def setUp(self, mock_pyw, mock_netifaces):
        """Set up test environment."""
        # Mock interfaces
        mock_netifaces.interfaces.return_value = ['lo', 'eth0', 'wlan0']
        
        # Mock the Card object
        self.mock_card = MagicMock()
        mock_pyw.getcard.return_value = self.mock_card
        
        # Mock mode
        mock_pyw.modeget.return_value = 'managed'
        
        # Create adapter instance
        self.adapter = WirelessAdapter('wlan0')
        
        # Save mocks for use in tests
        self.mock_pyw = mock_pyw
        self.mock_netifaces = mock_netifaces
    
    def test_initialization(self):
        """Test adapter initialization."""
        self.assertEqual(self.adapter.interface, 'wlan0')
        self.assertEqual(self.adapter.original_mode, 'managed')
    
    @patch('captiveclone.hardware.adapter.netifaces')
    def test_invalid_interface(self, mock_netifaces):
        """Test that an invalid interface raises an error."""
        mock_netifaces.interfaces.return_value = ['lo', 'eth0']
        
        with self.assertRaises(InterfaceError):
            WirelessAdapter('wlan0')
    
    @patch('captiveclone.hardware.adapter.subprocess.check_output')
    def test_detect_chipset_from_driver(self, mock_check_output):
        """Test detection of chipset from driver information."""
        # Mock driver output
        mock_check_output.return_value = "lrwxrwxrwx 1 root root 0 May 1 12:00 :ieee80211:ath9k_htc\n"
        
        chipset = self.adapter._detect_chipset()
        
        # Should extract the chipset name
        self.assertEqual(chipset, 'ath9k_htc')
    
    @patch('captiveclone.hardware.adapter.subprocess.check_output')
    def test_detect_chipset_from_airmon(self, mock_check_output):
        """Test detection of chipset from airmon-ng."""
        # Set side effect to simulate multiple command calls
        def side_effect(*args, **kwargs):
            if args[0][0] == 'ls':
                # First command fails
                raise subprocess.CalledProcessError(1, args[0])
            elif args[0][0] == 'airmon-ng':
                # airmon-ng output
                return "Interface\tChipset\t\tDriver\nwlan0\t\tAtheros AR9271\tath9k_htc\n"
            return ""
        
        mock_check_output.side_effect = side_effect
        
        chipset = self.adapter._detect_chipset()
        
        # Should extract the chipset from airmon-ng output
        self.assertEqual(chipset, 'Atheros AR9271')
    
    def test_check_monitor_mode_support_from_card(self):
        """Test detection of monitor mode support from card capabilities."""
        # Mock modes
        self.mock_pyw.devmodes.return_value = ['managed', 'monitor']
        
        result = self.adapter._check_monitor_mode_support()
        
        # Should detect monitor mode support
        self.assertTrue(result)
    
    def test_check_monitor_mode_support_from_chipset(self):
        """Test detection of monitor mode support from chipset."""
        # Mock modes (no monitor mode)
        self.mock_pyw.devmodes.return_value = ['managed']
        
        # Set a known chipset that supports monitor mode
        self.adapter.chipset = 'mt7612u'
        
        result = self.adapter._check_monitor_mode_support()
        
        # Should detect monitor mode support from chipset
        self.assertTrue(result)
    
    def test_set_monitor_mode(self):
        """Test setting monitor mode."""
        # Test setting monitor mode
        self.adapter.set_monitor_mode(True)
        
        # Verify calls
        self.mock_pyw.ifconfig.assert_any_call(self.mock_card, flags=0)
        self.mock_pyw.modeset.assert_called_with(self.mock_card, 'monitor')
        self.mock_pyw.ifconfig.assert_any_call(self.mock_card, flags=1)
    
    def test_get_mac_address(self):
        """Test getting the MAC address."""
        # Mock netifaces.ifaddresses
        self.mock_netifaces.AF_LINK = 17  # Typical value for AF_LINK
        self.mock_netifaces.ifaddresses.return_value = {
            17: [{'addr': '00:11:22:33:44:55'}]
        }
        
        mac = self.adapter.get_mac_address()
        
        # Should get the MAC address
        self.assertEqual(mac, '00:11:22:33:44:55')
    
    def test_set_channel(self):
        """Test setting the channel."""
        # Test setting channel
        result = self.adapter.set_channel(6)
        
        # Verify calls
        self.mock_pyw.chset.assert_called_with(self.mock_card, 6)
        self.assertTrue(result)
    
    @patch('captiveclone.hardware.adapter.pyw.winterfaces')
    def test_find_wireless_interfaces_with_pyric(self, mock_winterfaces):
        """Test finding wireless interfaces using pyric."""
        # Mock winterfaces to return a list of interfaces
        mock_winterfaces.return_value = ['wlan0', 'wlan1']
        
        interfaces = self.adapter.find_wireless_interfaces()
        
        # Should find the wireless interfaces
        self.assertEqual(interfaces, ['wlan0', 'wlan1'])
    
    @patch('captiveclone.hardware.adapter.pyw.winterfaces')
    @patch('captiveclone.hardware.adapter.subprocess.check_output')
    def test_find_wireless_interfaces_with_iwconfig(self, mock_check_output, mock_winterfaces):
        """Test finding wireless interfaces using iwconfig."""
        # Make pyric fail
        mock_winterfaces.side_effect = Exception("pyric failed")
        
        # Mock iwconfig output
        iwconfig_output = """
        wlan0     IEEE 802.11  ESSID:"TestNetwork"
                  Mode:Managed  Frequency:2.412 GHz  Access Point: 00:11:22:33:44:55
        
        lo        no wireless extensions.
        
        eth0      no wireless extensions.
        """
        mock_check_output.return_value = iwconfig_output
        
        interfaces = self.adapter.find_wireless_interfaces()
        
        # Should find wireless interfaces from iwconfig
        self.assertEqual(interfaces, ['wlan0'])
    
    @patch('captiveclone.hardware.adapter.os.path.exists')
    @patch('captiveclone.hardware.adapter.os.listdir')
    def test_find_wireless_interfaces_from_sys(self, mock_listdir, mock_exists):
        """Test finding wireless interfaces by checking /sys."""
        # Mock all other methods to fail
        with patch('captiveclone.hardware.adapter.pyw.winterfaces', side_effect=Exception("pyric failed")), \
             patch('captiveclone.hardware.adapter.subprocess.check_output', side_effect=Exception("iwconfig failed")):
            
            # Mock os.listdir to return interfaces
            mock_listdir.return_value = ['lo', 'eth0', 'wlan0']
            
            # Mock os.path.exists to make wlan0 look like a wireless interface
            mock_exists.side_effect = lambda path: 'wlan0' in path
            
            interfaces = self.adapter.find_wireless_interfaces()
            
            # Should find wireless interfaces from /sys
            self.assertEqual(interfaces, ['wlan0'])
    
    def test_get_interface_capabilities(self):
        """Test getting interface capabilities."""
        # Mock attributes and methods
        self.adapter.chipset = 'ath9k_htc'
        self.adapter.supports_monitor_mode = True
        self.adapter.supports_injection = False
        
        with patch.object(WirelessAdapter, 'get_mac_address', return_value='00:11:22:33:44:55'), \
             patch.object(WirelessAdapter, '_get_supported_channels', return_value={'2.4GHz': [1, 2, 3], '5GHz': []}):
            
            # Mock supported modes
            self.mock_pyw.devmodes.return_value = ['managed', 'monitor']
            
            capabilities = self.adapter.get_interface_capabilities()
            
            # Check capabilities
            self.assertEqual(capabilities['interface'], 'wlan0')
            self.assertEqual(capabilities['chipset'], 'ath9k_htc')
            self.assertEqual(capabilities['mac_address'], '00:11:22:33:44:55')
            self.assertTrue(capabilities['supports_monitor_mode'])
            self.assertFalse(capabilities['supports_injection'])
            self.assertEqual(capabilities['channels']['2.4GHz'], [1, 2, 3])
            self.assertEqual(capabilities['supported_modes'], ['managed', 'monitor'])
    
    @patch('captiveclone.hardware.adapter.subprocess.run')
    def test_set_mac_address(self, mock_run):
        """Test setting MAC address."""
        # Mock successful return codes
        mock_run.return_value = MagicMock(returncode=0)
        
        # Mock get_mac_address to verify the change
        with patch.object(WirelessAdapter, 'get_mac_address', return_value='00:11:22:33:44:55'):
            result = self.adapter.set_mac_address('00:11:22:33:44:55')
        
        # Should succeed
        self.assertTrue(result)
        
        # Verify subprocess calls
        mock_run.assert_any_call(['ip', 'link', 'set', 'dev', 'wlan0', 'down'], check=True)
        mock_run.assert_any_call(['ip', 'link', 'set', 'dev', 'wlan0', 'address', '00:11:22:33:44:55'], check=True)
        mock_run.assert_any_call(['ip', 'link', 'set', 'dev', 'wlan0', 'up'], check=True)


if __name__ == '__main__':
    unittest.main() 