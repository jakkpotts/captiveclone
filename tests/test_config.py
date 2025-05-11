"""
Tests for the configuration module.
"""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from captiveclone.utils.config import Config, DEFAULT_CONFIG


def test_config_defaults():
    """Test that default configuration is used when no file exists."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = os.path.join(temp_dir, "test_config.yaml")
        config = Config(config_path)
        
        # Check that default values are used
        assert config.get("scan.timeout") == DEFAULT_CONFIG["scan"]["timeout"]
        assert config.get("hardware.adapters.preferred") == DEFAULT_CONFIG["hardware"]["adapters"]["preferred"]
        
        # Check that the config file was created
        assert os.path.exists(config_path)


def test_config_load():
    """Test loading configuration from file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = os.path.join(temp_dir, "test_config.yaml")
        
        # Create a test configuration file
        test_config = {
            "scan": {
                "timeout": 120,
                "interfaces": {
                    "primary": "wlan0"
                }
            }
        }
        
        with open(config_path, "w") as f:
            yaml.dump(test_config, f)
        
        # Load the configuration
        config = Config(config_path)
        
        # Check that values from file are used
        assert config.get("scan.timeout") == 120
        assert config.get("scan.interfaces.primary") == "wlan0"
        
        # Check that default values are used for missing keys
        assert config.get("hardware.adapters.preferred") == DEFAULT_CONFIG["hardware"]["adapters"]["preferred"]


def test_config_get_set():
    """Test getting and setting configuration values."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = os.path.join(temp_dir, "test_config.yaml")
        config = Config(config_path)
        
        # Test setting a value
        config.set("scan.timeout", 120)
        assert config.get("scan.timeout") == 120
        
        # Test setting a nested value that doesn't exist yet
        config.set("new.nested.value", "test")
        assert config.get("new.nested.value") == "test"
        
        # Test default value for non-existent key
        assert config.get("non.existent.key", "default") == "default"
        
        # Check that changes were saved to file
        with open(config_path, "r") as f:
            saved_config = yaml.safe_load(f)
        
        assert saved_config["scan"]["timeout"] == 120
        assert saved_config["new"]["nested"]["value"] == "test"


def test_config_convenience_methods():
    """Test convenience methods for commonly accessed configuration values."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = os.path.join(temp_dir, "test_config.yaml")
        
        # Create a test configuration file
        test_config = {
            "scan": {
                "timeout": 120,
                "interfaces": {
                    "primary": "wlan0",
                    "secondary": "wlan1"
                }
            },
            "logging": {
                "level": "DEBUG"
            },
            "database": {
                "path": "test.db"
            }
        }
        
        with open(config_path, "w") as f:
            yaml.dump(test_config, f)
        
        # Load the configuration
        config = Config(config_path)
        
        # Test convenience methods
        assert config.get_scan_timeout() == 120
        assert config.get_primary_interface() == "wlan0"
        assert config.get_secondary_interface() == "wlan1"
        assert config.get_log_level() == "DEBUG"
        assert config.get_database_path() == "test.db" 