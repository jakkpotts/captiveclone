"""
Locust load testing script for CaptiveClone API endpoints.

This script tests the performance of the CaptiveClone API under load.
To run: locust -f tests/performance/load_test.py --host=http://localhost:5000
"""

import json
import random
import time
import uuid
from typing import Dict, Any, List

from locust import HttpUser, task, between, tag


# API key for authentication
API_KEY = "test-api-key"  # Set this to match your test environment


class CaptiveCloneAPI:
    """Client for the CaptiveClone API."""
    
    def __init__(self, client):
        """
        Initialize the client.
        
        Args:
            client: Locust HTTP client
        """
        self.client = client
        self.headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
    
    def get_version(self):
        """Get API version."""
        return self.client.get("/api/version")
    
    def get_networks(self, has_captive_portal=None):
        """
        Get networks.
        
        Args:
            has_captive_portal: Filter by captive portal presence
        """
        params = {}
        if has_captive_portal is not None:
            params["has_captive_portal"] = str(has_captive_portal).lower()
        
        return self.client.get("/api/networks", headers=self.headers, params=params)
    
    def get_network(self, network_id):
        """
        Get a network by ID.
        
        Args:
            network_id: Network ID
        """
        return self.client.get(f"/api/networks/{network_id}", headers=self.headers)
    
    def start_scan(self, interface="wlan0"):
        """
        Start a network scan.
        
        Args:
            interface: Wireless interface
        """
        payload = {"interface": interface}
        return self.client.post("/api/scan", headers=self.headers, json=payload)
    
    def get_workflow_state(self):
        """Get workflow state."""
        return self.client.get("/api/workflow/state", headers=self.headers)
    
    def transition_workflow(self, target_state, params=None):
        """
        Transition workflow state.
        
        Args:
            target_state: Target state
            params: Additional parameters
        """
        payload = {"target_state": target_state}
        if params:
            payload["params"] = params
        
        return self.client.post("/api/workflow/transition", headers=self.headers, json=payload)
    
    def analyze_portal(self, url=None, network_id=None):
        """
        Analyze a portal.
        
        Args:
            url: Portal URL
            network_id: Network ID
        """
        payload = {}
        if url:
            payload["url"] = url
        if network_id:
            payload["network_id"] = network_id
        
        return self.client.post("/api/analyze", headers=self.headers, json=payload)
    
    def clone_portal(self, portal_id, output_dir=None):
        """
        Clone a portal.
        
        Args:
            portal_id: Portal ID
            output_dir: Output directory
        """
        payload = {"portal_id": portal_id}
        if output_dir:
            payload["output_dir"] = output_dir
        
        return self.client.post("/api/clone", headers=self.headers, json=payload)
    
    def create_ap(self, interface, network_id=None, ssid=None, channel=None):
        """
        Create an access point.
        
        Args:
            interface: Wireless interface
            network_id: Network ID
            ssid: SSID
            channel: Channel
        """
        payload = {"interface": interface}
        if network_id:
            payload["network_id"] = network_id
        if ssid:
            payload["ssid"] = ssid
        if channel:
            payload["channel"] = channel
        
        return self.client.post("/api/ap/create", headers=self.headers, json=payload)
    
    def start_deauth(self, interface, network_id=None, bssid=None, client_macs=None):
        """
        Start deauthentication.
        
        Args:
            interface: Wireless interface
            network_id: Network ID
            bssid: BSSID
            client_macs: List of client MAC addresses
        """
        payload = {"interface": interface}
        if network_id:
            payload["network_id"] = network_id
        if bssid:
            payload["bssid"] = bssid
        if client_macs:
            payload["client_macs"] = client_macs
        
        return self.client.post("/api/deauth/start", headers=self.headers, json=payload)
    
    def start_capture(self, port=None):
        """
        Start credential capture.
        
        Args:
            port: Port to listen on
        """
        payload = {}
        if port:
            payload["port"] = port
        
        return self.client.post("/api/capture/start", headers=self.headers, json=payload)
    
    def generate_report(self, title=None, description=None, report_format="pdf", network_ids=None):
        """
        Generate a report.
        
        Args:
            title: Report title
            description: Report description
            report_format: Report format
            network_ids: Network IDs to include
        """
        payload = {"format": report_format}
        if title:
            payload["title"] = title
        if description:
            payload["description"] = description
        if network_ids:
            payload["network_ids"] = network_ids
        
        return self.client.post("/api/report/generate", headers=self.headers, json=payload)
    
    def schedule_report(self, title, description, schedule, report_format="pdf", network_ids=None):
        """
        Schedule a report.
        
        Args:
            title: Report title
            description: Report description
            schedule: Cron schedule
            report_format: Report format
            network_ids: Network IDs to include
        """
        payload = {
            "title": title,
            "description": description,
            "schedule": schedule,
            "format": report_format
        }
        if network_ids:
            payload["network_ids"] = network_ids
        
        return self.client.post("/api/report/schedule", headers=self.headers, json=payload)
    
    def get_scheduled_reports(self):
        """Get scheduled reports."""
        return self.client.get("/api/report/scheduled", headers=self.headers)
    
    def delete_scheduled_report(self, report_id):
        """
        Delete a scheduled report.
        
        Args:
            report_id: Report ID
        """
        return self.client.delete(f"/api/report/scheduled/{report_id}", headers=self.headers)
    
    def get_scan_sessions(self, limit=None):
        """
        Get scan sessions.
        
        Args:
            limit: Maximum number of sessions to return
        """
        params = {}
        if limit:
            params["limit"] = limit
        
        return self.client.get("/api/scan_sessions", headers=self.headers, params=params)
    
    def stop_workflow(self):
        """Stop the workflow."""
        return self.client.post("/api/workflow/stop", headers=self.headers)
    
    def get_openapi_spec(self):
        """Get OpenAPI specification."""
        return self.client.get("/api/openapi.json")
    
    def get_api_docs(self):
        """Get API documentation."""
        return self.client.get("/api/docs")


