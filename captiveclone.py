#!/usr/bin/env python3
"""
CaptiveClone - A network security assessment tool for captive portal analysis
For authorized security testing only.
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('captiveclone.log')
    ]
)

logger = logging.getLogger('captiveclone')

# Import modules after logging setup
try:
    from captiveclone.interface.terminal import TerminalUI
    from captiveclone.core.scanner import NetworkScanner
    from captiveclone.utils.config import Config
except ImportError as e:
    logger.critical(f"Failed to import required modules: {e}")
    logger.critical("Please make sure you have installed all dependencies: pip install -r requirements.txt")
    sys.exit(1)

def check_root():
    """Check if the script is running with root privileges"""
    if os.geteuid() != 0:
        logger.critical("This tool requires root privileges to interact with wireless interfaces")
        logger.critical("Please run with 'sudo python captiveclone.py'")
        return False
    return True

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="CaptiveClone - A network security assessment tool for captive portal analysis"
    )
    parser.add_argument('-c', '--config', type=str, help='Path to config file')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')
    parser.add_argument('-d', '--debug', action='store_true', help='Enable debug mode')
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Scan command
    scan_parser = subparsers.add_parser('scan', help='Scan for networks with captive portals')
    scan_parser.add_argument('-i', '--interface', type=str, help='Wireless interface to use')
    scan_parser.add_argument('-t', '--timeout', type=int, default=60, help='Scan timeout in seconds')
    
    # Interactive mode (default)
    interactive_parser = subparsers.add_parser('interactive', help='Start interactive terminal UI')
    
    return parser.parse_args()

def main():
    """Main entry point for CaptiveClone"""
    logger.info("Starting CaptiveClone...")
    
    # Check for root privileges
    if not check_root():
        sys.exit(1)
    
    # Parse arguments
    args = parse_arguments()
    
    # Set log level based on arguments
    if args.debug:
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled")
    elif args.verbose:
        logger.setLevel(logging.INFO)
    
    # Load configuration
    config_path = args.config if args.config else "config.yaml"
    config = Config(config_path)
    
    # Run in specified mode
    if args.command == 'scan':
        scanner = NetworkScanner(interface=args.interface, timeout=args.timeout)
        networks = scanner.scan()
        for network in networks:
            print(f"Network: {network.ssid}, Channel: {network.channel}, Captive Portal: {'Yes' if network.has_captive_portal else 'No'}")
    elif args.command == 'interactive' or not args.command:
        # Default to interactive mode
        terminal_ui = TerminalUI(config)
        terminal_ui.start()
    
    logger.info("CaptiveClone terminated")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Program interrupted by user")
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}", exc_info=True)
    finally:
        sys.exit(0) 