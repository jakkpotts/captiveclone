"""
Network Scanner Module for CaptiveClone.

This module is responsible for scanning wireless networks and detecting captive portals.
"""

import logging
import time
from typing import List, Dict, Optional, Any, Tuple
import threading
import re
import socket
import urllib.parse

from scapy.all import Dot11, Dot11Beacon, Dot11Elt, RadioTap, sniff
import netifaces
import requests

from captiveclone.utils.exceptions import InterfaceError
from captiveclone.core.models import WirelessNetwork, CaptivePortal
from captiveclone.hardware.adapter import WirelessAdapter
from captiveclone.database.models import Network as DBNetwork
from captiveclone.database.models import CaptivePortal as DBCaptivePortal
from captiveclone.database.models import ScanSession
from sqlalchemy.orm import Session as DBSession

logger = logging.getLogger(__name__)

# Constants for captive portal detection
CAPTIVE_PORTAL_CHECK_URLS = [
    "http://connectivitycheck.gstatic.com/generate_204",
    "http://www.apple.com/library/test/success.html",
    "http://detectportal.firefox.com/success.txt",
    "http://network-test.debian.org/nm",
]

CONNECTIVITY_CHECK_TIMEOUT = 5  # seconds

class NetworkScanner:
    """Scans for wireless networks and detects captive portals."""
    
    def __init__(self, interface: Optional[str] = None, timeout: int = 60, db_session: Optional[DBSession] = None):
        """
        Initialize the network scanner.
        
        Args:
            interface: Name of the wireless interface to use (e.g., 'wlan0')
            timeout: Scan timeout in seconds
            db_session: Database session for storing results
        """
        self.interface = interface
        self.timeout = timeout
        self.networks = {}  # type: Dict[str, WirelessNetwork]
        self._stop_sniffing = threading.Event()
        self.adapter = None
        self.db_session = db_session
        self.scan_session = None
        
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
    
    def set_db_session(self, db_session: DBSession) -> None:
        """
        Set the database session for storing results.
        
        Args:
            db_session: SQLAlchemy session object
        """
        self.db_session = db_session
    
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
        
        # Create scan session if db_session is available
        if self.db_session:
            self.scan_session = ScanSession(interface=self.interface)
            self.db_session.add(self.scan_session)
            self.db_session.commit()
        
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
            
            # Update scan session if db_session is available
            if self.db_session and self.scan_session:
                self.scan_session.end_time = time.time()
                self.scan_session.networks_found = len(self.networks)
                self.scan_session.captive_portals_found = sum(1 for n in self.networks.values() if n.has_captive_portal)
                self.db_session.commit()
            
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
        
        # Store in database if db_session is available
        if self.db_session:
            self._store_network_in_db(network)
    
    def _store_network_in_db(self, network: WirelessNetwork) -> None:
        """
        Store a network in the database.
        
        Args:
            network: The WirelessNetwork object to store
        """
        # Check if network already exists in the database
        existing_network = self.db_session.query(DBNetwork).filter_by(bssid=network.bssid).first()
        
        if existing_network:
            # Update existing network
            existing_network.last_seen = time.time()
            existing_network.signal_strength = network.signal_strength
            existing_network.channel = network.channel
            existing_network.encryption = network.encryption
            existing_network.has_captive_portal = network.has_captive_portal
        else:
            # Create new network
            db_network = DBNetwork(
                ssid=network.ssid,
                bssid=network.bssid,
                channel=network.channel,
                encryption=network.encryption,
                signal_strength=network.signal_strength,
                has_captive_portal=network.has_captive_portal
            )
            self.db_session.add(db_network)
        
        self.db_session.commit()
    
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
            
            # Try to connect to the network
            if not self._connect_to_network(network):
                logger.warning(f"Could not connect to network: {network.ssid}")
                continue
            
            # Detect captive portal
            portal_info = self._check_for_captive_portal()
            if portal_info:
                network.has_captive_portal = True
                portal_url, is_auth, redirect_url = portal_info
                
                logger.info(f"Detected captive portal on network: {network.ssid}")
                logger.debug(f"Portal URL: {portal_url}, Requires Auth: {is_auth}, Redirect URL: {redirect_url}")
                
                # Create CaptivePortal object
                portal = CaptivePortal(
                    network=network,
                    requires_authentication=is_auth,
                    login_url=portal_url,
                    redirect_url=redirect_url
                )
                
                # Store in database if db_session is available
                if self.db_session:
                    self._store_portal_in_db(network, portal)
            
            # Disconnect from the network
            self._disconnect_from_network()
    
    def _connect_to_network(self, network: WirelessNetwork) -> bool:
        """
        Connect to a wireless network.
        
        Args:
            network: The network to connect to
            
        Returns:
            True if connection successful, False otherwise
        """
        # This is a placeholder for actual connection logic
        # In a real implementation, this would use wpa_supplicant or a similar tool
        logger.debug(f"Attempting to connect to network: {network.ssid}")
        
        try:
            # Get current connection info to check if already connected
            # This is simplified for now
            if self._is_connected_to_network(network.ssid):
                logger.debug(f"Already connected to network: {network.ssid}")
                return True
            
            # Run nmcli command to connect to open network
            import subprocess
            
            # Disconnect from any current network first
            subprocess.run(["nmcli", "device", "disconnect", self.interface], 
                           capture_output=True, text=True, check=False)
            
            # Connect to the open network
            result = subprocess.run(
                ["nmcli", "device", "wifi", "connect", network.ssid, "ifname", self.interface],
                capture_output=True, text=True, check=False
            )
            
            if result.returncode == 0:
                logger.info(f"Connected to network: {network.ssid}")
                return True
            else:
                logger.warning(f"Failed to connect to network: {network.ssid}")
                logger.debug(f"nmcli output: {result.stdout}, Error: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error connecting to network {network.ssid}: {str(e)}")
            return False
    
    def _is_connected_to_network(self, ssid: str) -> bool:
        """
        Check if currently connected to a specific network.
        
        Args:
            ssid: The SSID to check for
            
        Returns:
            True if connected to the specified network, False otherwise
        """
        try:
            import subprocess
            result = subprocess.run(["nmcli", "-t", "-f", "active,ssid", "device", "wifi"], 
                                  capture_output=True, text=True, check=True)
            
            for line in result.stdout.splitlines():
                if ':' not in line:
                    continue
                active, line_ssid = line.split(':', 1)
                if active == 'yes' and line_ssid == ssid:
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking network connection: {str(e)}")
            return False
    
    def _disconnect_from_network(self) -> bool:
        """
        Disconnect from the current network.
        
        Returns:
            True if disconnection successful, False otherwise
        """
        try:
            import subprocess
            result = subprocess.run(["nmcli", "device", "disconnect", self.interface], 
                                  capture_output=True, text=True, check=False)
            
            if result.returncode == 0:
                logger.debug("Disconnected from network")
                return True
            else:
                logger.warning(f"Failed to disconnect: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error disconnecting from network: {str(e)}")
            return False
    
    def _check_for_captive_portal(self) -> Optional[Tuple[str, bool, Optional[str]]]:
        """
        Check if the current network has a captive portal by trying to access known URLs.
        
        Returns:
            Tuple of (portal_url, requires_authentication, redirect_url) if a portal is detected,
            None otherwise
        """
        logger.debug("Checking for captive portal")
        
        # Check internet connectivity first (give DHCP a moment to initialize)
        time.sleep(2)
        
        # Check if we can resolve domain names
        if not self._can_resolve_dns():
            logger.debug("DNS resolution failed, likely captive portal or no connectivity")
            return None
        
        # Try accessing known URLs that should return specific responses
        session = requests.Session()
        
        # Don't follow redirects automatically
        session.max_redirects = 0
        
        for url in CAPTIVE_PORTAL_CHECK_URLS:
            try:
                response = session.get(url, timeout=CONNECTIVITY_CHECK_TIMEOUT, allow_redirects=False)
                
                # If we get a redirect, it's likely a captive portal
                if response.status_code in (301, 302, 303, 307, 308):
                    redirect_url = response.headers.get('Location')
                    logger.debug(f"Detected redirect to: {redirect_url}")
                    
                    # Analyze the portal URL to determine if it requires authentication
                    requires_auth = self._portal_requires_authentication(redirect_url)
                    
                    return (redirect_url, requires_auth, None)
                
                # If we get an unexpected response code or content, might be captive portal
                if (url.endswith('/generate_204') and response.status_code != 204) or \
                   (url.endswith('/success.html') and not 'Success' in response.text) or \
                   (url.endswith('/success.txt') and not 'success' in response.text.lower()):
                    logger.debug(f"Unexpected response from {url}: {response.status_code}")
                    return (url, False, None)
                
            except requests.exceptions.RequestException as e:
                logger.debug(f"Request to {url} failed: {str(e)}")
                continue
        
        logger.debug("No captive portal detected")
        return None
    
    def _can_resolve_dns(self) -> bool:
        """
        Check if DNS resolution is working.
        
        Returns:
            True if DNS resolution is working, False otherwise
        """
        try:
            socket.gethostbyname('www.google.com')
            return True
        except socket.error:
            return False
    
    def _portal_requires_authentication(self, url: str) -> bool:
        """
        Determine if a captive portal likely requires authentication.
        
        Args:
            url: The URL of the captive portal
            
        Returns:
            True if the portal likely requires authentication, False otherwise
        """
        try:
            response = requests.get(url, timeout=CONNECTIVITY_CHECK_TIMEOUT)
            
            # Check for common login form elements
            auth_indicators = [
                'login', 'password', 'username', 'email', 'signin', 'credentials',
                'authenticate', 'input type="password"', 'form'
            ]
            
            content_lower = response.text.lower()
            
            for indicator in auth_indicators:
                if indicator in content_lower:
                    return True
            
            return False
            
        except Exception:
            # If we can't determine, assume it might require auth
            return True
    
    def _store_portal_in_db(self, network: WirelessNetwork, portal: CaptivePortal) -> None:
        """
        Store a captive portal in the database.
        
        Args:
            network: The associated WirelessNetwork object
            portal: The CaptivePortal object to store
        """
        # Find the corresponding network in the DB
        db_network = self.db_session.query(DBNetwork).filter_by(bssid=network.bssid).first()
        
        if not db_network:
            logger.warning(f"Network {network.ssid} not found in database for portal storage")
            return
        
        # Update network with portal information
        db_network.has_captive_portal = True
        
        # Check if portal already exists
        existing_portal = self.db_session.query(DBCaptivePortal).filter_by(network_id=db_network.id).first()
        
        if existing_portal:
            # Update existing portal
            existing_portal.login_url = portal.login_url
            existing_portal.redirect_url = portal.redirect_url
            existing_portal.requires_authentication = portal.requires_authentication
            existing_portal.last_seen = time.time()
        else:
            # Create new portal
            db_portal = DBCaptivePortal(
                network_id=db_network.id,
                login_url=portal.login_url,
                redirect_url=portal.redirect_url,
                requires_authentication=portal.requires_authentication
            )
            self.db_session.add(db_portal)
        
        self.db_session.commit()
    
    def _find_wireless_interfaces(self) -> List[str]:
        """
        Find available wireless interfaces.
        
        Returns:
            List of available wireless interface names
        """
        return self.adapter.find_wireless_interfaces() 