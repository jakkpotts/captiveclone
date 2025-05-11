"""
Configuration utility for CaptiveClone.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from dotenv import load_dotenv

from captiveclone.utils.exceptions import ConfigError

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_CONFIG = {
    "scan": {
        "timeout": 60,
        "interfaces": {
            "primary": None,
            "secondary": None
        },
        "detect_captive_portals": True
    },
    "hardware": {
        "adapters": {
            "preferred": ["wlan0", "wlan1"]
        }
    },
    "interface": {
        "color": True,
        "verbose": False
    },
    "database": {
        "path": "captiveclone.db"
    },
    "logging": {
        "level": "INFO",
        "file": "captiveclone.log"
    }
}


class Config:
    """
    Configuration manager for CaptiveClone.
    
    This class handles loading, validating, and accessing configuration settings.
    """
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        Initialize configuration manager.
        
        Args:
            config_path: Path to the configuration file
        """
        self.config_path = config_path
        self.config = DEFAULT_CONFIG.copy()
        
        # Load environment variables
        load_dotenv()
        
        # Try to load configuration file
        self._load_config()
        
        logger.debug("Configuration loaded successfully")
    
    def _load_config(self) -> None:
        """
        Load configuration from file.
        
        If the file doesn't exist, a default configuration will be created.
        """
        config_file = Path(self.config_path)
        
        if not config_file.exists():
            logger.warning(f"Configuration file '{self.config_path}' not found, using defaults")
            self._save_config()
            return
        
        try:
            with open(config_file, "r") as f:
                user_config = yaml.safe_load(f)
            
            if user_config:
                # Merge user config with defaults (this is a simple recursive merge)
                self._merge_configs(self.config, user_config)
            
            logger.debug(f"Loaded configuration from '{self.config_path}'")
        
        except Exception as e:
            logger.error(f"Error loading configuration from '{self.config_path}': {str(e)}")
            logger.warning("Using default configuration")
    
    def _merge_configs(self, base: Dict[str, Any], overlay: Dict[str, Any]) -> None:
        """
        Recursively merge overlay configuration into base configuration.
        
        Args:
            base: Base configuration dictionary (modified in place)
            overlay: Overlay configuration dictionary
        """
        for key, value in overlay.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_configs(base[key], value)
            else:
                base[key] = value
    
    def _save_config(self) -> None:
        """Save the current configuration to file."""
        config_file = Path(self.config_path)
        
        try:
            # Create parent directories if they don't exist
            config_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(config_file, "w") as f:
                yaml.dump(self.config, f, default_flow_style=False)
            
            logger.debug(f"Saved configuration to '{self.config_path}'")
        
        except Exception as e:
            logger.error(f"Error saving configuration to '{self.config_path}': {str(e)}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.
        
        Args:
            key: Configuration key (can be nested, separated by dots)
            default: Default value if the key doesn't exist
            
        Returns:
            Configuration value, or default if the key doesn't exist
        """
        keys = key.split(".")
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value.
        
        Args:
            key: Configuration key (can be nested, separated by dots)
            value: Value to set
        """
        keys = key.split(".")
        config = self.config
        
        # Navigate to the parent of the key to set
        for i, k in enumerate(keys[:-1]):
            if k not in config:
                config[k] = {}
            elif not isinstance(config[k], dict):
                # If the key exists but is not a dict, make it a dict
                config[k] = {}
            
            config = config[k]
        
        # Set the value
        config[keys[-1]] = value
        
        # Save the updated configuration
        self._save_config()
    
    def get_scan_timeout(self) -> int:
        """
        Get the scan timeout in seconds.
        
        Returns:
            Scan timeout in seconds
        """
        return int(self.get("scan.timeout", 60))
    
    def get_primary_interface(self) -> Optional[str]:
        """
        Get the primary interface name.
        
        Returns:
            Primary interface name, or None if not configured
        """
        return self.get("scan.interfaces.primary")
    
    def get_secondary_interface(self) -> Optional[str]:
        """
        Get the secondary interface name.
        
        Returns:
            Secondary interface name, or None if not configured
        """
        return self.get("scan.interfaces.secondary")
    
    def get_preferred_adapters(self) -> list:
        """
        Get the list of preferred adapter names.
        
        Returns:
            List of preferred adapter names
        """
        return self.get("hardware.adapters.preferred", ["wlan0", "wlan1"])
    
    def get_log_level(self) -> str:
        """
        Get the logging level.
        
        Returns:
            Logging level
        """
        return self.get("logging.level", "INFO")
    
    def get_database_path(self) -> str:
        """
        Get the database path.
        
        Returns:
            Database path
        """
        return self.get("database.path", "captiveclone.db") 