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

from captiveclone.utils.exceptions import InterfaceError

logger = logging.getLogger(__name__)


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
        
        logger.debug(f"Initialized adapter for interface {interface} (current mode: {self.original_mode})")
    
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