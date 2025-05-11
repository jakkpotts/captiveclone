"""
RESTful API module for CaptiveClone with OpenAPI specification.

This module provides a RESTful API for interacting with CaptiveClone
and includes OpenAPI documentation.
"""

import json
import os
import logging
import datetime
from typing import Dict, List, Optional, Any, Union, Callable
from pathlib import Path
from functools import wraps

from flask import Blueprint, request, jsonify, current_app, send_from_directory
from flask_cors import CORS
from werkzeug.exceptions import HTTPException, NotFound, BadRequest
from sqlalchemy.orm import Session

from captiveclone.database.models import Network, CaptivePortal, ScanSession, User
from captiveclone.database.db_pool import get_db_session, cached_query, optimize_query
from captiveclone.core.scanner import NetworkScanner
from captiveclone.core.portal_analyzer import PortalAnalyzer
from captiveclone.core.portal_cloner import PortalCloner
from captiveclone.core.access_point import AccessPoint
from captiveclone.core.deauthenticator import Deauthenticator
from captiveclone.core.credential_capture import CredentialCapture
from captiveclone.core.reporting import ReportManager
from captiveclone.core.workflow import Workflow, WorkflowState

logger = logging.getLogger(__name__)

# Create Blueprint
api_bp = Blueprint('api', __name__, url_prefix='/api')
CORS(api_bp)  # Enable CORS for all API routes

# API version
API_VERSION = "v1"

# Global workflow instance
_workflow: Optional[Workflow] = None


def json_response(data: Any, status_code: int = 200) -> tuple:
    """
    Create a JSON response with the given data and status code.
    
    Args:
        data: Data to return as JSON
        status_code: HTTP status code
        
    Returns:
        Flask response with JSON data and status code
    """
    response = jsonify(data)
    return response, status_code


def api_error(message: str, status_code: int = 400, details: Optional[Dict[str, Any]] = None) -> tuple:
    """
    Create a JSON error response.
    
    Args:
        message: Error message
        status_code: HTTP status code
        details: Additional error details
        
    Returns:
        Flask response with error data and status code
    """
    error_data = {
        "error": True,
        "message": message,
        "code": status_code
    }
    
    if details:
        error_data["details"] = details
    
    return json_response(error_data, status_code)


