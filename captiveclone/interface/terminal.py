"""
Terminal-based user interface for CaptiveClone.
"""

import logging
import sys
from typing import List, Dict, Any, Optional

from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from captiveclone.core.scanner import NetworkScanner
from captiveclone.core.models import WirelessNetwork
from captiveclone.utils.config import Config
from captiveclone.utils.exceptions import InterfaceError

logger = logging.getLogger(__name__)


class TerminalUI:
    """
    Terminal-based user interface for CaptiveClone.
    
    This class provides a simple text-based interface for interacting with the tool.
    """
    
    def __init__(self, config: Config):
        """
        Initialize the terminal UI.
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.console = Console()
        self.networks = []  # type: List[WirelessNetwork]
        self.scanner = None  # type: Optional[NetworkScanner]
        
        # Command system
        self.commands = {
            "help": self.cmd_help,
            "scan": self.cmd_scan,
            "list": self.cmd_list,
            "info": self.cmd_info,
            "set": self.cmd_set,
            "interfaces": self.cmd_interfaces,
            "exit": self.cmd_exit,
            "quit": self.cmd_exit
        }
        
        self.command_completer = WordCompleter(list(self.commands.keys()))
        
        # Prompt style
        self.style = Style.from_dict({
            'prompt': 'ansigreen bold',
        })
    
    def start(self) -> None:
        """Start the terminal UI."""
        self._print_banner()
        
        try:
            while True:
                user_input = prompt(
                    HTML('<ansigreen>captiveclone&gt;</ansigreen> '),
                    completer=self.command_completer,
                    style=self.style
                ).strip()
                
                if not user_input:
                    continue
                
                # Parse command and arguments
                parts = user_input.split(" ")
                command = parts[0].lower()
                args = parts[1:] if len(parts) > 1 else []
                
                # Execute command
                if command in self.commands:
                    self.commands[command](args)
                else:
                    self.console.print(f"[bold red]Unknown command: {command}[/bold red]")
                    self.console.print("Type 'help' to see available commands.")
        
        except KeyboardInterrupt:
            logger.info("Terminal UI interrupted")
            self.console.print("\n[bold yellow]Interrupted by user[/bold yellow]")
        
        except Exception as e:
            logger.error(f"Error in terminal UI: {str(e)}", exc_info=True)
            self.console.print(f"[bold red]Error: {str(e)}[/bold red]")
        
        finally:
            self.console.print("[bold green]Goodbye![/bold green]")
    
    def _print_banner(self) -> None:
        """Print the CaptiveClone banner."""
        banner = """
 ██████╗ █████╗ ██████╗ ████████╗██╗██╗   ██╗███████╗ ██████╗██╗      ██████╗ ███╗   ██╗███████╗
