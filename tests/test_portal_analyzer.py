"""
Tests for the PortalAnalyzer class.
"""

import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import tempfile
import shutil

from bs4 import BeautifulSoup
import requests
from selenium.webdriver.support.ui import WebDriverWait

from captiveclone.core.portal_analyzer import PortalAnalyzer, PortalAsset
from captiveclone.utils.exceptions import CaptivePortalError


class TestPortalAsset(unittest.TestCase):
    """Test cases for the PortalAsset class."""
    
    def test_compute_hash(self):
        """Test hash computation for an asset."""
        content = b'test content'
        asset = PortalAsset(url='http://example.com/test.js', asset_type='js', content=content)
        
        hash_value = asset.compute_hash()
        
        # Verify the hash is a non-empty string
        self.assertTrue(hash_value)
        self.assertIsInstance(hash_value, str)
    
    def test_get_extension_for_type(self):
        """Test extension determination based on asset type."""
        # Test with URL that has an extension
        asset1 = PortalAsset(url='http://example.com/test.jpg', asset_type='image')
        self.assertEqual(asset1._get_extension_for_type(), '.jpg')
        
        # Test with URL that has no extension
        asset2 = PortalAsset(url='http://example.com/image', asset_type='image')
        self.assertEqual(asset2._get_extension_for_type(), '.png')  # Default for image
        
        # Test with other asset types
        asset3 = PortalAsset(url='http://example.com/style', asset_type='css')
        self.assertEqual(asset3._get_extension_for_type(), '.css')
    
    @patch('os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    def test_save_to_disk(self, mock_file, mock_makedirs):
        """Test saving an asset to disk."""
        content = b'test content'
        asset = PortalAsset(
            url='http://example.com/test.js',
            asset_type='js',
            content=content
        )
        
        filepath = asset.save_to_disk('/tmp/assets')
        
        # Verify directory creation
        mock_makedirs.assert_called_once_with('/tmp/assets', exist_ok=True)
        
        # Verify file writing
        mock_file.assert_called_once_with('/tmp/assets/test.js', 'wb')
        mock_file().write.assert_called_once_with(content)
        
        # Verify the local_path was set
        self.assertEqual(asset.local_path, '/tmp/assets/test.js')


class TestPortalAnalyzer(unittest.TestCase):
    """Test cases for the PortalAnalyzer class."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a temporary directory for test assets
        self.test_dir = tempfile.mkdtemp()
        self.analyzer = PortalAnalyzer(output_dir=self.test_dir)
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    def test_initialization(self):
        """Test analyzer initialization."""
        self.assertEqual(self.analyzer.output_dir, self.test_dir)
        self.assertIsNotNone(self.analyzer.session)
        self.assertIsNone(self.analyzer.driver)
        self.assertEqual(self.analyzer.assets, {})
    
    @patch('captiveclone.core.portal_analyzer.requests.Session')
    @patch('captiveclone.core.portal_analyzer.BeautifulSoup')
    def test_analyze_page_requests(self, mock_soup, mock_session):
        """Test analyze_page with requests."""
        # Mock session and response
        mock_session_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "<html><body><h1>Test Page</h1></body></html>"
        mock_response.status_code = 200
        mock_response.url = 'http://example.com/portal'
        mock_response.headers = {'Content-Type': 'text/html'}
        mock_session_instance.get.return_value = mock_response
        mock_session.return_value = mock_session_instance
        
        # Mock BeautifulSoup
        mock_soup_instance = MagicMock()
        mock_soup.return_value = mock_soup_instance
        
        # Replace session
        self.analyzer.session = mock_session_instance
        
        # Mock extract_assets
        with patch.object(self.analyzer, '_extract_assets', return_value=[]) as mock_extract:
            # Call analyze_page
            result = self.analyzer._analyze_page('http://example.com/portal')
            
            # Verify behavior
            mock_session_instance.get.assert_called_once_with('http://example.com/portal', timeout=10)
            mock_soup.assert_called_with(mock_response.text, 'html.parser')
            mock_extract.assert_called_once()
            
            # Check result
            self.assertEqual(result['url'], 'http://example.com/portal')
            self.assertEqual(result['original_url'], 'http://example.com/portal')
            self.assertEqual(result['status_code'], 200)
    
    @patch('captiveclone.core.portal_analyzer.selenium.webdriver')
    @patch('captiveclone.core.portal_analyzer.Options')
    @patch('captiveclone.core.portal_analyzer.BeautifulSoup')
    def test_setup_browser(self, mock_soup, mock_options, mock_webdriver):
        """Test browser setup."""
        # Mock driver
        mock_driver = MagicMock()
        mock_webdriver.Chrome.return_value = mock_driver
        
        # Mock options
        mock_options_instance = MagicMock()
        mock_options.return_value = mock_options_instance
        
        # Call setup_browser
        self.analyzer._setup_browser()
        
        # Verify driver initialization
        mock_webdriver.Chrome.assert_called_once()
        self.assertEqual(self.analyzer.driver, mock_driver)
        
        # Verify options
        mock_options_instance.add_argument.assert_any_call("--headless")
        mock_options_instance.add_argument.assert_any_call("--no-sandbox")
    
    @patch('captiveclone.core.portal_analyzer.BeautifulSoup')
    def test_extract_assets(self, mock_soup):
        """Test asset extraction from HTML."""
        # Create a simple HTML document
        html = """
        <html>
            <head>
                <link rel="stylesheet" href="style.css">
                <script src="script.js"></script>
                <link rel="icon" href="favicon.ico">
                <link rel="preload" as="font" href="font.woff">
            </head>
            <body>
                <img src="image.jpg">
                <div style="background: url('bg.png')"></div>
            </body>
        </html>
        """
        
        # Create soup
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extract assets
        assets = self.analyzer._extract_assets(soup, 'http://example.com')
        
        # Verify asset extraction
        self.assertEqual(len(assets), 6)  # CSS, JS, favicon, font, image, bg image
        
        # Check asset types
        asset_types = {asset.asset_type for asset in assets}
        self.assertEqual(asset_types, {'css', 'js', 'image', 'font'})
        
        # Check URLs
        asset_urls = {asset.url for asset in assets}
        expected_urls = {
            'http://example.com/style.css',
            'http://example.com/script.js',
            'http://example.com/favicon.ico',
            'http://example.com/font.woff',
            'http://example.com/image.jpg',
            'http://example.com/bg.png'
        }
        self.assertEqual(asset_urls, expected_urls)
    
    @patch('captiveclone.core.portal_analyzer.requests.Session')
    def test_download_assets(self, mock_session):
        """Test asset downloading."""
        # Mock session and response
        mock_session_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.content = b'test content'
        mock_session_instance.get.return_value = mock_response
        
        # Replace session
        self.analyzer.session = mock_session_instance
        
        # Create assets to download
        assets = [
            PortalAsset(url='http://example.com/test.js', asset_type='js'),
            PortalAsset(url='http://example.com/style.css', asset_type='css')
        ]
        
        # Mock PortalAsset methods
        with patch.object(PortalAsset, 'compute_hash', return_value='hash'), \
             patch.object(PortalAsset, 'save_to_disk', return_value='/tmp/assets/test.js'):
            
            # Download assets
            self.analyzer._download_assets('http://example.com', assets, '/tmp/assets')
            
            # Verify session get calls
            mock_session_instance.get.assert_any_call('http://example.com/test.js', timeout=10)
            mock_session_instance.get.assert_any_call('http://example.com/style.css', timeout=10)
            
            # Verify assets dict
            self.assertEqual(len(self.analyzer.assets), 3)  # 2 assets + main HTML
    
    def test_extract_forms(self):
        """Test form extraction from HTML."""
        # Create a simple HTML document with forms
        html = """
        <html>
            <body>
                <form id="login" action="/login" method="post">
                    <input type="text" name="username" placeholder="Username" required>
                    <input type="password" name="password" placeholder="Password">
                    <button type="submit">Login</button>
                </form>
                <form id="search" action="/search">
                    <input type="text" name="q">
                    <button>Search</button>
                </form>
            </body>
        </html>
        """
        
        # Create soup
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extract forms
        forms = self.analyzer._extract_forms(soup)
        
        # Verify form extraction
        self.assertEqual(len(forms), 2)
        
        # Check first form
        self.assertEqual(forms[0]['id'], 'login')
        self.assertEqual(forms[0]['action'], '/login')
        self.assertEqual(forms[0]['method'], 'POST')
        
        # Check form fields
        self.assertEqual(len(forms[0]['fields']), 2)
        self.assertEqual(forms[0]['fields'][0]['name'], 'username')
        self.assertEqual(forms[0]['fields'][0]['type'], 'text')
        self.assertTrue(forms[0]['fields'][0]['required'])
        self.assertEqual(forms[0]['fields'][1]['name'], 'password')
        self.assertEqual(forms[0]['fields'][1]['type'], 'password')
    
    def test_check_requires_auth(self):
        """Test authentication requirement detection."""
        # Create forms with password field
        forms_with_pass = [{
            'fields': [
                {'type': 'text', 'name': 'username'},
                {'type': 'password', 'name': 'password'}
            ]
        }]
        
        # Create forms without password field
        forms_without_pass = [{
            'fields': [
                {'type': 'text', 'name': 'name'},
                {'type': 'email', 'name': 'email'}
            ]
        }]
        
        # Create soup with login keywords
        soup_with_login = BeautifulSoup("<html><body>Please login to continue</body></html>", 'html.parser')
        
        # Create soup without login keywords
        soup_without_login = BeautifulSoup("<html><body>Please accept terms</body></html>", 'html.parser')
        
        # Test with password field
        self.assertTrue(self.analyzer._check_requires_auth(forms_with_pass, soup_without_login))
        
        # Test with login keywords
        self.assertTrue(self.analyzer._check_requires_auth(forms_without_pass, soup_with_login))
        
        # Test with neither
        self.assertFalse(self.analyzer._check_requires_auth(forms_without_pass, soup_without_login))
    
    def test_convert_forms_to_dict(self):
        """Test conversion of forms to dictionary."""
        # Create forms
        forms = [
            {
                'id': 'login',
                'action': '/login',
                'method': 'POST',
                'name': '',
                'fields': [
                    {
                        'type': 'text',
                        'name': 'username',
                        'id': '',
                        'value': '',
                        'placeholder': 'Username',
                        'required': True
                    },
                    {
                        'type': 'password',
                        'name': 'password',
                        'id': '',
                        'value': '',
                        'placeholder': 'Password',
                        'required': False
                    }
                ]
            }
        ]
        
        # Convert forms
        result = self.analyzer._convert_forms_to_dict(forms)
        
        # Verify conversion
        self.assertIn('login', result)
        self.assertEqual(result['login']['action'], '/login')
        self.assertEqual(result['login']['method'], 'POST')
        self.assertIn('username', result['login']['fields'])
        self.assertEqual(result['login']['fields']['username']['type'], 'text')
        self.assertTrue(result['login']['fields']['username']['required'])
        self.assertIn('password', result['login']['fields'])
        self.assertEqual(result['login']['fields']['password']['type'], 'password')
        self.assertFalse(result['login']['fields']['password']['required'])
    
    def test_get_safe_domain(self):
        """Test safe domain name generation."""
        # Test with normal URL
        self.assertEqual(
            self.analyzer._get_safe_domain('http://example.com/path'),
            'example_com'
        )
        
        # Test with invalid URL
        self.assertEqual(
            self.analyzer._get_safe_domain('not a url'),
            'local_portal'
        )


if __name__ == '__main__':
    unittest.main() 