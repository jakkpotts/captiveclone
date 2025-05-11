"""
Reporting module for CaptiveClone.

This module provides functionality for generating reports in various formats (PDF, HTML)
with customizable templates and vulnerability assessment data.
"""

import os
import json
import logging
import datetime
from typing import Dict, List, Optional, Any, Union
from pathlib import Path

import jinja2
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.platypus import PageBreak, ListFlowable, ListItem
from reportlab.lib.units import inch
from sqlalchemy.orm import Session

from captiveclone.database.models import Network, CaptivePortal, ScanSession, User, PortalAsset
from captiveclone.utils.config import Config

logger = logging.getLogger(__name__)

class Report:
    """Base report class with common functionality."""
    
    def __init__(
        self, 
        title: str, 
        description: str, 
        config: Config,
        template_name: Optional[str] = None,
        custom_template_path: Optional[str] = None
    ):
        """
        Initialize a new report.
        
        Args:
            title: Report title
            description: Report description
            config: CaptiveClone configuration object
            template_name: Name of built-in template to use (if not using custom)
            custom_template_path: Path to custom template (if not using built-in)
        """
        self.title = title
        self.description = description
        self.config = config
        self.template_name = template_name or "default"
        self.custom_template_path = custom_template_path
        self.data: Dict[str, Any] = {
            "title": title,
            "description": description,
            "timestamp": datetime.datetime.now(),
            "generated_by": "CaptiveClone",
            "version": "1.0.0",  # Should be fetched from version file
            "networks": [],
            "captive_portals": [],
            "scan_sessions": [],
            "vulnerability_assessment": {},
            "recommendations": []
        }
        
        # Set up the Jinja2 environment
        self.template_dirs = [
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates", "reports")
        ]
        
        # Add custom template path if provided
        if custom_template_path:
            self.template_dirs.append(custom_template_path)
            
        self.jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(self.template_dirs),
            autoescape=jinja2.select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
    
    def add_network_data(self, session: Session, network_ids: Optional[List[int]] = None) -> None:
        """
        Add network data to the report.
        
        Args:
            session: SQLAlchemy session
            network_ids: Optional list of network IDs to include. If None, include all networks.
        """
        query = session.query(Network)
        if network_ids:
            query = query.filter(Network.id.in_(network_ids))
            
        networks = query.all()
        network_data = []
        
        for network in networks:
            network_info = {
                "id": network.id,
                "ssid": network.ssid,
                "bssid": network.bssid,
                "channel": network.channel,
                "encryption": network.encryption,
                "signal_strength": network.signal_strength,
                "has_captive_portal": network.has_captive_portal,
                "first_seen": network.first_seen,
                "last_seen": network.last_seen,
                "captive_portal": None
            }
            
            if network.captive_portal:
                portal = network.captive_portal
                portal_info = {
                    "id": portal.id,
                    "login_url": portal.login_url,
                    "redirect_url": portal.redirect_url,
                    "requires_authentication": portal.requires_authentication,
                    "form_data": json.loads(portal.form_data) if portal.form_data else None,
                    "first_seen": portal.first_seen,
                    "last_seen": portal.last_seen,
                    "assets": []
                }
                
                if portal.assets:
                    for asset in portal.assets:
                        asset_info = {
                            "id": asset.id,
                            "asset_type": asset.asset_type,
                            "url": asset.url,
                            "local_path": asset.local_path,
                            "content_hash": asset.content_hash
                        }
                        portal_info["assets"].append(asset_info)
                
                network_info["captive_portal"] = portal_info
            
            network_data.append(network_info)
        
        self.data["networks"] = network_data
    
    def add_scan_session_data(self, session: Session, limit: int = 10) -> None:
        """
        Add scan session data to the report.
        
        Args:
            session: SQLAlchemy session
            limit: Maximum number of scan sessions to include
        """
        scan_sessions = session.query(ScanSession).order_by(ScanSession.start_time.desc()).limit(limit).all()
        session_data = []
        
        for scan_session in scan_sessions:
            session_info = {
                "id": scan_session.id,
                "start_time": scan_session.start_time,
                "end_time": scan_session.end_time,
                "interface": scan_session.interface,
                "networks_found": scan_session.networks_found,
                "captive_portals_found": scan_session.captive_portals_found,
                "duration": (scan_session.end_time - scan_session.start_time).total_seconds() if scan_session.end_time else None
            }
            session_data.append(session_info)
        
        self.data["scan_sessions"] = session_data
    
    def add_vulnerability_assessment(self, vuln_data: Dict[str, Any]) -> None:
        """
        Add vulnerability assessment data to the report.
        
        Args:
            vuln_data: Dictionary containing vulnerability assessment data
        """
        self.data["vulnerability_assessment"] = vuln_data
    
    def add_recommendations(self, recommendations: List[Dict[str, str]]) -> None:
        """
        Add recommendations to the report.
        
        Args:
            recommendations: List of recommendation dictionaries with 'title' and 'description' keys
        """
        self.data["recommendations"] = recommendations


