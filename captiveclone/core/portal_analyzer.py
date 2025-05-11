"""
Captive Portal Analyzer Module for CaptiveClone.

This module is responsible for analyzing captive portals, extracting assets,
and mapping form fields and API calls.
"""

import logging
import os
import re
import time
import json
import urllib.parse
from typing import Dict, List, Optional, Tuple, Set, Any
from dataclasses import dataclass, field
import hashlib
import base64
from pathlib import Path

import requests
from bs4 import BeautifulSoup
import selenium
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from captiveclone.core.models import CaptivePortal, WirelessNetwork
from captiveclone.utils.exceptions import CaptivePortalError

logger = logging.getLogger(__name__)

# Constants
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36"
DOWNLOAD_TIMEOUT = 10  # seconds
BROWSER_LOAD_TIMEOUT = 15  # seconds
ASSET_DIR = "assets"


@dataclass
class PortalAsset:
    """Represents an asset from a captive portal."""
    url: str
    asset_type: str  # 'html', 'css', 'js', 'image', etc.
    content: Optional[bytes] = None
    content_hash: Optional[str] = None
    local_path: Optional[str] = None
    
    def compute_hash(self) -> str:
        """Compute a hash of the asset content."""
        if not self.content:
            return ""
        return hashlib.sha256(self.content).hexdigest()
    
    def save_to_disk(self, base_dir: str) -> str:
        """
        Save the asset to disk.
        
        Args:
            base_dir: Base directory for saving assets
            
        Returns:
            Path to the saved file
        """
        if not self.content:
            raise ValueError("Cannot save asset with no content")
        
        # Create directory structure
        os.makedirs(base_dir, exist_ok=True)
        
        # Determine filename
        filename = os.path.basename(urllib.parse.urlparse(self.url).path)
        if not filename:
            # Generate a filename based on the URL and content hash
            url_hash = hashlib.md5(self.url.encode()).hexdigest()[:8]
            ext = self._get_extension_for_type()
            filename = f"{self.asset_type}_{url_hash}{ext}"
        
        # Ensure filename is valid
        filename = re.sub(r'[^\w\-.]', '_', filename)
        
        # Save the file
        filepath = os.path.join(base_dir, filename)
        with open(filepath, 'wb') as f:
            f.write(self.content)
        
        self.local_path = filepath
        return filepath
    
    def _get_extension_for_type(self) -> str:
        """Get the file extension based on asset type."""
        extensions = {
            'html': '.html',
            'css': '.css',
            'js': '.js',
            'image': '.png',  # Default, will be overridden if determined from URL
            'font': '.woff',
            'json': '.json',
        }
        
        # Check URL for extension
        url_path = urllib.parse.urlparse(self.url).path
        if '.' in url_path:
            ext = os.path.splitext(url_path)[1]
            if ext:
                return ext
        
        return extensions.get(self.asset_type, '.bin')


