"""
Wireless adapter abstraction layer for CaptiveClone.

This module provides an abstraction for working with wireless network interfaces.
"""

import logging
import subprocess
import os
import re
import time
from typing import List, Dict, Optional, Tuple, Any

import pyric.pyw as pyw
from pyric.pyw import Card
import netifaces

from captiveclone.utils.exceptions import InterfaceError, AdapterError

logger = logging.getLogger(__name__)

# Common chipsets that support monitor mode
MONITOR_MODE_CHIPSETS = {
    'mt7612u': 'MediaTek MT7612U',
    'mt7601u': 'MediaTek MT7601U',
    'rt2800usb': 'Ralink RT2800',
    'rtl8812au': 'Realtek RTL8812AU',
    'rtl8192cu': 'Realtek RTL8192CU',
    'ath9k_htc': 'Atheros AR9271',
    'ath10k': 'Atheros AR9280',
}


class WirelessAdapter:
    """
    Represents a physical wireless network adapter.
    
    This class provides methods for interacting with wireless network adapters,
    including changing modes, scanning for networks, and connecting to networks.
    """
    
    def __init__(self, interface: str):
        """
        Initialize a wireless adapter.
        
        Args:
            interface: Name of the wireless interface (e.g., 'wlan0')
            
        Raises:
            InterfaceError: If the interface does not exist or is not a wireless interface
        """
        self.interface = interface
        self._validate_interface()
        self.original_mode = self._get_current_mode()
        self.chipset = self._detect_chipset()
        self.supports_monitor_mode = self._check_monitor_mode_support()
        self.supports_injection = self._check_injection_support()
        
        logger.debug(f"Initialized adapter for interface {interface} (current mode: {self.original_mode}, chipset: {self.chipset})")
        logger.debug(f"Monitor mode support: {self.supports_monitor_mode}, Packet injection support: {self.supports_injection}")
    
    def _validate_interface(self) -> None:
        """
        Validate that the interface exists and is a wireless interface.
        
        Raises:
            InterfaceError: If the interface doesn't exist or is not a wireless interface
        """
        if self.interface not in netifaces.interfaces():
            raise InterfaceError(f"Interface {self.interface} does not exist")
        
        try:
            # Try to get the Card object for this interface
            pyw.getcard(self.interface)
        except Exception as e:
            raise InterfaceError(f"Interface {self.interface} is not a wireless interface: {str(e)}")
    
    def _get_current_mode(self) -> str:
        """
        Get the current mode of the wireless interface.
        
        Returns:
            Current mode of the interface (e.g., 'managed', 'monitor')
        """
        try:
            card = pyw.getcard(self.interface)
            mode = pyw.modeget(card)
            return mode
        except Exception as e:
            logger.warning(f"Could not determine mode for interface {self.interface}: {str(e)}")
            return "unknown"
    
    def _detect_chipset(self) -> Optional[str]:
        """
        Detect the chipset of the wireless adapter.
        
        Returns:
            String identifying the chipset, or None if not determined
        """
        chipset = None
        
        # Try to get chipset information from drivers
        try:
            # Method 1: Check kernel driver
            output = subprocess.check_output(
                ["ls", "-l", f"/sys/class/net/{self.interface}/device/driver/module/drivers"],
                stderr=subprocess.STDOUT,
                text=True
            )
            
            # Parse output to find driver name
            match = re.search(r":[^:]+:([^:]+)$", output)
            if match:
                chipset = match.group(1)
        except Exception:
            pass
        
        if not chipset:
            # Method 2: Check lsusb for USB adapters
            try:
                # First, find the device path
                output = subprocess.check_output(
                    ["readlink", "-f", f"/sys/class/net/{self.interface}/device"],
                    stderr=subprocess.STDOUT,
                    text=True
                ).strip()
                
                # Extract vendor and product ID from sysfs
                if '/usb' in output:
                    with open("/proc/bus/usb/devices", "r") as f:
                        usb_info = f.read()
                    
                    # This is simplified - a real implementation would parse this more carefully
                    # to match the specific interface
                    for line in usb_info.splitlines():
                        if self.interface in line or "Wireless" in line:
                            match = re.search(r"Vendor=([0-9a-f]+) ProdID=([0-9a-f]+)", line)
                            if match:
                                vendor_id, product_id = match.groups()
                                chipset = f"{vendor_id}:{product_id}"
                                break
            except Exception as e:
                logger.debug(f"Could not determine chipset from USB info: {str(e)}")
        
        if not chipset:
            # Method 3: Try using the airmon-ng command
            try:
                output = subprocess.check_output(
                    ["airmon-ng"], 
                    stderr=subprocess.STDOUT,
                    text=True
                )
                
                for line in output.splitlines():
                    if self.interface in line:
                        parts = line.split("\t")
                        if len(parts) >= 2:
                            chipset = parts[1].strip()
                            break
            except Exception as e:
                logger.debug(f"Could not determine chipset from airmon-ng: {str(e)}")
        
        if not chipset:
            # Method 4: Use ethtool to get driver information
            try:
                output = subprocess.check_output(
                    ["ethtool", "-i", self.interface],
                    stderr=subprocess.STDOUT,
                    text=True
                )
                
                for line in output.splitlines():
                    if "driver" in line.lower():
                        chipset = line.split(":")[1].strip()
                        break
            except Exception as e:
                logger.debug(f"Could not determine chipset from ethtool: {str(e)}")
        
        return chipset
    
    def _check_monitor_mode_support(self) -> bool:
        """
        Check if the adapter supports monitor mode.
        
        Returns:
            True if monitor mode is supported, False otherwise
        """
        # Check if the interface supports monitor mode
        try:
            card = pyw.getcard(self.interface)
            modes = pyw.devmodes(card)
            
            if "monitor" in modes:
                return True
        except Exception as e:
            logger.debug(f"Error checking monitor mode support: {str(e)}")
        
        # If we have a chipset, check if it's known to support monitor mode
        if self.chipset:
            for chipset_id in MONITOR_MODE_CHIPSETS:
                if chipset_id in str(self.chipset).lower():
                    return True
        
        # Try to set monitor mode as a definitive test
        original_mode = self._get_current_mode()
        if self.set_monitor_mode(True):
            # Restore original mode
            if original_mode != "monitor":
                self.set_monitor_mode(False)
            return True
        
        return False
    
    def _check_injection_support(self) -> bool:
        """
        Check if the adapter supports packet injection.
        
        Returns:
            True if packet injection is supported, False otherwise
        """
        # First, check if monitor mode is supported (prerequisite for injection)
        if not self.supports_monitor_mode:
            return False
        
        original_mode = self._get_current_mode()
        supports_injection = False
        
        try:
            # Set to monitor mode if not already
            if original_mode != "monitor":
                self.set_monitor_mode(True)
            
            # Try using the aireplay-ng test command
            try:
                output = subprocess.check_output(
                    ["aireplay-ng", "--test", self.interface],
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=5  # Don't let this run too long
                )
                
                if "Injection is working" in output:
                    supports_injection = True
                
            except (subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
                logger.debug(f"Aireplay-ng test failed: {str(e)}")
            
        except Exception as e:
            logger.debug(f"Error checking injection support: {str(e)}")
        
        finally:
            # Restore original mode
            if original_mode != "monitor":
                self.set_monitor_mode(False)
        
        return supports_injection
    
    def set_monitor_mode(self, enable: bool = True) -> bool:
        """
        Set the interface to monitor mode or back to managed mode.
        
        Args:
            enable: If True, set to monitor mode; if False, set to managed mode
            
        Returns:
            True if successful, False otherwise
        """
        target_mode = "monitor" if enable else "managed"
        current_mode = self._get_current_mode()
        
        if current_mode == target_mode:
            logger.debug(f"Interface {self.interface} is already in {target_mode} mode")
            return True
        
        logger.info(f"Setting interface {self.interface} to {target_mode} mode")
        
        try:
            # Get the Card object for this interface
            card = pyw.getcard(self.interface)
            
            # Turn down the interface
            pyw.ifconfig(card, flags=0)
            
            # Set the mode
            pyw.modeset(card, target_mode)
            
            # Turn up the interface
            pyw.ifconfig(card, flags=1)
            
            # Verify mode change
            new_mode = self._get_current_mode()
            if new_mode != target_mode:
                logger.error(f"Failed to set interface {self.interface} to {target_mode} mode (current mode: {new_mode})")
                return False
            
            logger.debug(f"Successfully set interface {self.interface} to {target_mode} mode")
            return True
        
        except Exception as e:
            logger.error(f"Error setting interface {self.interface} to {target_mode} mode: {str(e)}")
            
            # Fall back to using airmon-ng if pyric fails
            return self._fallback_set_mode(target_mode)
    
    def _fallback_set_mode(self, mode: str) -> bool:
        """
        Fall back to using airmon-ng to set the interface mode.
        
        Args:
            mode: The mode to set ('monitor' or 'managed')
            
        Returns:
            True if successful, False otherwise
        """
        logger.debug(f"Falling back to airmon-ng to set {self.interface} to {mode} mode")
        
        try:
            if mode == "monitor":
                # Check if airmon-ng is available
                result = subprocess.run(["which", "airmon-ng"], capture_output=True, text=True)
                if result.returncode != 0:
                    logger.error("airmon-ng is not installed")
                    return False
                
                # Start monitor mode
                result = subprocess.run(["airmon-ng", "start", self.interface], capture_output=True, text=True)
                
                # Check if a new interface was created (like wlan0mon)
                match = re.search(r"(Created monitor mode interface|monitor mode enabled on) (\w+)", result.stdout)
                if match:
                    new_interface = match.group(2)
                    logger.info(f"Created monitor interface: {new_interface}")
                    self.interface = new_interface
                    return True
            
            elif mode == "managed":
                # Stop monitor mode
                result = subprocess.run(["airmon-ng", "stop", self.interface], capture_output=True, text=True)
                
                # Check if the original interface was restored
                match = re.search(r"(Removed monitor mode interface|monitor mode disabled on) (\w+)", result.stdout)
                if match:
                    new_interface = match.group(2)
                    logger.info(f"Restored managed interface: {new_interface}")
                    self.interface = new_interface
                    return True
            
            # If we get here, the command ran but we couldn't confirm the mode change
            logger.warning(f"Ran airmon-ng but couldn't confirm mode change for {self.interface}")
            return False
        
        except Exception as e:
            logger.error(f"Error using airmon-ng: {str(e)}")
            return False
    
    def get_mac_address(self) -> Optional[str]:
        """
        Get the MAC address of the interface.
        
        Returns:
            MAC address as a string, or None if it couldn't be determined
        """
        try:
            addrs = netifaces.ifaddresses(self.interface)
            if netifaces.AF_LINK in addrs:
                return addrs[netifaces.AF_LINK][0]['addr']
        except Exception as e:
            logger.error(f"Error getting MAC address for {self.interface}: {str(e)}")
        
        return None
    
    def set_channel(self, channel: int) -> bool:
        """
        Set the channel for the wireless interface.
        
        Args:
            channel: Channel number to set
            
        Returns:
            True if successful, False otherwise
        """
        logger.debug(f"Setting channel {channel} for interface {self.interface}")
        
        try:
            card = pyw.getcard(self.interface)
            pyw.chset(card, channel)
            return True
        except Exception as e:
            logger.error(f"Error setting channel {channel} for interface {self.interface}: {str(e)}")
            return False
    
    def find_wireless_interfaces(self) -> List[str]:
        """
        Find available wireless interfaces on the system.
        
        Returns:
            List of available wireless interface names
        """
        wireless_interfaces = []
        
        # Method 1: Use pyric to find wireless interfaces
        try:
            for interface in pyw.winterfaces():
                wireless_interfaces.append(interface)
        except Exception as e:
            logger.debug(f"Error finding wireless interfaces with pyric: {str(e)}")
        
        # If no interfaces were found, try alternative methods
        if not wireless_interfaces:
            # Method 2: Use iwconfig to find wireless interfaces
            try:
                output = subprocess.check_output(["iwconfig"], stderr=subprocess.STDOUT, text=True)
                
                for line in output.splitlines():
                    if "IEEE 802.11" in line:
                        interface = line.split()[0]
                        wireless_interfaces.append(interface)
            except Exception as e:
                logger.debug(f"Error finding wireless interfaces with iwconfig: {str(e)}")
        
        # Method 3: Use iw to find wireless interfaces
        if not wireless_interfaces:
            try:
                output = subprocess.check_output(["iw", "dev"], stderr=subprocess.STDOUT, text=True)
                
                for line in output.splitlines():
                    match = re.search(r"Interface\s+(\w+)", line)
                    if match:
                        interface = match.group(1)
                        wireless_interfaces.append(interface)
            except Exception as e:
                logger.debug(f"Error finding wireless interfaces with iw: {str(e)}")
        
        # Method 4: Check /sys/class/net for wireless interfaces
        if not wireless_interfaces:
            for interface in os.listdir("/sys/class/net"):
                try:
                    if os.path.exists(f"/sys/class/net/{interface}/wireless"):
                        wireless_interfaces.append(interface)
                except Exception:
                    pass
        
        return wireless_interfaces
    
    def get_interface_capabilities(self) -> Dict[str, Any]:
        """
        Get the capabilities of the wireless interface.
        
        Returns:
            Dictionary of capabilities
        """
        capabilities = {
            "interface": self.interface,
            "chipset": self.chipset,
            "mode": self._get_current_mode(),
            "supports_monitor_mode": self.supports_monitor_mode,
            "supports_injection": self.supports_injection,
            "mac_address": self.get_mac_address(),
        }
        
        # Get supported bands and channels
        capabilities["channels"] = self._get_supported_channels()
        
        # Get supported modes
        try:
            card = pyw.getcard(self.interface)
            capabilities["supported_modes"] = pyw.devmodes(card)
        except Exception:
            capabilities["supported_modes"] = []
        
        return capabilities
    
    def _get_supported_channels(self) -> Dict[str, List[int]]:
        """
        Get the supported channels of the wireless interface.
        
        Returns:
            Dictionary of supported bands and their channels
        """
        supported_channels = {
            "2.4GHz": [],
            "5GHz": []
        }
        
        try:
            card = pyw.getcard(self.interface)
            phy = pyw.phyget(card)
            
            # Get the channel information
            for band, channels in pyw.devchs(phy).items():
                # Map frequency to band
                if band == "2GHz":
                    supported_channels["2.4GHz"] = channels
                elif band in ("5GHz", "5.8GHz"):
                    supported_channels["5GHz"].extend(channels)
        except Exception as e:
            logger.debug(f"Error getting supported channels: {str(e)}")
            
            # Fall back to standard channels if we can't get specific ones
            supported_channels["2.4GHz"] = list(range(1, 15))
            supported_channels["5GHz"] = list(range(36, 165, 4))
        
        return supported_channels
    
    def set_mac_address(self, mac_address: str) -> bool:
        """
        Set the MAC address of the interface (MAC spoofing).
        
        Args:
            mac_address: The MAC address to set
            
        Returns:
            True if successful, False otherwise
        """
        logger.debug(f"Setting MAC address {mac_address} for interface {self.interface}")
        
        try:
            # Try using macchanger if available
            try:
                subprocess.run(["which", "macchanger"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # Turn down the interface
                subprocess.run(["ip", "link", "set", "dev", self.interface, "down"], check=True)
                
                # Set the MAC address
                result = subprocess.run(
                    ["macchanger", "--mac", mac_address, self.interface],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                # Turn up the interface
                subprocess.run(["ip", "link", "set", "dev", self.interface, "up"], check=True)
                
                return True
            except subprocess.SubprocessError:
                logger.debug("macchanger failed or not available, trying alternative method")
            
            # Alternative method: ip link
            subprocess.run(["ip", "link", "set", "dev", self.interface, "down"], check=True)
            subprocess.run(["ip", "link", "set", "dev", self.interface, "address", mac_address], check=True)
            subprocess.run(["ip", "link", "set", "dev", self.interface, "up"], check=True)
            
            # Verify the change
            new_mac = self.get_mac_address()
            if new_mac and new_mac.lower() == mac_address.lower():
                logger.info(f"Successfully set MAC address to {mac_address}")
                return True
            else:
                logger.warning(f"Failed to set MAC address to {mac_address}")
                return False
                
        except Exception as e:
            logger.error(f"Error setting MAC address: {str(e)}")
            return False
    
    def __del__(self):
        """
        Restore the original mode when the object is destroyed.
        
        This ensures that the interface is left in its original state.
        """
        if hasattr(self, 'original_mode') and self.original_mode != "unknown":
            current_mode = self._get_current_mode()
            if current_mode != self.original_mode:
                logger.debug(f"Restoring interface {self.interface} to original mode: {self.original_mode}")
                self.set_monitor_mode(self.original_mode == "monitor") 