class HTMLReport(Report):
    """HTML report generator."""
    
    def generate(self, output_path: str) -> str:
        """
        Generate an HTML report.
        
        Args:
            output_path: Path to save the HTML report to
            
        Returns:
            Path to the generated report
        """
        try:
            template_filename = f"{self.template_name}.html"
            template = self.jinja_env.get_template(template_filename)
            
            html_content = template.render(**self.data)
            
            output_file = os.path.join(output_path, f"report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
                
            logger.info(f"HTML report generated at {output_file}")
            return output_file
            
        except Exception as e:
            logger.error(f"Failed to generate HTML report: {str(e)}")
            raise


class PDFReport(Report):
    """PDF report generator using ReportLab."""
    
    def generate(self, output_path: str) -> str:
        """
        Generate a PDF report.
        
        Args:
            output_path: Path to save the PDF report to
            
        Returns:
            Path to the generated report
        """
        try:
            output_file = os.path.join(output_path, f"report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            
            doc = SimpleDocTemplate(
                output_file,
                pagesize=letter,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=72
            )
            
            styles = getSampleStyleSheet()
            styles.add(ParagraphStyle(
                name='Heading1',
                parent=styles['Heading1'],
                fontSize=18,
                spaceAfter=12
            ))
            styles.add(ParagraphStyle(
                name='Heading2',
                parent=styles['Heading2'],
                fontSize=16,
                spaceAfter=10
            ))
            styles.add(ParagraphStyle(
                name='Heading3',
                parent=styles['Heading3'],
                fontSize=14,
                spaceAfter=8
            ))
            styles.add(ParagraphStyle(
                name='Normal',
                parent=styles['Normal'],
                fontSize=11,
                spaceAfter=6
            ))
            
            # Build document elements
            elements = []
            
            # Title
            elements.append(Paragraph(self.data["title"], styles['Heading1']))
            elements.append(Spacer(1, 0.25 * inch))
            
            # Description
            elements.append(Paragraph(self.data["description"], styles['Normal']))
            elements.append(Spacer(1, 0.25 * inch))
            
            # General information
            elements.append(Paragraph("Report Information", styles['Heading2']))
            elements.append(Paragraph(f"Generated: {self.data['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
            elements.append(Paragraph(f"Generated by: {self.data['generated_by']} v{self.data['version']}", styles['Normal']))
            elements.append(Spacer(1, 0.25 * inch))
            
            # Scan sessions
            if self.data["scan_sessions"]:
                elements.append(Paragraph("Scan Sessions", styles['Heading2']))
                scan_data = [["ID", "Start Time", "Duration", "Networks", "Captive Portals"]]
                
                for session in self.data["scan_sessions"]:
                    scan_data.append([
                        str(session["id"]),
                        session["start_time"].strftime("%Y-%m-%d %H:%M:%S"),
                        f"{session['duration']:.2f} seconds" if session["duration"] else "N/A",
                        str(session["networks_found"]),
                        str(session["captive_portals_found"])
                    ])
                
                scan_table = Table(scan_data, repeatRows=1)
                scan_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 12),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ]))
                
                elements.append(scan_table)
                elements.append(Spacer(1, 0.25 * inch))
            
            # Networks
            if self.data["networks"]:
                elements.append(Paragraph("Networks Discovered", styles['Heading2']))
                elements.append(Spacer(1, 0.1 * inch))
                
                for i, network in enumerate(self.data["networks"]):
                    elements.append(Paragraph(f"Network {i+1}: {network['ssid']}", styles['Heading3']))
                    network_data = [
                        ["BSSID", network["bssid"]],
                        ["Channel", str(network["channel"])],
                        ["Encryption", "Yes" if network["encryption"] else "No"],
                        ["Signal Strength", f"{network['signal_strength']} dBm" if network["signal_strength"] else "N/A"],
                        ["Has Captive Portal", "Yes" if network["has_captive_portal"] else "No"],
                        ["First Seen", network["first_seen"].strftime("%Y-%m-%d %H:%M:%S")],
                        ["Last Seen", network["last_seen"].strftime("%Y-%m-%d %H:%M:%S")]
                    ]
                    
                    network_table = Table(network_data)
                    network_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                        ('TEXTCOLOR', (0, 0), (0, -1), colors.black),
                        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ]))
                    
                    elements.append(network_table)
                    elements.append(Spacer(1, 0.1 * inch))
                    
                    # Portal information if available
                    if network["captive_portal"]:
                        portal = network["captive_portal"]
                        elements.append(Paragraph("Captive Portal Details", styles['Heading3']))
                        
                        portal_data = [
                            ["Login URL", portal["login_url"] or "N/A"],
                            ["Redirect URL", portal["redirect_url"] or "N/A"],
                            ["Requires Authentication", "Yes" if portal["requires_authentication"] else "No"],
                            ["First Seen", portal["first_seen"].strftime("%Y-%m-%d %H:%M:%S")],
                            ["Last Seen", portal["last_seen"].strftime("%Y-%m-%d %H:%M:%S")]
                        ]
                        
                        portal_table = Table(portal_data)
                        portal_table.setStyle(TableStyle([
                            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                            ('TEXTCOLOR', (0, 0), (0, -1), colors.black),
                            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                            ('GRID', (0, 0), (-1, -1), 1, colors.black),
                            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ]))
                        
                        elements.append(portal_table)
                        
                        # Form fields if available
                        if portal["form_data"]:
                            elements.append(Paragraph("Form Fields", styles['Heading3']))
                            elements.append(Paragraph("The following form fields were identified:", styles['Normal']))
                            
                            form_items = []
                            for form_id, fields in portal["form_data"].items():
                                form_text = f"Form {form_id}"
                                field_items = []
                                
                                for field_name, field_info in fields.items():
                                    field_type = field_info.get("type", "unknown")
                                    field_text = f"{field_name} ({field_type})"
                                    field_items.append(ListItem(Paragraph(field_text, styles['Normal'])))
                                
                                form_items.append(ListItem(
                                    Paragraph(form_text, styles['Normal']),
                                    ListFlowable(field_items, bulletType='bullet', leftIndent=20)
                                ))
                            
                            elements.append(ListFlowable(form_items, bulletType='bullet', leftIndent=20))
                    
                    elements.append(Spacer(1, 0.1 * inch))
                    if i < len(self.data["networks"]) - 1:
                        elements.append(PageBreak())
            
            # Vulnerability Assessment
            if self.data["vulnerability_assessment"]:
                elements.append(PageBreak())
                elements.append(Paragraph("Vulnerability Assessment", styles['Heading2']))
                elements.append(Spacer(1, 0.1 * inch))
                
                vuln_data = self.data["vulnerability_assessment"]
                
                if "summary" in vuln_data:
                    elements.append(Paragraph("Summary", styles['Heading3']))
                    elements.append(Paragraph(vuln_data["summary"], styles['Normal']))
                    elements.append(Spacer(1, 0.1 * inch))
                
                if "vulnerabilities" in vuln_data:
                    elements.append(Paragraph("Identified Vulnerabilities", styles['Heading3']))
                    
                    vuln_items = []
                    for vuln in vuln_data["vulnerabilities"]:
                        vuln_text = f"{vuln['name']} - Risk Level: {vuln['risk_level']}"
                        vuln_items.append(ListItem(
                            Paragraph(vuln_text, styles['Normal']),
                            Paragraph(vuln['description'], styles['Normal'])
                        ))
                    
                    elements.append(ListFlowable(vuln_items, bulletType='bullet', leftIndent=20))
                    elements.append(Spacer(1, 0.1 * inch))
            
            # Recommendations
            if self.data["recommendations"]:
                elements.append(PageBreak())
                elements.append(Paragraph("Recommendations", styles['Heading2']))
                elements.append(Spacer(1, 0.1 * inch))
                
                rec_items = []
                for rec in self.data["recommendations"]:
                    rec_text = rec["title"]
                    rec_items.append(ListItem(
                        Paragraph(rec_text, styles['Normal']),
                        Paragraph(rec["description"], styles['Normal'])
                    ))
                
                elements.append(ListFlowable(rec_items, bulletType='bullet', leftIndent=20))
            
            # Build the PDF
            doc.build(elements)
            
            logger.info(f"PDF report generated at {output_file}")
            return output_file
            
        except Exception as e:
            logger.error(f"Failed to generate PDF report: {str(e)}")
            raise