def requires_auth(f: Callable) -> Callable:
    """
    Decorator to check if the request is authenticated.
    
    Args:
        f: Function to wrap
        
    Returns:
        Wrapped function that checks authentication
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # Check authentication - this is a simple API key check for now
        api_key = request.headers.get('X-API-Key')
        
        if not api_key:
            return api_error("Authentication required", 401)
        
        # Check if the API key is valid (a proper implementation would check against a database)
        valid_key = current_app.config.get('API_KEY')
        if not api_key == valid_key:
            return api_error("Invalid API key", 401)
        
        return f(*args, **kwargs)
    return decorated


def get_workflow() -> Workflow:
    """
    Get or create the global workflow instance.
    
    Returns:
        Workflow instance
    """
    global _workflow
    
    if _workflow is None:
        config = current_app.config.get('app_config')
        db_session = current_app.config.get('db_session')
        _workflow = Workflow(config, db_session)
        
        # Load saved state if available
        _workflow.load_state()
    
    return _workflow


# API routes

@api_bp.route('/version', methods=['GET'])
def get_version():
    """Get the API version."""
    return json_response({
        "version": API_VERSION,
        "captiveclone_version": "1.0.0"  # Should be fetched from version file
    })


@api_bp.route('/networks', methods=['GET'])
@requires_auth
def get_networks():
    """Get all networks."""
    try:
        with get_db_session() as session:
            # Apply query optimization
            query = optimize_query(session.query(Network))
            
            # Apply filters if provided
            has_captive_portal = request.args.get('has_captive_portal')
            if has_captive_portal is not None:
                has_captive_portal_bool = has_captive_portal.lower() == 'true'
                query = query.filter(Network.has_captive_portal == has_captive_portal_bool)
            
            # Get networks
            networks = query.all()
            
            # Convert to dictionary
            result = [
                {
                    "id": network.id,
                    "ssid": network.ssid,
                    "bssid": network.bssid,
                    "channel": network.channel,
                    "encryption": network.encryption,
                    "signal_strength": network.signal_strength,
                    "has_captive_portal": network.has_captive_portal,
                    "first_seen": network.first_seen.isoformat() if network.first_seen else None,
                    "last_seen": network.last_seen.isoformat() if network.last_seen else None
                }
                for network in networks
            ]
            
            return json_response({"networks": result})
            
    except Exception as e:
        logger.error(f"Error getting networks: {str(e)}")
        return api_error(f"Failed to get networks: {str(e)}")


@api_bp.route('/networks/<int:network_id>', methods=['GET'])
@requires_auth
def get_network(network_id: int):
    """Get a network by ID."""
    try:
        with get_db_session() as session:
            network = session.query(Network).get(network_id)
            
            if not network:
                return api_error(f"Network with ID {network_id} not found", 404)
            
            # Convert to dictionary
            result = {
                "id": network.id,
                "ssid": network.ssid,
                "bssid": network.bssid,
                "channel": network.channel,
                "encryption": network.encryption,
                "signal_strength": network.signal_strength,
                "has_captive_portal": network.has_captive_portal,
                "first_seen": network.first_seen.isoformat() if network.first_seen else None,
                "last_seen": network.last_seen.isoformat() if network.last_seen else None
            }
            
            # Include captive portal if available
            if network.captive_portal:
                portal = network.captive_portal
                result["captive_portal"] = {
                    "id": portal.id,
                    "login_url": portal.login_url,
                    "redirect_url": portal.redirect_url,
                    "requires_authentication": portal.requires_authentication,
                    "first_seen": portal.first_seen.isoformat() if portal.first_seen else None,
                    "last_seen": portal.last_seen.isoformat() if portal.last_seen else None
                }
            
            return json_response(result)
            
    except Exception as e:
        logger.error(f"Error getting network {network_id}: {str(e)}")
        return api_error(f"Failed to get network: {str(e)}")


@api_bp.route('/scan', methods=['POST'])
@requires_auth
def start_scan():
    """Start a network scan."""
    try:
        data = request.json or {}
        interface = data.get('interface')
        timeout = data.get('timeout', 60)
        
        # Get the workflow
        workflow = get_workflow()
        
        # Check if we can start a scan
        if workflow.state not in [WorkflowState.INITIAL, WorkflowState.SCAN_COMPLETE, WorkflowState.COMPLETE]:
            return api_error(f"Cannot start scan from current state: {workflow.state.value}")
        
        # Start the workflow
        if workflow.state == WorkflowState.INITIAL:
            workflow.start(network_interface=interface)
        else:
            workflow.transition_to(WorkflowState.SCANNING, interface=interface)
        
        return json_response({
            "message": "Scan started",
            "workflow_id": workflow.id,
            "state": workflow.state.value
        })
        
    except Exception as e:
        logger.error(f"Error starting scan: {str(e)}")
        return api_error(f"Failed to start scan: {str(e)}")


@api_bp.route('/workflow/state', methods=['GET'])
@requires_auth
def get_workflow_state():
    """Get the current workflow state."""
    try:
        workflow = get_workflow()
        
        # Get workflow state
        result = {
            "id": workflow.id,
            "state": workflow.state.value,
            "history": workflow.history,
            "errors": workflow.errors
        }
        
        # Include state data if available
        if workflow.state_data:
            result["data"] = workflow.state_data
        
        return json_response(result)
        
    except Exception as e:
        logger.error(f"Error getting workflow state: {str(e)}")
        return api_error(f"Failed to get workflow state: {str(e)}")


@api_bp.route('/workflow/transition', methods=['POST'])
@requires_auth
def transition_workflow():
    """Transition the workflow to a new state."""
    try:
        data = request.json or {}
        target_state_str = data.get('target_state')
        params = data.get('params', {})
        
        if not target_state_str:
            return api_error("Target state is required")
        
        # Get the workflow
        workflow = get_workflow()
        
        # Convert string to enum
        try:
            target_state = WorkflowState(target_state_str)
        except ValueError:
            return api_error(f"Invalid target state: {target_state_str}")
        
        # Check if transition is possible
        can_transition, reason = workflow.can_transition_to(target_state)
        if not can_transition:
            return api_error(f"Cannot transition to {target_state_str}: {reason}")
        
        # Perform the transition
        workflow.transition_to(target_state, **params)
        
        return json_response({
            "message": f"Transitioned to {target_state.value}",
            "workflow_id": workflow.id,
            "state": workflow.state.value
        })
        
    except Exception as e:
        logger.error(f"Error transitioning workflow: {str(e)}")
        return api_error(f"Failed to transition workflow: {str(e)}")


@api_bp.route('/analyze', methods=['POST'])
@requires_auth
def analyze_portal():
    """Analyze a captive portal."""
    try:
        data = request.json or {}
        url = data.get('url')
        network_id = data.get('network_id')
        
        if not url and not network_id:
            return api_error("Either URL or network_id is required")
        
        # Get the workflow
        workflow = get_workflow()
        
        # Start analysis
        if workflow.state == WorkflowState.SCAN_COMPLETE:
            if network_id:
                workflow.transition_to(WorkflowState.ANALYZING, network_id=network_id)
            else:
                workflow.transition_to(WorkflowState.ANALYZING, url=url)
        else:
            return api_error(f"Cannot start analysis from current state: {workflow.state.value}")
        
        return json_response({
            "message": "Analysis started",
            "workflow_id": workflow.id,
            "state": workflow.state.value
        })
        
    except Exception as e:
        logger.error(f"Error analyzing portal: {str(e)}")
        return api_error(f"Failed to analyze portal: {str(e)}")


@api_bp.route('/clone', methods=['POST'])
@requires_auth
def clone_portal():
    """Clone a captive portal."""
    try:
        data = request.json or {}
        portal_id = data.get('portal_id')
        output_dir = data.get('output_dir')
        
        if not portal_id:
            return api_error("Portal ID is required")
        
        # Get the workflow
        workflow = get_workflow()
        
        # Start cloning
        if workflow.state == WorkflowState.ANALYSIS_COMPLETE:
            workflow.transition_to(WorkflowState.CLONING, portal_id=portal_id, output_dir=output_dir)
        else:
            return api_error(f"Cannot start cloning from current state: {workflow.state.value}")
        
        return json_response({
            "message": "Cloning started",
            "workflow_id": workflow.id,
            "state": workflow.state.value
        })
        
    except Exception as e:
        logger.error(f"Error cloning portal: {str(e)}")
        return api_error(f"Failed to clone portal: {str(e)}")


@api_bp.route('/ap/create', methods=['POST'])
@requires_auth
def create_ap():
    """Create an access point."""
    try:
        data = request.json or {}
        interface = data.get('interface')
        network_id = data.get('network_id')
        ssid = data.get('ssid')
        channel = data.get('channel')
        
        if not interface:
            return api_error("Interface is required")
        
        if not network_id and not ssid:
            return api_error("Either network_id or ssid is required")
        
        # Get the workflow
        workflow = get_workflow()
        
        # Start AP creation
        if workflow.state == WorkflowState.CLONE_COMPLETE:
            workflow.transition_to(
                WorkflowState.AP_CREATING,
                interface=interface,
                network_id=network_id,
                ssid=ssid,
                channel=channel
            )
        else:
            return api_error(f"Cannot create AP from current state: {workflow.state.value}")
        
        return json_response({
            "message": "Access point creation started",
            "workflow_id": workflow.id,
            "state": workflow.state.value
        })
        
    except Exception as e:
        logger.error(f"Error creating AP: {str(e)}")
        return api_error(f"Failed to create access point: {str(e)}")


@api_bp.route('/deauth/start', methods=['POST'])
@requires_auth
def start_deauth():
    """Start deauthentication."""
    try:
        data = request.json or {}
        interface = data.get('interface')
        network_id = data.get('network_id')
        bssid = data.get('bssid')
        client_macs = data.get('client_macs')
        
        if not interface:
            return api_error("Interface is required")
        
        if not network_id and not bssid:
            return api_error("Either network_id or bssid is required")
        
        # Get the workflow
        workflow = get_workflow()
        
        # Start deauthentication
        if workflow.state == WorkflowState.AP_RUNNING:
            workflow.transition_to(
                WorkflowState.DEAUTH_STARTING,
                interface=interface,
                network_id=network_id,
                bssid=bssid,
                client_macs=client_macs
            )
        else:
            return api_error(f"Cannot start deauthentication from current state: {workflow.state.value}")
        
        return json_response({
            "message": "Deauthentication started",
            "workflow_id": workflow.id,
            "state": workflow.state.value
        })
        
    except Exception as e:
        logger.error(f"Error starting deauthentication: {str(e)}")
        return api_error(f"Failed to start deauthentication: {str(e)}")


@api_bp.route('/capture/start', methods=['POST'])
@requires_auth
def start_capture():
    """Start credential capture."""
    try:
        data = request.json or {}
        port = data.get('port')
        
        # Get the workflow
        workflow = get_workflow()
        
        # Start credential capture
        if workflow.state == WorkflowState.DEAUTH_RUNNING:
            workflow.transition_to(WorkflowState.CAPTURING, port=port)
        else:
            return api_error(f"Cannot start capture from current state: {workflow.state.value}")
        
        return json_response({
            "message": "Credential capture started",
            "workflow_id": workflow.id,
            "state": workflow.state.value
        })
        
    except Exception as e:
        logger.error(f"Error starting credential capture: {str(e)}")
        return api_error(f"Failed to start credential capture: {str(e)}")


@api_bp.route('/report/generate', methods=['POST'])
@requires_auth
def generate_report():
    """Generate a report."""
    try:
        data = request.json or {}
        title = data.get('title')
        description = data.get('description')
        report_format = data.get('format', 'pdf')
        network_ids = data.get('network_ids')
        
        # Get the workflow
        workflow = get_workflow()
        
        # Confirm we're in a valid state to generate a report
        if workflow.state not in [WorkflowState.CAPTURING, WorkflowState.COMPLETE]:
            return api_error(f"Cannot generate report from current state: {workflow.state.value}")
        
        # Transition to reporting state
        workflow.transition_to(
            WorkflowState.REPORTING,
            title=title,
            description=description,
            format=report_format,
            network_ids=network_ids
        )
        
        return json_response({
            "message": "Report generation started",
            "workflow_id": workflow.id,
            "state": workflow.state.value
        })
        
    except Exception as e:
        logger.error(f"Error generating report: {str(e)}")
        return api_error(f"Failed to generate report: {str(e)}")


@api_bp.route('/report/schedule', methods=['POST'])
@requires_auth
def schedule_report():
    """Schedule a recurring report."""
    try:
        data = request.json or {}
        title = data.get('title')
        description = data.get('description')
        schedule = data.get('schedule')
        report_format = data.get('format', 'pdf')
        network_ids = data.get('network_ids')
        
        if not title or not description or not schedule:
            return api_error("Title, description, and schedule are required")
        
        # Create report manager
        config = current_app.config.get('app_config')
        db_session = current_app.config.get('db_session')
        report_manager = ReportManager(config, db_session)
        
        # Schedule the report
        report_job = report_manager.schedule_report(
            title=title,
            description=description,
            schedule=schedule,
            report_format=report_format,
            network_ids=network_ids
        )
        
        return json_response({
            "message": "Report scheduled",
            "report_id": report_job["id"],
            "title": report_job["title"],
            "schedule": report_job["schedule"]
        })
        
    except Exception as e:
        logger.error(f"Error scheduling report: {str(e)}")
        return api_error(f"Failed to schedule report: {str(e)}")


@api_bp.route('/report/scheduled', methods=['GET'])
@requires_auth
def get_scheduled_reports():
    """Get all scheduled reports."""
    try:
        # Create report manager
        config = current_app.config.get('app_config')
        db_session = current_app.config.get('db_session')
        report_manager = ReportManager(config, db_session)
        
        # Get scheduled reports
        scheduled_reports = report_manager.get_scheduled_reports()
        
        # Convert to JSON-serializable format
        for report in scheduled_reports:
            if "created_at" in report:
                report["created_at"] = report["created_at"].isoformat()
            if "last_run" in report and report["last_run"]:
                report["last_run"] = report["last_run"].isoformat()
        
        return json_response({"reports": scheduled_reports})
        
    except Exception as e:
        logger.error(f"Error getting scheduled reports: {str(e)}")
        return api_error(f"Failed to get scheduled reports: {str(e)}")


@api_bp.route('/report/scheduled/<int:report_id>', methods=['DELETE'])
@requires_auth
def delete_scheduled_report(report_id: int):
    """Delete a scheduled report."""
    try:
        # Create report manager
        config = current_app.config.get('app_config')
        db_session = current_app.config.get('db_session')
        report_manager = ReportManager(config, db_session)
        
        # Delete the report
        success = report_manager.delete_scheduled_report(report_id)
        
        if not success:
            return api_error(f"Report with ID {report_id} not found", 404)
        
        return json_response({
            "message": f"Report {report_id} deleted",
            "success": True
        })
        
    except Exception as e:
        logger.error(f"Error deleting scheduled report {report_id}: {str(e)}")
        return api_error(f"Failed to delete scheduled report: {str(e)}")


@api_bp.route('/scan_sessions', methods=['GET'])
@requires_auth
@cached_query(ttl=30)  # Cache for 30 seconds
def get_scan_sessions():
    """Get all scan sessions."""
    try:
        with get_db_session() as session:
            # Apply query optimization
            query = optimize_query(
                session.query(ScanSession).order_by(ScanSession.start_time.desc())
            )
            
            # Apply limit if provided
            limit = request.args.get('limit')
            if limit:
                query = query.limit(int(limit))
            
            # Get scan sessions
            scan_sessions = query.all()
            
            # Convert to dictionary
            result = [
                {
                    "id": scan_session.id,
                    "start_time": scan_session.start_time.isoformat() if scan_session.start_time else None,
                    "end_time": scan_session.end_time.isoformat() if scan_session.end_time else None,
                    "interface": scan_session.interface,
                    "networks_found": scan_session.networks_found,
                    "captive_portals_found": scan_session.captive_portals_found,
                    "duration": (scan_session.end_time - scan_session.start_time).total_seconds() if scan_session.end_time else None
                }
                for scan_session in scan_sessions
            ]
            
            return json_response({"scan_sessions": result})
            
    except Exception as e:
        logger.error(f"Error getting scan sessions: {str(e)}")
        return api_error(f"Failed to get scan sessions: {str(e)}")


@api_bp.route('/workflow/stop', methods=['POST'])
@requires_auth
def stop_workflow():
    """Stop the workflow."""
    try:
        # Get the workflow
        workflow = get_workflow()
        
        # Stop the workflow
        workflow.stop()
        
        return json_response({
            "message": "Workflow stopped",
            "workflow_id": workflow.id,
            "state": workflow.state.value
        })
        
    except Exception as e:
        logger.error(f"Error stopping workflow: {str(e)}")
        return api_error(f"Failed to stop workflow: {str(e)}")


# OpenAPI specification
@api_bp.route('/openapi.json', methods=['GET'])
def get_openapi_spec():
    """Get the OpenAPI specification."""
    # Load OpenAPI spec from JSON file
    spec_path = os.path.join(os.path.dirname(__file__), 'openapi.json')
    
    if os.path.exists(spec_path):
        with open(spec_path, 'r') as f:
            return json_response(json.load(f))
    
    # Generate minimal spec if file doesn't exist
    spec = {
        "openapi": "3.0.0",
        "info": {
            "title": "CaptiveClone API",
            "description": "API for CaptiveClone network security assessment tool",
            "version": API_VERSION
        },
        "servers": [
            {
                "url": "/api"
            }
        ],
        "paths": {},
        "components": {
            "securitySchemes": {
                "ApiKeyAuth": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-API-Key"
                }
            }
        },
        "security": [
            {
                "ApiKeyAuth": []
            }
        ]
    }
    
    return json_response(spec)


@api_bp.route('/docs', methods=['GET'])
def get_api_docs():
    """Get the API documentation UI."""
    # Serve Swagger UI for API documentation
    return '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>CaptiveClone API Documentation</title>
        <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@5.4.2/swagger-ui.css">
    </head>
    <body>
        <div id="swagger-ui"></div>
        <script src="https://unpkg.com/swagger-ui-dist@5.4.2/swagger-ui-bundle.js"></script>
        <script>
            window.onload = function() {
                SwaggerUIBundle({
                    url: "/api/openapi.json",
                    dom_id: '#swagger-ui',
                    deepLinking: true,
                    presets: [
                        SwaggerUIBundle.presets.apis,
                        SwaggerUIBundle.SwaggerUIStandalonePreset
                    ],
                    layout: "BaseLayout"
                });
            }
        </script>
    </body>
    </html>
    '''


# Error handlers
@api_bp.errorhandler(Exception)
def handle_exception(e):
    """Handle all exceptions."""
    logger.error(f"API error: {str(e)}")
    
    if isinstance(e, HTTPException):
        return api_error(str(e), e.code)
    
    return api_error("Internal server error", 500)


@api_bp.errorhandler(400)
def handle_bad_request(e):
    """Handle bad request errors."""
    return api_error("Bad request", 400)


@api_bp.errorhandler(404)
def handle_not_found(e):
    """Handle not found errors."""
    return api_error("Resource not found", 404)


@api_bp.errorhandler(500)
def handle_internal_error(e):
    """Handle internal server errors."""
    return api_error("Internal server error", 500)


def init_api(app):
    """
    Initialize the API module.
    
    Args:
        app: Flask application
    """
    # Register blueprint
    app.register_blueprint(api_bp)
    
    logger.info("API module initialized") 