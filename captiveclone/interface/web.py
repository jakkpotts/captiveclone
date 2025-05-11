"""
Web interface for CaptiveClone.

This module provides a Flask-based web interface for interacting with
CaptiveClone, managing portal analysis, and clone generation.
"""

import os
import json
import logging
from typing import Dict, List, Optional
from pathlib import Path
import threading
import time

from flask import Flask, request, render_template, jsonify, send_from_directory, redirect, url_for, flash
from flask_socketio import SocketIO
from werkzeug.utils import secure_filename

from captiveclone.core.portal_analyzer import PortalAnalyzer
from captiveclone.core.portal_cloner import PortalCloner
from captiveclone.core.scanner import NetworkScanner
from captiveclone.core.models import WirelessNetwork, CaptivePortal
from captiveclone.core.access_point import AccessPoint
from captiveclone.core.deauthenticator import Deauthenticator
from captiveclone.core.credential_capture import CredentialCapture, CaptureEndpoint
from captiveclone.utils.config import Config
from captiveclone.utils.exceptions import CaptivePortalError, CloneGenerationError, APError, DeauthError, CaptureError

logger = logging.getLogger(__name__)

class WebInterface:
    """Flask-based web interface for CaptiveClone."""
    
    def __init__(self, config: Config, host: str = "127.0.0.1", port: int = 5000):
        """
        Initialize the web interface.
        
        Args:
            config: Configuration object
            host: Host address to bind to
            port: Port to listen on
        """
        self.config = config
        self.host = host
        self.port = port
        self.app = Flask(__name__, 
                         template_folder=str(Path(__file__).parent.parent / "templates"),
                         static_folder=str(Path(__file__).parent.parent / "static"))
        
        # Initialize Socket.IO for real-time updates
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        
        # Create necessary directories
        self.templates_dir = Path(__file__).parent.parent / "templates"
        self.static_dir = Path(__file__).parent.parent / "static"
        self.portal_clones_dir = Path(config.get_output_dir() or "portal_clones")
        self.credentials_dir = Path(config.get("capture", {}).get("output_dir", "captured_credentials"))
        
        os.makedirs(self.templates_dir, exist_ok=True)
        os.makedirs(self.static_dir, exist_ok=True)
        os.makedirs(self.portal_clones_dir, exist_ok=True)
        os.makedirs(self.credentials_dir, exist_ok=True)
        
        # Initialize components
        self.analyzer = PortalAnalyzer()
        self.cloner = PortalCloner()
        self.scanner = None  # Initialize when needed
        self.ap = None  # Access point instance
        self.deauth = None  # Deauthenticator instance
        self.credentials = CredentialCapture(str(self.credentials_dir))
        self.capture_endpoint = None  # Initialize when needed
        
        # Store for active portals and networks
        self.networks: List[WirelessNetwork] = []
        self.portals: Dict[str, CaptivePortal] = {}
        self.clones: Dict[str, str] = {}  # clone_name -> path
        
        # Status trackers
        self.ap_running = False
        self.deauth_running = False
        self.capture_running = False
        
        # Register credential observer for real-time updates
        self.credentials.register_observer(self._credential_callback)
        
        # Configure Flask app
        self._configure_app()
    
    def _configure_app(self) -> None:
        """Configure the Flask application and routes."""
        # Register routes
        self.app.route("/")(self.index)
        self.app.route("/scan", methods=["GET", "POST"])(self.scan)
        self.app.route("/analyze", methods=["GET", "POST"])(self.analyze)
        self.app.route("/clone", methods=["GET", "POST"])(self.clone)
        self.app.route("/portal/<clone_name>")(self.portal)
        self.app.route("/portal-assets/<clone_name>/<path:filename>")(self.portal_assets)
        self.app.route("/download/<clone_name>")(self.download)
        
        # New routes for Phase 3
        self.app.route("/ap", methods=["GET", "POST"])(self.access_point)
        self.app.route("/ap/start", methods=["POST"])(self.start_ap)
        self.app.route("/ap/stop", methods=["POST"])(self.stop_ap)
        self.app.route("/deauth", methods=["GET", "POST"])(self.deauthenticate)
        self.app.route("/deauth/start", methods=["POST"])(self.start_deauth)
        self.app.route("/deauth/stop", methods=["POST"])(self.stop_deauth)
        self.app.route("/dashboard")(self.dashboard)
        self.app.route("/credentials")(self.view_credentials)
        self.app.route("/credentials/export", methods=["POST"])(self.export_credentials)
        
        # Error handlers
        self.app.errorhandler(404)(self.page_not_found)
        self.app.errorhandler(500)(self.server_error)
        
        # Configure secret key for flash messages
        self.app.secret_key = os.urandom(24)
        
        # SocketIO event handlers for real-time updates
        self.socketio.on_event('connect', self._socket_connect)
        self.socketio.on_event('disconnect', self._socket_disconnect)
    
    def start(self) -> None:
        """Start the web interface."""
        logger.info(f"Starting web interface on {self.host}:{self.port}")
        self.socketio.run(self.app, host=self.host, port=self.port, debug=self.config.get_debug_mode())
    
    def index(self):
        """Home page route."""
        return render_template("index.html", 
                              networks=self.networks, 
                              portals=self.portals, 
                              clones=self.clones,
                              ap_running=self.ap_running,
                              deauth_running=self.deauth_running,
                              capture_running=self.capture_running)
    
    def scan(self):
        """Scan for networks with captive portals."""
        if request.method == "POST":
            interface = request.form.get("interface", None)
            timeout = int(request.form.get("timeout", 60))
            
            try:
                self.scanner = NetworkScanner(interface=interface, timeout=timeout)
                self.networks = self.scanner.scan()
                flash(f"Scan complete. Found {len(self.networks)} networks.", "success")
            except Exception as e:
                logger.error(f"Error scanning networks: {str(e)}")
                flash(f"Error scanning networks: {str(e)}", "error")
            
            return redirect(url_for("index"))
        
        # GET request
        interfaces = self._get_interfaces()
        return render_template("scan.html", interfaces=interfaces)
    
    def analyze(self):
        """Analyze a captive portal."""
        if request.method == "POST":
            portal_url = request.form.get("portal_url", "")
            if not portal_url:
                flash("Please provide a portal URL.", "error")
                return redirect(url_for("analyze"))
            
            try:
                portal = self.analyzer.analyze_portal(portal_url)
                self.portals[portal_url] = portal
                flash(f"Portal analysis complete for {portal_url}.", "success")
                return redirect(url_for("index"))
            except CaptivePortalError as e:
                logger.error(f"Error analyzing portal: {str(e)}")
                flash(f"Error analyzing portal: {str(e)}", "error")
            
            return redirect(url_for("analyze"))
        
        # GET request
        return render_template("analyze.html")
    
    def clone(self):
        """Clone a captive portal."""
        if request.method == "POST":
            portal_url = request.form.get("portal_url", "")
            clone_name = request.form.get("clone_name", "")
            
            if not portal_url:
                flash("Please provide a portal URL.", "error")
                return redirect(url_for("clone"))
            
            try:
                clone_dir = self.cloner.clone_portal(portal_url, output_name=clone_name)
                clone_name = os.path.basename(clone_dir)
                self.clones[clone_name] = clone_dir
                flash(f"Portal clone generated at {clone_dir}.", "success")
                return redirect(url_for("index"))
            except CloneGenerationError as e:
                logger.error(f"Error cloning portal: {str(e)}")
                flash(f"Error cloning portal: {str(e)}", "error")
            
            return redirect(url_for("clone"))
        
        # GET request - populate form with existing portals
        return render_template("clone.html", portals=self.portals)
    
    def portal(self, clone_name):
        """View a cloned portal."""
        if clone_name not in self.clones:
            flash(f"Portal clone not found: {clone_name}", "error")
            return redirect(url_for("index"))
        
        clone_dir = self.clones[clone_name]
        index_path = os.path.join(clone_dir, "index.html")
        
        if not os.path.exists(index_path):
            flash(f"Portal index not found: {index_path}", "error")
            return redirect(url_for("index"))
        
        with open(index_path, 'r') as f:
            html_content = f.read()
        
        return render_template("portal_view.html", 
                              clone_name=clone_name, 
                              html_content=html_content)
    
    def portal_assets(self, clone_name, filename):
        """Serve portal assets."""
        if clone_name not in self.clones:
            return "Portal clone not found", 404
        
        clone_dir = self.clones[clone_name]
        return send_from_directory(clone_dir, filename)
    
    def download(self, clone_name):
        """Download a cloned portal."""
        if clone_name not in self.clones:
            flash(f"Portal clone not found: {clone_name}", "error")
            return redirect(url_for("index"))
        
        # TODO: Implement zip creation and download
        flash("Download functionality not implemented yet.", "warning")
        return redirect(url_for("index"))
    
    def access_point(self):
        """Access point management page."""
        interfaces = self._get_interfaces()
        return render_template("access_point.html", 
                              interfaces=interfaces, 
                              networks=self.networks,
                              ap_running=self.ap_running,
                              clones=self.clones)
    
    def start_ap(self):
        """Start the access point."""
        if self.ap_running:
            flash("Access point is already running.", "warning")
            return redirect(url_for("access_point"))
        
        interface = request.form.get("interface")
        network_bssid = request.form.get("network_bssid")
        clone_name = request.form.get("clone_name")
        hidden = request.form.get("hidden") == "on"
        spoof_mac = request.form.get("spoof_mac") == "on"
        
        # Validate input
        if not interface or not network_bssid or not clone_name:
            flash("Please provide all required fields.", "error")
            return redirect(url_for("access_point"))
        
        # Find the target network
        target_network = None
        for network in self.networks:
            if network.bssid == network_bssid:
                target_network = network
                break
        
        if not target_network:
            flash("Target network not found.", "error")
            return redirect(url_for("access_point"))
        
        # Get clone directory
        if clone_name not in self.clones:
            flash("Portal clone not found.", "error")
            return redirect(url_for("access_point"))
        
        clone_dir = self.clones[clone_name]
        
        try:
            # Initialize access point
            self.ap = AccessPoint(interface, clone_dir)
            
            # Set MAC address if spoofing is enabled
            if spoof_mac and target_network.bssid:
                self.ap.set_mac_address(target_network.bssid)
            
            # Start access point
            self.ap.start(target_network, hidden)
            self.ap_running = True
            
            # Start credential capture endpoint if not already running
            if not self.capture_running:
                self._start_capture_endpoint()
            
            flash(f"Access point '{target_network.ssid}' started on {interface}.", "success")
        except APError as e:
            logger.error(f"Error starting access point: {str(e)}")
            flash(f"Error starting access point: {str(e)}", "error")
        
        return redirect(url_for("dashboard"))
    
    def stop_ap(self):
        """Stop the access point."""
        if not self.ap_running or not self.ap:
            flash("No access point is running.", "warning")
            return redirect(url_for("access_point"))
        
        try:
            self.ap.stop()
            self.ap_running = False
            self.ap = None
            flash("Access point stopped.", "success")
        except APError as e:
            logger.error(f"Error stopping access point: {str(e)}")
            flash(f"Error stopping access point: {str(e)}", "error")
        
        return redirect(url_for("access_point"))
    
    def deauthenticate(self):
        """Deauthentication management page."""
        interfaces = self._get_interfaces()
        return render_template("deauthenticate.html", 
                              interfaces=interfaces, 
                              networks=self.networks,
                              deauth_running=self.deauth_running)
    
    def start_deauth(self):
        """Start the deauthenticator."""
        if self.deauth_running:
            flash("Deauthenticator is already running.", "warning")
            return redirect(url_for("deauthenticate"))
        
        interface = request.form.get("interface")
        network_bssid = request.form.get("network_bssid")
        target_all = request.form.get("target_all") == "on"
        
        # Validate input
        if not interface or not network_bssid:
            flash("Please provide all required fields.", "error")
            return redirect(url_for("deauthenticate"))
        
        # Find the target network
        target_network = None
        for network in self.networks:
            if network.bssid == network_bssid:
                target_network = network
                break
        
        if not target_network:
            flash("Target network not found.", "error")
            return redirect(url_for("deauthenticate"))
        
        try:
            # Initialize deauthenticator
            self.deauth = Deauthenticator(interface)
            
            # Set target network
            self.deauth.set_target_network(target_network)
            
            # Start deauthenticator
            self.deauth.start(target_all_clients=target_all)
            self.deauth_running = True
            
            # Start a background thread to update client list
            threading.Thread(target=self._update_client_list, daemon=True).start()
            
            flash(f"Deauthenticator started targeting '{target_network.ssid}'.", "success")
        except DeauthError as e:
            logger.error(f"Error starting deauthenticator: {str(e)}")
            flash(f"Error starting deauthenticator: {str(e)}", "error")
        
        return redirect(url_for("dashboard"))
    
    def stop_deauth(self):
        """Stop the deauthenticator."""
        if not self.deauth_running or not self.deauth:
            flash("No deauthenticator is running.", "warning")
            return redirect(url_for("deauthenticate"))
        
        try:
            self.deauth.stop()
            self.deauth_running = False
            self.deauth = None
            flash("Deauthenticator stopped.", "success")
        except DeauthError as e:
            logger.error(f"Error stopping deauthenticator: {str(e)}")
            flash(f"Error stopping deauthenticator: {str(e)}", "error")
        
        return redirect(url_for("deauthenticate"))
    
    def dashboard(self):
        """Dashboard for monitoring connected clients and captures."""
        clients = {}
        credentials = []
        target_network = None
        
        if self.deauth_running and self.deauth:
            clients = self.deauth.get_active_clients()
            target_network = self.deauth.target_network
        
        credentials = self.credentials.get_recent_credentials(10)
        
        return render_template("dashboard.html",
                              clients=clients,
                              credentials=credentials,
                              target_network=target_network,
                              ap_running=self.ap_running,
                              deauth_running=self.deauth_running,
                              capture_running=self.capture_running)
    
    def view_credentials(self):
        """View captured credentials."""
        credentials = self.credentials.get_all_credentials()
        return render_template("credentials.html", credentials=credentials)
    
    def export_credentials(self):
        """Export credentials to CSV."""
        try:
            csv_file = self.credentials.export_csv()
            flash(f"Credentials exported to {csv_file}.", "success")
        except CaptureError as e:
            logger.error(f"Error exporting credentials: {str(e)}")
            flash(f"Error exporting credentials: {str(e)}", "error")
        
        return redirect(url_for("view_credentials"))
    
    def page_not_found(self, e):
        """404 error handler."""
        return render_template("404.html"), 404
    
    def server_error(self, e):
        """500 error handler."""
        return render_template("500.html"), 500
    
    def _get_interfaces(self) -> List[str]:
        """Get a list of available wireless interfaces."""
        try:
            # This would use the hardware abstraction layer in a real implementation
            # For now, we'll just return a placeholder
            return ["wlan0", "wlan1"]
        except Exception as e:
            logger.error(f"Error getting interfaces: {str(e)}")
            return [] 
    
    def _credential_callback(self, credential):
        """Callback for new captured credentials."""
        # Emit to all connected clients
        self.socketio.emit('new_credential', credential)
    
    def _update_client_list(self):
        """Background thread to update client list periodically."""
        while self.deauth_running and self.deauth:
            clients = self.deauth.get_active_clients()
            self.socketio.emit('client_update', clients)
            time.sleep(5)  # Update every 5 seconds
    
    def _start_capture_endpoint(self):
        """Start the credential capture endpoint."""
        if self.capture_running:
            return
        
        # Default port from config or use 8080
        port = self.config.get("capture", {}).get("port", 8080)
        
        try:
            self.capture_endpoint = CaptureEndpoint(self.credentials, port)
            self.capture_endpoint.start()
            self.capture_running = True
            logger.info(f"Started credential capture endpoint on port {port}")
        except CaptureError as e:
            logger.error(f"Failed to start capture endpoint: {str(e)}")
            flash(f"Failed to start capture endpoint: {str(e)}", "error")
    
    def _socket_connect(self):
        """Handle SocketIO connection."""
        logger.debug("Client connected to SocketIO")
    
    def _socket_disconnect(self):
        """Handle SocketIO disconnection."""
        logger.debug("Client disconnected from SocketIO") 