class ReportManager:
    """Manager for report generation and scheduling."""
    
    def __init__(self, config: Config, db_session: Session):
        """
        Initialize a new report manager.
        
        Args:
            config: CaptiveClone configuration object
            db_session: SQLAlchemy session
        """
        self.config = config
        self.db_session = db_session
        self.reports_dir = config.get("reports.output_dir", "reports")
        self.scheduled_reports = []
        
        # Create reports directory if it doesn't exist
        os.makedirs(self.reports_dir, exist_ok=True)
    
    def generate_report(
        self,
        title: str,
        description: str,
        report_format: str = "pdf",
        template_name: Optional[str] = None,
        custom_template_path: Optional[str] = None,
        network_ids: Optional[List[int]] = None,
        include_vulnerability_assessment: bool = True,
        include_recommendations: bool = True,
        output_dir: Optional[str] = None
    ) -> str:
        """
        Generate a report.
        
        Args:
            title: Report title
            description: Report description
            report_format: Report format ('pdf' or 'html')
            template_name: Name of built-in template to use (if not using custom)
            custom_template_path: Path to custom template (if not using built-in)
            network_ids: Optional list of network IDs to include
            include_vulnerability_assessment: Whether to include vulnerability assessment data
            include_recommendations: Whether to include recommendations
            output_dir: Optional output directory (defaults to reports_dir from config)
            
        Returns:
            Path to the generated report
        """
        output_dir = output_dir or self.reports_dir
        
        # Create report instance based on requested format
        if report_format.lower() == "pdf":
            report = PDFReport(
                title=title,
                description=description,
                config=self.config,
                template_name=template_name,
                custom_template_path=custom_template_path
            )
        elif report_format.lower() == "html":
            report = HTMLReport(
                title=title,
                description=description,
                config=self.config,
                template_name=template_name,
                custom_template_path=custom_template_path
            )
        else:
            raise ValueError(f"Unsupported report format: {report_format}")
        
        # Add data to report
        report.add_network_data(self.db_session, network_ids)
        report.add_scan_session_data(self.db_session)
        
        if include_vulnerability_assessment:
            vuln_assessment = self._generate_vulnerability_assessment(network_ids)
            report.add_vulnerability_assessment(vuln_assessment)
        
        if include_recommendations:
            recommendations = self._generate_recommendations()
            report.add_recommendations(recommendations)
        
        # Generate and return the report
        return report.generate(output_dir)
    
    def _generate_vulnerability_assessment(self, network_ids: Optional[List[int]] = None) -> Dict[str, Any]:
        """
        Generate vulnerability assessment data for networks.
        
        Args:
            network_ids: Optional list of network IDs to include
            
        Returns:
            Dictionary containing vulnerability assessment data
        """
        # Query relevant networks
        query = self.db_session.query(Network)
        if network_ids:
            query = query.filter(Network.id.in_(network_ids))
        
        networks = query.all()
        
        # Initialize vulnerability assessment data
        vuln_data = {
            "summary": "This vulnerability assessment evaluates risks associated with discovered networks and captive portals.",
            "vulnerabilities": [],
            "risk_summary": {
                "high": 0,
                "medium": 0,
                "low": 0
            }
        }
        
        # Analyze networks for vulnerabilities
        for network in networks:
            # Check for unencrypted networks
            if not network.encryption:
                vuln_data["vulnerabilities"].append({
                    "name": "Unencrypted Network",
                    "network_id": network.id,
                    "network_ssid": network.ssid,
                    "risk_level": "high",
                    "description": f"The network '{network.ssid}' does not use encryption, allowing traffic to be easily intercepted."
                })
                vuln_data["risk_summary"]["high"] += 1
            
            # Check for captive portals with authentication but no HTTPS
            if network.has_captive_portal and network.captive_portal:
                portal = network.captive_portal
                
                if portal.requires_authentication and portal.login_url and not portal.login_url.startswith("https://"):
                    vuln_data["vulnerabilities"].append({
                        "name": "Insecure Authentication",
                        "network_id": network.id,
                        "network_ssid": network.ssid,
                        "portal_id": portal.id,
                        "risk_level": "high",
                        "description": f"The captive portal for '{network.ssid}' requires authentication over an unencrypted connection."
                    })
                    vuln_data["risk_summary"]["high"] += 1
                
                # Check for form submissions without HTTPS
                if portal.form_data:
                    form_data = json.loads(portal.form_data) if isinstance(portal.form_data, str) else portal.form_data
                    for form_id, fields in form_data.items():
                        if any(field.get("type") == "password" for field in fields.values()):
                            vuln_data["vulnerabilities"].append({
                                "name": "Password Submission Over HTTP",
                                "network_id": network.id,
                                "network_ssid": network.ssid,
                                "portal_id": portal.id,
                                "form_id": form_id,
                                "risk_level": "high",
                                "description": f"Form in captive portal for '{network.ssid}' collects passwords without encryption."
                            })
                            vuln_data["risk_summary"]["high"] += 1
                            break
        
        return vuln_data
    
    def _generate_recommendations(self) -> List[Dict[str, str]]:
        """
        Generate recommendations based on discovered vulnerabilities.
        
        Returns:
            List of recommendation dictionaries with 'title' and 'description' keys
        """
        # Standard recommendations
        recommendations = [
            {
                "title": "Implement HTTPS for All Authentication",
                "description": "Ensure that all authentication forms use HTTPS to encrypt credentials during transmission."
            },
            {
                "title": "Use WPA2/WPA3 Encryption",
                "description": "Secure wireless networks with WPA2 or WPA3 encryption to prevent unauthorized access and traffic interception."
            },
            {
                "title": "Implement Certificate Pinning",
                "description": "Use certificate pinning in captive portal implementations to prevent man-in-the-middle attacks."
            },
            {
                "title": "Regular Security Audits",
                "description": "Conduct regular security audits of wireless infrastructure and captive portal implementations."
            },
            {
                "title": "Secure User Data Storage",
                "description": "Ensure any user data collected through captive portals is stored securely and in compliance with relevant regulations."
            }
        ]
        
        return recommendations
    
    def schedule_report(
        self,
        title: str,
        description: str,
        schedule: str,
        report_format: str = "pdf",
        template_name: Optional[str] = None,
        custom_template_path: Optional[str] = None,
        network_ids: Optional[List[int]] = None,
        include_vulnerability_assessment: bool = True,
        include_recommendations: bool = True,
        output_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Schedule a recurring report.
        
        Args:
            title: Report title
            description: Report description
            schedule: Cron-style schedule string
            report_format: Report format ('pdf' or 'html')
            template_name: Name of built-in template to use (if not using custom)
            custom_template_path: Path to custom template (if not using built-in)
            network_ids: Optional list of network IDs to include
            include_vulnerability_assessment: Whether to include vulnerability assessment data
            include_recommendations: Whether to include recommendations
            output_dir: Optional output directory (defaults to reports_dir from config)
            
        Returns:
            Dictionary with scheduled report information
        """
        from apscheduler.triggers.cron import CronTrigger
        from apscheduler.schedulers.background import BackgroundScheduler
        
        # Create scheduler if it doesn't exist
        if not hasattr(self, 'scheduler'):
            self.scheduler = BackgroundScheduler()
            self.scheduler.start()
        
        # Parse cron string
        parts = schedule.strip().split()
        if len(parts) < 5:
            raise ValueError("Invalid cron schedule format. Expected: minute hour day_of_month month day_of_week")
        
        trigger = CronTrigger(
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4]
        )
        
        # Create report job info
        report_job = {
            "id": len(self.scheduled_reports) + 1,
            "title": title,
            "description": description,
            "schedule": schedule,
            "report_format": report_format,
            "template_name": template_name,
            "custom_template_path": custom_template_path,
            "network_ids": network_ids,
            "include_vulnerability_assessment": include_vulnerability_assessment,
            "include_recommendations": include_recommendations,
            "output_dir": output_dir or self.reports_dir,
            "created_at": datetime.datetime.now(),
            "last_run": None,
            "job_id": None
        }
        
        # Schedule the job
        job = self.scheduler.add_job(
            self._generate_scheduled_report,
            trigger=trigger,
            args=[report_job],
            id=f"report_{report_job['id']}"
        )
        
        report_job["job_id"] = job.id
        self.scheduled_reports.append(report_job)
        
        logger.info(f"Scheduled report '{title}' with ID {report_job['id']} and schedule '{schedule}'")
        return report_job
    
    def _generate_scheduled_report(self, report_job: Dict[str, Any]) -> str:
        """
        Generate a scheduled report.
        
        Args:
            report_job: Dictionary with report job information
            
        Returns:
            Path to the generated report
        """
        try:
            logger.info(f"Generating scheduled report: {report_job['title']}")
            
            # Generate the report
            report_path = self.generate_report(
                title=report_job['title'],
                description=report_job['description'],
                report_format=report_job['report_format'],
                template_name=report_job['template_name'],
                custom_template_path=report_job['custom_template_path'],
                network_ids=report_job['network_ids'],
                include_vulnerability_assessment=report_job['include_vulnerability_assessment'],
                include_recommendations=report_job['include_recommendations'],
                output_dir=report_job['output_dir']
            )
            
            # Update last run timestamp
            for job in self.scheduled_reports:
                if job["id"] == report_job["id"]:
                    job["last_run"] = datetime.datetime.now()
                    break
            
            logger.info(f"Scheduled report generated: {report_path}")
            return report_path
            
        except Exception as e:
            logger.error(f"Failed to generate scheduled report: {str(e)}")
            raise
    
    def get_scheduled_reports(self) -> List[Dict[str, Any]]:
        """
        Get all scheduled reports.
        
        Returns:
            List of scheduled report dictionaries
        """
        return self.scheduled_reports
    
    def delete_scheduled_report(self, report_id: int) -> bool:
        """
        Delete a scheduled report.
        
        Args:
            report_id: ID of the scheduled report to delete
            
        Returns:
            True if successful, False otherwise
        """
        for i, job in enumerate(self.scheduled_reports):
            if job["id"] == report_id:
                if hasattr(self, 'scheduler') and job["job_id"]:
                    try:
                        self.scheduler.remove_job(job["job_id"])
                    except Exception as e:
                        logger.error(f"Failed to remove scheduled job: {str(e)}")
                
                del self.scheduled_reports[i]
                logger.info(f"Deleted scheduled report with ID {report_id}")
                return True
        
        logger.warning(f"Scheduled report with ID {report_id} not found")
        return False
    
    def stop(self) -> None:
        """
        Stop the report manager and scheduler.
        """
        if hasattr(self, 'scheduler'):
            self.scheduler.shutdown()
            logger.info("Report scheduler stopped") 