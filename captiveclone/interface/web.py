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

from flask import Flask, request, render_template, jsonify, send_from_directory, redirect, url_for, flash
from werkzeug.utils import secure_filename

from captiveclone.core.portal_analyzer import PortalAnalyzer
from captiveclone.core.portal_cloner import PortalCloner
from captiveclone.core.scanner import NetworkScanner
from captiveclone.core.models import WirelessNetwork, CaptivePortal
from captiveclone.utils.config import Config
from captiveclone.utils.exceptions import CaptivePortalError, CloneGenerationError

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
        
        # Create necessary directories
        self.templates_dir = Path(__file__).parent.parent / "templates"
        self.static_dir = Path(__file__).parent.parent / "static"
        self.portal_clones_dir = Path(config.get_output_dir() or "portal_clones")
        
        os.makedirs(self.templates_dir, exist_ok=True)
        os.makedirs(self.static_dir, exist_ok=True)
        os.makedirs(self.portal_clones_dir, exist_ok=True)
        
        # Initialize components
        self.analyzer = PortalAnalyzer()
        self.cloner = PortalCloner()
        self.scanner = None  # Initialize when needed
        
        # Store for active portals and networks
        self.networks: List[WirelessNetwork] = []
        self.portals: Dict[str, CaptivePortal] = {}
        self.clones: Dict[str, str] = {}  # clone_name -> path
        
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
        
        # Error handlers
        self.app.errorhandler(404)(self.page_not_found)
        self.app.errorhandler(500)(self.server_error)
        
        # Configure secret key for flash messages
        self.app.secret_key = os.urandom(24)
    
    def start(self) -> None:
        """Start the web interface."""
        logger.info(f"Starting web interface on {self.host}:{self.port}")
        self.app.run(host=self.host, port=self.port, debug=self.config.get_debug_mode())
    
    def index(self):
        """Home page route."""
        return render_template("index.html", 
                              networks=self.networks, 
                              portals=self.portals, 
                              clones=self.clones)
    
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