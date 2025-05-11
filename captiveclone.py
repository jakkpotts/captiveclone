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
    from captiveclone.interface.web import WebInterface
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
    
    # Interactive mode
    interactive_parser = subparsers.add_parser('interactive', help='Start interactive terminal UI')
    
    # Web interface mode
    web_parser = subparsers.add_parser('web', help='Start web interface')
    web_parser.add_argument('-H', '--host', type=str, default='127.0.0.1', help='Host address to bind to')
    web_parser.add_argument('-p', '--port', type=int, default=5000, help='Port to listen on')
    
    # Analyze portal
    analyze_parser = subparsers.add_parser('analyze', help='Analyze a captive portal')
    analyze_parser.add_argument('url', type=str, help='URL of the captive portal')
    
    # Clone portal
    clone_parser = subparsers.add_parser('clone', help='Clone a captive portal')
    clone_parser.add_argument('url', type=str, help='URL of the captive portal')
    clone_parser.add_argument('-o', '--output', type=str, help='Name for the output directory')
    
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
    
    elif args.command == 'analyze':
        try:
            from captiveclone.core.portal_analyzer import PortalAnalyzer
            analyzer = PortalAnalyzer()
            portal = analyzer.analyze_portal(args.url)
            print(f"Portal analysis complete for {args.url}")
            print(f"Authentication required: {portal.requires_authentication}")
            if portal.form_fields:
                print("Form fields detected:")
                for form_id, fields in portal.form_fields.items():
                    print(f"  Form {form_id}:")
                    for field_name, field_info in fields.items():
                        print(f"    {field_name}: {field_info.get('type', 'unknown')}")
        except Exception as e:
            logger.error(f"Error analyzing portal: {str(e)}")
            sys.exit(1)
    
    elif args.command == 'clone':
        try:
            from captiveclone.core.portal_cloner import PortalCloner
            cloner = PortalCloner()
            clone_dir = cloner.clone_portal(args.url, output_name=args.output)
            print(f"Portal clone generated at: {clone_dir}")
        except Exception as e:
            logger.error(f"Error cloning portal: {str(e)}")
            sys.exit(1)
    
    elif args.command == 'web':
        web_ui = WebInterface(config, host=args.host, port=args.port)
        logger.info(f"Starting web interface on {args.host}:{args.port}")
        try:
            web_ui.start()
        except KeyboardInterrupt:
            logger.info("Web interface stopped by user")
    
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