class CaptiveCloneUser(HttpUser):
    """Locust user for testing the CaptiveClone API."""
    
    # Wait between 1 and 5 seconds between tasks
    wait_time = between(1, 5)
    
    def __init__(self, *args, **kwargs):
        """Initialize the user."""
        super().__init__(*args, **kwargs)
        self.api = CaptiveCloneAPI(self.client)
        self.network_ids = []
        self.portal_ids = []
        self.report_ids = []
    
    def on_start(self):
        """Called when a user starts running."""
        # Test the version endpoint to make sure the API is available
        response = self.api.get_version()
        if response.status_code != 200:
            self.environment.runner.quit()
    
    @tag("public")
    @task(3)
    def test_version(self):
        """Test the version endpoint."""
        response = self.api.get_version()
        if response.status_code == 200:
            data = response.json()
            if "version" not in data:
                response.failure("Missing version in response")
    
    @tag("api", "networks")
    @task(5)
    def test_get_networks(self):
        """Test getting networks."""
        response = self.api.get_networks()
        if response.status_code == 200:
            data = response.json()
            if "networks" in data and data["networks"]:
                self.network_ids = [n["id"] for n in data["networks"]]
    
    @tag("api", "networks")
    @task(2)
    def test_get_network(self):
        """Test getting a specific network."""
        if not self.network_ids:
            return
        
        network_id = random.choice(self.network_ids)
        response = self.api.get_network(network_id)
        if response.status_code == 200:
            data = response.json()
            if data["id"] != network_id:
                response.failure(f"Expected network_id {network_id}, got {data['id']}")
    
    @tag("api", "workflow")
    @task(1)
    def test_workflow_state(self):
        """Test getting workflow state."""
        response = self.api.get_workflow_state()
        if response.status_code == 200:
            data = response.json()
            if "state" not in data:
                response.failure("Missing state in response")
    
    @tag("api", "scan_sessions")
    @task(3)
    def test_scan_sessions(self):
        """Test getting scan sessions."""
        response = self.api.get_scan_sessions(limit=5)
        if response.status_code == 200:
            data = response.json()
            if "scan_sessions" not in data:
                response.failure("Missing scan_sessions in response")
    
    @tag("api", "reports")
    @task(2)
    def test_scheduled_reports(self):
        """Test getting scheduled reports."""
        response = self.api.get_scheduled_reports()
        if response.status_code == 200:
            data = response.json()
            if "reports" in data and data["reports"]:
                self.report_ids = [r["id"] for r in data["reports"]]
    
    @tag("api", "openapi")
    @task(1)
    def test_openapi_spec(self):
        """Test getting OpenAPI specification."""
        response = self.api.get_openapi_spec()
        if response.status_code == 200:
            data = response.json()
            if "openapi" not in data:
                response.failure("Missing openapi version in response")
    
    @tag("api", "docs")
    @task(1)
    def test_api_docs(self):
        """Test getting API documentation."""
        response = self.api.get_api_docs()
        if response.status_code == 200:
            if "swagger-ui" not in response.text:
                response.failure("Missing swagger-ui in response")
    
    @tag("api", "workflow", "scan", "advanced")
    @task(1)
    def test_scan_workflow(self):
        """Test the scanning workflow."""
        # Only run this test occasionally to avoid overloading the server
        if random.random() > 0.1:
            return
        
        # Start scan
        interface = random.choice(["wlan0", "wlan1"])
        response = self.api.start_scan(interface=interface)
        if response.status_code not in [200, 400]:  # 400 if workflow not in correct state
            response.failure(f"Failed to start scan: {response.text}")
            return
        
        # Wait for scan to complete
        time.sleep(2)
        
        # Get workflow state
        response = self.api.get_workflow_state()
        if response.status_code != 200:
            response.failure(f"Failed to get workflow state: {response.text}")
    
    @tag("api", "reports", "advanced")
    @task(1)
    def test_schedule_report(self):
        """Test scheduling a report."""
        # Only run this test occasionally
        if random.random() > 0.2:
            return
        
        title = f"Load Test Report {str(uuid.uuid4())[:8]}"
        description = "Report scheduled during load testing"
        schedule = "0 * * * *"  # Every hour
        
        response = self.api.schedule_report(title=title, description=description, schedule=schedule)
        if response.status_code == 200:
            data = response.json()
            if "report_id" in data:
                self.report_ids.append(data["report_id"])