██╔════╝██╔══██╗██╔══██╗╚══██╔══╝██║██║   ██║██╔════╝██╔════╝██║     ██╔═══██╗████╗  ██║██╔════╝
██║     ███████║██████╔╝   ██║   ██║██║   ██║█████╗  ██║     ██║     ██║   ██║██╔██╗ ██║█████╗  
██║     ██╔══██║██╔═══╝    ██║   ██║╚██╗ ██╔╝██╔══╝  ██║     ██║     ██║   ██║██║╚██╗██║██╔══╝  
╚██████╗██║  ██║██║        ██║   ██║ ╚████╔╝ ███████╗╚██████╗███████╗╚██████╔╝██║ ╚████║███████╗
 ╚═════╝╚═╝  ╚═╝╚═╝        ╚═╝   ╚═╝  ╚═══╝  ╚══════╝ ╚═════╝╚══════╝ ╚═════╝ ╚═╝  ╚═══╝╚══════╝
 """
        self.console.print(banner, style="bold blue")
        self.console.print("[bold yellow]LEGAL DISCLAIMER:[/bold yellow] This tool is intended ONLY for authorized security testing with proper written permission.")
        self.console.print("[bold red]Unauthorized use against networks without explicit consent is illegal in most jurisdictions.[/bold red]\n")
        self.console.print("Type 'help' to see available commands.\n")
    
    def cmd_help(self, args: List[str]) -> None:
        """
        Show help information.
        
        Args:
            args: Command arguments
        """
        table = Table(title="Available Commands")
        table.add_column("Command", style="cyan")
        table.add_column("Description", style="green")
        table.add_column("Usage", style="yellow")
        
        commands_help = {
            "help": ("Show this help information", "help"),
            "scan": ("Scan for wireless networks", "scan [interface] [timeout]"),
            "list": ("List discovered networks", "list"),
            "info": ("Show detailed information about a network", "info <network_index>"),
            "set": ("Set a configuration value", "set <key> <value>"),
            "interfaces": ("List available wireless interfaces", "interfaces"),
            "exit": ("Exit the program", "exit or quit")
        }
        
        for cmd, (desc, usage) in commands_help.items():
            table.add_row(cmd, desc, usage)
        
        self.console.print(table)
    
    def cmd_scan(self, args: List[str]) -> None:
        """
        Scan for wireless networks.
        
        Args:
            args: Command arguments (optional interface and timeout)
        """
        interface = None
        timeout = self.config.get_scan_timeout()
        
        if len(args) >= 1:
            interface = args[0]
        
        if len(args) >= 2:
            try:
                timeout = int(args[1])
            except ValueError:
                self.console.print("[bold red]Invalid timeout value. Using default.[/bold red]")
        
        self.console.print(f"[bold green]Starting network scan{'...' if not interface else f' on interface {interface}...'}[/bold green]")
        
        try:
            self.scanner = NetworkScanner(interface=interface, timeout=timeout)
            
            with self.console.status("[bold blue]Scanning for networks...[/bold blue]", spinner="dots"):
                self.networks = self.scanner.scan()
            
            self.console.print(f"[bold green]Scan complete. Found {len(self.networks)} networks.[/bold green]")
            
            # Display networks
            self._display_networks()
        
        except InterfaceError as e:
            self.console.print(f"[bold red]Interface error: {str(e)}[/bold red]")
        
        except Exception as e:
            logger.error(f"Error scanning networks: {str(e)}", exc_info=True)
            self.console.print(f"[bold red]Error scanning networks: {str(e)}[/bold red]")
    
    def cmd_list(self, args: List[str]) -> None:
        """
        List discovered networks.
        
        Args:
            args: Command arguments
        """
        if not self.networks:
            self.console.print("[bold yellow]No networks discovered yet. Run 'scan' first.[/bold yellow]")
            return
        
        self._display_networks()
    
    def cmd_info(self, args: List[str]) -> None:
        """
        Show detailed information about a network.
        
        Args:
            args: Command arguments (network index)
        """
        if not self.networks:
            self.console.print("[bold yellow]No networks discovered yet. Run 'scan' first.[/bold yellow]")
            return
        
        if not args:
            self.console.print("[bold red]Missing network index. Usage: info <network_index>[/bold red]")
            return
        
        try:
            index = int(args[0])
            if index < 0 or index >= len(self.networks):
                self.console.print(f"[bold red]Invalid network index: {index}[/bold red]")
                return
            
            network = self.networks[index]
            
            # Display detailed information
            panel = Panel(
                Text.from_markup(
                    f"[bold cyan]SSID:[/bold cyan] {network.ssid}\n"
                    f"[bold cyan]BSSID:[/bold cyan] {network.bssid}\n"
                    f"[bold cyan]Channel:[/bold cyan] {network.channel or 'Unknown'}\n"
                    f"[bold cyan]Signal Strength:[/bold cyan] {network.signal_strength or 'Unknown'} dBm\n"
                    f"[bold cyan]Security:[/bold cyan] {'Encrypted' if network.encryption else 'Open'}\n"
                    f"[bold cyan]Captive Portal:[/bold cyan] {'Yes' if network.has_captive_portal else 'No'}"
                ),
                title=f"Network Details: {network.ssid}",
                border_style="green"
            )
            
            self.console.print(panel)
        
        except ValueError:
            self.console.print("[bold red]Invalid network index. Please provide a number.[/bold red]")
        
        except Exception as e:
            logger.error(f"Error displaying network info: {str(e)}", exc_info=True)
            self.console.print(f"[bold red]Error: {str(e)}[/bold red]")
    
    def cmd_set(self, args: List[str]) -> None:
        """
        Set a configuration value.
        
        Args:
            args: Command arguments (key and value)
        """
        if len(args) < 2:
            self.console.print("[bold red]Missing key or value. Usage: set <key> <value>[/bold red]")
            return
        
        key = args[0]
        value = args[1]
        
        try:
            self.config.set(key, value)
            self.console.print(f"[bold green]Set {key} to {value}[/bold green]")
        
        except Exception as e:
            logger.error(f"Error setting configuration: {str(e)}", exc_info=True)
            self.console.print(f"[bold red]Error setting configuration: {str(e)}[/bold red]")
    
    def cmd_interfaces(self, args: List[str]) -> None:
        """
        List available wireless interfaces.
        
        Args:
            args: Command arguments
        """
        try:
            import netifaces
            interfaces = netifaces.interfaces()
            
            # Filter for likely wireless interfaces (simple heuristic)
            wireless_interfaces = [iface for iface in interfaces if iface.startswith(('w', 'en', 'wl'))]
            
            table = Table(title="Available Interfaces")
            table.add_column("Interface", style="cyan")
            table.add_column("MAC Address", style="green")
            
            for iface in wireless_interfaces:
                mac = "Unknown"
                try:
                    addrs = netifaces.ifaddresses(iface)
                    if netifaces.AF_LINK in addrs:
                        mac = addrs[netifaces.AF_LINK][0]['addr']
                except:
                    pass
                
                table.add_row(iface, mac)
            
            self.console.print(table)
            
            if not wireless_interfaces:
                self.console.print("[bold yellow]No wireless interfaces found.[/bold yellow]")
        
        except Exception as e:
            logger.error(f"Error listing interfaces: {str(e)}", exc_info=True)
            self.console.print(f"[bold red]Error listing interfaces: {str(e)}[/bold red]")
    
    def cmd_exit(self, args: List[str]) -> None:
        """
        Exit the program.
        
        Args:
            args: Command arguments
        """
        raise KeyboardInterrupt()
    
    def _display_networks(self) -> None:
        """Display the list of discovered networks in a table."""
        table = Table(title="Discovered Networks")
        table.add_column("#", style="cyan")
        table.add_column("SSID", style="green")
        table.add_column("BSSID", style="blue")
        table.add_column("Channel", style="magenta")
        table.add_column("Security", style="yellow")
        table.add_column("Signal", style="cyan")
        table.add_column("Captive Portal", style="red")
        
        for i, network in enumerate(self.networks):
            table.add_row(
                str(i),
                network.ssid,
                network.bssid,
                str(network.channel or "Unknown"),
                "Encrypted" if network.encryption else "Open",
                f"{network.signal_strength} dBm" if network.signal_strength else "Unknown",
                "Yes" if network.has_captive_portal else "No"
            )
        
        self.console.print(table)