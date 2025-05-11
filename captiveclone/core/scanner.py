"""
Network Scanner Module for CaptiveClone.

This module is responsible for scanning wireless networks and detecting captive portals.
"""

import logging
import time
from typing import List, Dict, Optional, Any
import threading

from scapy.all import Dot11, Dot11Beacon, Dot11Elt, RadioTap, sniff
import netifaces
import requests

from captiveclone.utils.exceptions import InterfaceError
from captiveclone.core.models import WirelessNetwork
from captiveclone.hardware.adapter import WirelessAdapter

logger = logging.getLogger(__name__)

class NetworkScanner:
    """Scans for wireless networks and detects captive portals."""
    
    def __init__(self, interface: Optional[str] = None, timeout: int = 60):
        """
        Initialize the network scanner.
        
        Args:
            interface: Name of the wireless interface to use (e.g., 'wlan0')
            timeout: Scan timeout in seconds
        """
        self.interface = interface
        self.timeout = timeout
        self.networks = {}  # type: Dict[str, WirelessNetwork]
        self._stop_sniffing = threading.Event()
        self.adapter = None
        
        if interface:
            self.set_interface(interface)
    
    def set_interface(self, interface: str) -> None:
        """
        Set the wireless interface to use for scanning.
        
        Args:
            interface: Name of the wireless interface
            
        Raises:
            InterfaceError: If the interface is not valid or doesn't exist
        """
        if interface not in netifaces.interfaces():
            raise InterfaceError(f"Interface {interface} does not exist")
        
        self.interface = interface
        self.adapter = WirelessAdapter(interface)
        
        logger.info(f"Using interface {interface} for scanning")
    
    def scan(self) -> List[WirelessNetwork]:
        """
        Scan for wireless networks.
        
        Returns:
            List of discovered wireless networks
        """
        if not self.interface:
            available_interfaces = self._find_wireless_interfaces()
            if not available_interfaces:
                raise InterfaceError("No wireless interfaces found")
            
            self.set_interface(available_interfaces[0])
        
        logger.info(f"Starting network scan on interface {self.interface}")
        
        # Put interface in monitor mode
        self.adapter.set_monitor_mode(True)
        
        try:
            # Start sniffing
            self._stop_sniffing.clear()
            logger.debug("Starting packet capture")
            
            sniff_thread = threading.Thread(
                target=sniff,
                kwargs={
                    'iface': self.interface,
                    'prn': self._process_packet,
                    'stop_filter': lambda _: self._stop_sniffing.is_set(),
                    'store': False
                }
            )
            
            sniff_thread.start()
            
            # Wait for timeout
            time.sleep(self.timeout)
            
            # Stop sniffing
            self._stop_sniffing.set()
            sniff_thread.join()
            
            logger.info(f"Scan completed. Found {len(self.networks)} networks")
            
            # Check for captive portals
            self._detect_captive_portals()
            
            return list(self.networks.values())
        
        finally:
            # Restore interface to managed mode
            self.adapter.set_monitor_mode(False)
    
    def _process_packet(self, packet) -> None:
        """
        Process a captured packet.
        
        Args:
            packet: Scapy packet object
        """
        if not packet.haslayer(Dot11Beacon):
            return
        
        # Extract the MAC address of the network
        bssid = packet[Dot11].addr2
        if bssid in self.networks:
            return
        
        # Extract network details
        ssid = None
        channel = None
        encryption = False
        
        # Extract SSID
        if packet.haslayer(Dot11Elt) and packet[Dot11Elt].ID == 0:
            ssid = packet[Dot11Elt].info.decode(errors='replace')
            
        # Extract channel
        if packet.haslayer(Dot11Elt) and packet[Dot11Elt].ID == 3:
            channel = int(packet[Dot11Elt].info[0])
        
        # Check for encryption
        capability = packet[Dot11Beacon].cap
        if capability.privacy:
            encryption = True
        
        if not ssid:
            return
        
        # Store network
        network = WirelessNetwork(
            ssid=ssid,
            bssid=bssid,
            channel=channel,
            encryption=encryption,
            signal_strength=self._get_signal_strength(packet),
            has_captive_portal=False  # Will be determined later
        )
        
        self.networks[bssid] = network
        logger.debug(f"Found network: {ssid} (BSSID: {bssid}, Channel: {channel})")
    
    def _get_signal_strength(self, packet) -> Optional[int]:
        """
        Extract the signal strength from a packet.
        
        Args:
            packet: Scapy packet object
            
        Returns:
            Signal strength in dBm, or None if not available
        """
        if packet.haslayer(RadioTap):
            # Try to extract the signal strength from the RadioTap header
            try:
                return -(256 - packet[RadioTap].dBm_AntSignal)
            except:
                pass
        return None
    
    def _detect_captive_portals(self) -> None:
        """
        Detect which networks have captive portals.
        
        This method attempts to connect to open networks and check for captive portals.
        """
        # Restore interface to managed mode for connecting to networks
        self.adapter.set_monitor_mode(False)
        
        for bssid, network in list(self.networks.items()):
            if network.encryption:
                logger.debug(f"Skipping captive portal detection for encrypted network: {network.ssid}")
                continue
            
            logger.info(f"Checking for captive portal on network: {network.ssid}")
            
            # Connect to the network (would use the adapter for this)
            # For now, just a placeholder implementation that checks if a network might have a portal
            
            if self._is_captive_portal():
                network.has_captive_portal = True
                logger.info(f"Detected captive portal on network: {network.ssid}")
    
    def _is_captive_portal(self) -> bool:
        """
        Check if the current network has a captive portal.
        
        Returns:
            True if a captive portal is detected, False otherwise
        """
        # This is a simplified implementation
        # In a real implementation, we would:
        # 1. Connect to the network
        # 2. Try to access a known URL (e.g., captive.apple.com/hotspot-detect.html)
        # 3. Check if the response is redirected or modified
        
        # For now, return a placeholder result (randomly detect ~30% of networks as having portals)
        # This will be implemented properly in the future
        import random
        return random.random() < 0.3
    
    def _find_wireless_interfaces(self) -> List[str]:
        """
        Find available wireless interfaces.
        
        Returns:
            List of available wireless interface names
        """
        # This is a simplified implementation
        # In a real implementation, we would check if the interfaces are wireless
        wireless_interfaces = []
        
        for interface in netifaces.interfaces():
            # Simple heuristic: wireless interfaces often start with 'w'
            if interface.startswith('w'):
                wireless_interfaces.append(interface)
        
        return wireless_interfaces 