class CaptiveCloneFullWorkflowUser(HttpUser):
    """
    User that tests the full workflow end-to-end.
    This user is more resource-intensive and should have a smaller weight.
    """
    
    weight = 1  # Lower weight than regular user
    wait_time = between(5, 10)  # Longer waits to reduce load
    
    def __init__(self, *args, **kwargs):
        """Initialize the user."""
        super().__init__(*args, **kwargs)
        self.api = CaptiveCloneAPI(self.client)
    
    @tag("workflow", "full")
    @task
    def full_workflow(self):
        """Test the complete workflow from scan to report."""
        # Only run this test very occasionally
        if random.random() > 0.05:
            return
        
        # Start with a fresh workflow
        response = self.api.stop_workflow()
        # Ignore response - might not be in right state
        
        # Start scan
        interface = "wlan0"
        response = self.api.start_scan(interface=interface)
        if response.status_code != 200:
            # Not an error, might not be in the right state
            return
        
        # Skip to the relevant states using test data
        # In a real scenario, we would follow the proper workflow steps
        response = self.api.transition_workflow(
            "scan_complete", 
            {"networks": [{"id": 1, "ssid": "test_network", "bssid": "00:11:22:33:44:55"}]}
        )
        if response.status_code != 200:
            return
        
        # Start analysis
        response = self.api.analyze_portal(url="http://test.example.com")
        if response.status_code != 200:
            return
        
        # Skip to analysis complete
        response = self.api.transition_workflow(
            "analysis_complete", 
            {"portal": {"id": 1, "login_url": "http://test.example.com", "requires_authentication": True}}
        )
        if response.status_code != 200:
            return
        
        # Clone portal
        response = self.api.clone_portal(portal_id=1)
        if response.status_code != 200:
            return
        
        # Skip to clone complete
        response = self.api.transition_workflow("clone_complete")
        if response.status_code != 200:
            return
        
        # Create AP
        response = self.api.create_ap(interface="wlan1", ssid="test_ap")
        if response.status_code != 200:
            return
        
        # Skip to running
        response = self.api.transition_workflow("ap_running")
        if response.status_code != 200:
            return
        
        # Start deauth
        response = self.api.start_deauth(interface="wlan0", bssid="00:11:22:33:44:55")
        if response.status_code != 200:
            return
        
        # Skip to running
        response = self.api.transition_workflow("deauth_running")
        if response.status_code != 200:
            return
        
        # Start capture
        response = self.api.start_capture()
        if response.status_code != 200:
            return
        
        # Generate report
        response = self.api.generate_report(
            title="Full Workflow Test", 
            description="Report generated during load testing of full workflow"
        )
        if response.status_code != 200:
            return
        
        # Verify we got to the complete state
        response = self.api.get_workflow_state()
        if response.status_code == 200:
            data = response.json()
            if "state" not in data:
                response.failure("Missing state in workflow response") 