class PortalAnalyzer:
    """Analyzes captive portals and extracts information."""
    
    def __init__(self, output_dir: str = "./portal_assets"):
        """
        Initialize the portal analyzer.
        
        Args:
            output_dir: Directory to store downloaded assets
        """
        self.output_dir = output_dir
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})
        self.driver = None
        self.assets: Dict[str, PortalAsset] = {}  # URL -> Asset
        
    def analyze_portal(self, portal_url: str) -> CaptivePortal:
        """
        Analyze a captive portal.
        
        Args:
            portal_url: URL of the captive portal
            
        Returns:
            CaptivePortal object with analysis results
        """
        logger.info(f"Analyzing captive portal at URL: {portal_url}")
        
        # Create a network object (in a real implementation, this would be passed in)
        network = WirelessNetwork(
            ssid="CaptivePortalNetwork",
            bssid="00:11:22:33:44:55",
            has_captive_portal=True
        )
        
        # Initialize captive portal object
        portal = CaptivePortal(
            network=network,
            login_url=portal_url
        )
        
        try:
            # Extract portal information using both requests and selenium
            self._setup_browser()
            page_info = self._analyze_page(portal_url)
            
            # Extract forms and determine if authentication is required
            forms = self._extract_forms(page_info['soup'])
            requires_auth = self._check_requires_auth(forms, page_info['soup'])
            
            # Update portal object
            portal.requires_authentication = requires_auth
            portal.form_fields = self._convert_forms_to_dict(forms)
            
            # Download and catalog assets
            assets_dir = os.path.join(self.output_dir, self._get_safe_domain(portal_url))
            self._download_assets(portal_url, page_info['assets'], assets_dir)
            
            logger.info(f"Portal analysis complete. Auth required: {requires_auth}, Assets: {len(self.assets)}")
            
            return portal
            
        except Exception as e:
            logger.error(f"Error analyzing portal: {str(e)}")
            raise CaptivePortalError(f"Failed to analyze portal at {portal_url}: {str(e)}")
        
        finally:
            self._teardown_browser()
    
    def _setup_browser(self) -> None:
        """Set up the Selenium WebDriver."""
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument(f"--user-agent={USER_AGENT}")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-dev-shm-usage")
            
            # Use chromedriver
            self.driver = webdriver.Chrome(options=chrome_options)
            
            logger.debug("Browser set up successfully")
        except Exception as e:
            logger.error(f"Failed to set up browser: {str(e)}")
            raise CaptivePortalError(f"Browser setup failed: {str(e)}")
    
    def _teardown_browser(self) -> None:
        """Clean up the Selenium WebDriver."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                logger.warning(f"Error closing browser: {str(e)}")
            finally:
                self.driver = None
    
    def _analyze_page(self, url: str) -> Dict[str, Any]:
        """
        Analyze a web page.
        
        Args:
            url: URL to analyze
            
        Returns:
            Dictionary with page information
        """
        # First, get the page using requests
        try:
            response = self.session.get(url, timeout=DOWNLOAD_TIMEOUT)
            soup = BeautifulSoup(response.text, 'html.parser')
        except requests.RequestException as e:
            logger.error(f"Error fetching page with requests: {str(e)}")
            raise CaptivePortalError(f"Failed to fetch page: {str(e)}")
        
        # Then, load the page with Selenium for JavaScript execution
        if self.driver:
            try:
                self.driver.get(url)
                WebDriverWait(self.driver, BROWSER_LOAD_TIMEOUT).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                
                # Get the rendered HTML
                rendered_html = self.driver.page_source
                rendered_soup = BeautifulSoup(rendered_html, 'html.parser')
                
                # Check for redirects
                final_url = self.driver.current_url
                
                # Take a screenshot
                screenshot_path = os.path.join(self.output_dir, "portal_screenshot.png")
                os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
                self.driver.save_screenshot(screenshot_path)
                
            except (TimeoutException, WebDriverException) as e:
                logger.warning(f"Error loading page with Selenium: {str(e)}")
                # Fall back to requests data
                final_url = response.url
                rendered_soup = soup
        else:
            # If no driver, use requests data
            rendered_soup = soup
            final_url = response.url
        
        # Extract assets
        assets = self._extract_assets(rendered_soup, final_url)
        
        return {
            'url': final_url,
            'original_url': url,
            'soup': rendered_soup,
            'status_code': response.status_code if hasattr(response, 'status_code') else None,
            'headers': dict(response.headers) if hasattr(response, 'headers') else {},
            'assets': assets
        }
    
    def _extract_assets(self, soup: BeautifulSoup, base_url: str) -> List[PortalAsset]:
        """
        Extract assets from a web page.
        
        Args:
            soup: BeautifulSoup object of the page
            base_url: Base URL for resolving relative URLs
            
        Returns:
            List of assets
        """
        assets = []
        
        # Helper to create absolute URLs
        def make_absolute(url: str) -> str:
            if not url or url.startswith('data:'):
                return url
            return urllib.parse.urljoin(base_url, url)
        
        # Extract CSS files
        for link in soup.find_all('link', rel='stylesheet'):
            href = link.get('href')
            if href:
                assets.append(PortalAsset(
                    url=make_absolute(href),
                    asset_type='css'
                ))
        
        # Extract JavaScript files
        for script in soup.find_all('script', src=True):
            src = script.get('src')
            if src:
                assets.append(PortalAsset(
                    url=make_absolute(src),
                    asset_type='js'
                ))
        
        # Extract images
        for img in soup.find_all('img', src=True):
            src = img.get('src')
            if src and not src.startswith('data:'):
                assets.append(PortalAsset(
                    url=make_absolute(src),
                    asset_type='image'
                ))
        
        # Extract background images from inline styles
        for element in soup.find_all(style=True):
            style = element.get('style', '')
            urls = re.findall(r'url\([\'"]?([^\'")]+)[\'"]?\)', style)
            for url in urls:
                if not url.startswith('data:'):
                    assets.append(PortalAsset(
                        url=make_absolute(url),
                        asset_type='image'
                    ))
        
        # Extract font files
        for link in soup.find_all('link', rel='preload'):
            if link.get('as') == 'font' and link.get('href'):
                assets.append(PortalAsset(
                    url=make_absolute(link.get('href')),
                    asset_type='font'
                ))
        
        # Extract favicon
        for link in soup.find_all('link', rel=lambda x: x and ('icon' in x.lower())):
            href = link.get('href')
            if href:
                assets.append(PortalAsset(
                    url=make_absolute(href),
                    asset_type='image'
                ))
        
        return assets
    
    def _download_assets(self, base_url: str, assets: List[PortalAsset], output_dir: str) -> None:
        """
        Download assets and store them locally.
        
        Args:
            base_url: Base URL for resolving relative URLs
            assets: List of assets to download
            output_dir: Directory to save assets to
        """
        logger.info(f"Downloading {len(assets)} assets to {output_dir}")
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Also save the main HTML
        if base_url not in self.assets:
            try:
                response = self.session.get(base_url, timeout=DOWNLOAD_TIMEOUT)
                html_asset = PortalAsset(
                    url=base_url,
                    asset_type='html',
                    content=response.content
                )
                html_asset.content_hash = html_asset.compute_hash()
                html_asset.save_to_disk(output_dir)
                self.assets[base_url] = html_asset
            except Exception as e:
                logger.warning(f"Error downloading main HTML from {base_url}: {str(e)}")
        
        # Download other assets
        for asset in assets:
            if asset.url in self.assets:
                continue  # Already downloaded
            
            try:
                # Skip data: URLs
                if asset.url.startswith('data:'):
                    continue
                
                # Skip invalid URLs
                try:
                    urllib.parse.urlparse(asset.url)
                except Exception:
                    logger.warning(f"Invalid URL: {asset.url}")
                    continue
                
                # Download the asset
                response = self.session.get(asset.url, timeout=DOWNLOAD_TIMEOUT)
                
                # Store the content
                asset.content = response.content
                asset.content_hash = asset.compute_hash()
                
                # Save to disk
                asset.save_to_disk(output_dir)
                
                # Store in assets dictionary
                self.assets[asset.url] = asset
                
                logger.debug(f"Downloaded asset: {asset.url}")
                
            except Exception as e:
                logger.warning(f"Error downloading asset {asset.url}: {str(e)}")
    
    def _extract_forms(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """
        Extract forms from a web page.
        
        Args:
            soup: BeautifulSoup object of the page
            
        Returns:
            List of form dictionaries
        """
        forms = []
        
        for form in soup.find_all('form'):
            form_data = {
                'action': form.get('action', ''),
                'method': form.get('method', 'get').upper(),
                'id': form.get('id', ''),
                'name': form.get('name', ''),
                'fields': []
            }
            
            # Extract input fields
            for field in form.find_all(['input', 'select', 'textarea']):
                field_type = field.name
                
                if field_type == 'input':
                    field_type = field.get('type', 'text')
                
                field_data = {
                    'type': field_type,
                    'name': field.get('name', ''),
                    'id': field.get('id', ''),
                    'value': field.get('value', ''),
                    'placeholder': field.get('placeholder', ''),
                    'required': field.has_attr('required')
                }
                
                form_data['fields'].append(field_data)
            
            forms.append(form_data)
        
        return forms
    
    def _check_requires_auth(self, forms: List[Dict[str, Any]], soup: BeautifulSoup) -> bool:
        """
        Check if the page requires authentication.
        
        Args:
            forms: List of forms extracted from the page
            soup: BeautifulSoup object of the page
            
        Returns:
            True if the page likely requires authentication, False otherwise
        """
        # Look for password fields in forms
        for form in forms:
            for field in form['fields']:
                if field['type'] == 'password':
                    return True
        
        # Look for other common authentication indicators
        auth_keywords = ['login', 'signin', 'password', 'username', 'credentials']
        
        page_text = soup.get_text().lower()
        for keyword in auth_keywords:
            if keyword in page_text:
                return True
        
        return False
    
    def _convert_forms_to_dict(self, forms: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Convert forms list to a simplified dictionary for storage.
        
        Args:
            forms: List of forms extracted from the page
            
        Returns:
            Dictionary representation of forms
        """
        result = {}
        
        for i, form in enumerate(forms):
            form_id = form.get('id') or form.get('name') or f"form_{i}"
            form_fields = {}
            
            for field in form['fields']:
                field_name = field.get('name') or field.get('id') or f"field_{len(form_fields)}"
                form_fields[field_name] = {
                    'type': field['type'],
                    'required': field['required']
                }
            
            result[form_id] = {
                'action': form['action'],
                'method': form['method'],
                'fields': form_fields
            }
        
        return result
    
    def _get_safe_domain(self, url: str) -> str:
        """
        Get a safe directory name from a URL.
        
        Args:
            url: URL to convert
            
        Returns:
            Safe string for use as a directory name
        """
        try:
            parsed = urllib.parse.urlparse(url)
            domain = parsed.netloc
            if not domain:
                # Handle invalid or local URLs
                return "local_portal"
            return re.sub(r'[^\w\-]', '_', domain)
        except Exception:
            return "unknown_portal" 