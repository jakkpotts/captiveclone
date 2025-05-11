# CaptiveClone

A network security assessment tool designed for ethical security professionals to evaluate and test captive portal implementations on public WiFi networks.

## Legal Disclaimer

This tool is intended **ONLY** for authorized security testing with proper written permission. Unauthorized use against networks without explicit consent is illegal in most jurisdictions.

## System Requirements

- Linux-based operating system (Kali/Parrot OS recommended)
- Two compatible wireless adapters:
  - Primary: Panda PAU09 or adapter with MT7612U chipset
  - Secondary: Any adapter with monitor mode support
- 4GB+ RAM
- Python 3.8+
- Root access

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/captiveclone.git
cd captiveclone

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt
```

### System Dependencies

For Phase 3 features (Access Point and Deauthentication), the following system dependencies are required:

```bash
# On Debian/Kali/Ubuntu systems:
sudo apt update && sudo apt install -y hostapd dnsmasq iptables

# On Arch-based systems:
sudo pacman -S hostapd dnsmasq iptables

# On Fedora/RHEL/CentOS:
sudo dnf install hostapd dnsmasq iptables
```

## Usage

```bash
# Activate virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Run the tool (root privileges required for wireless interface access)
sudo python captiveclone.py
```

### Commands

```
scan - Scan for wireless networks with captive portals
  --interface (-i) - Specify wireless interface to use
  --timeout (-t) - Specify scan timeout in seconds
  
analyze - Analyze a captive portal
  <url> - URL of the captive portal to analyze
  
clone - Clone a captive portal
  <url> - URL of the captive portal to clone
  --output (-o) - Name for the output directory
  
ap - Create a rogue access point mimicking a network
  <ssid> - SSID of the network to mimic
  --interface (-i) - Wireless interface to use for the AP
  --channel (-c) - Channel to use (default: same as target network)
  --hidden - Create a hidden access point
  
deauth - Deauthenticate clients from a network
  <bssid> - BSSID of the network to target
  --interface (-i) - Wireless interface to use
  --client (-c) - MAC address of specific client to target (can be used multiple times)
  --all - Target all clients (default)
  --interval - Interval between deauth bursts in seconds (default: 0.5)
  
capture - Start credential capture
  --port (-p) - Port to listen on for the capture endpoint (default: 8080)
  --output (-o) - Directory to store captured credentials
  
web - Start the web interface
  --host (-H) - Host address to bind to (default: 127.0.0.1)
  --port (-p) - Port to listen on (default: 5000)
  
interactive - Start interactive terminal UI (default mode)
```

### Web Interface

CaptiveClone provides a web interface for easier management of captive portal analysis and cloning operations. To access the web interface:

```bash
sudo python captiveclone.py web
```

Then open a browser and navigate to http://127.0.0.1:5000

The web interface provides the following features:
- Network scanning and detection of captive portals
- Captive portal analysis
- Visual preview of cloned portals
- Portal asset management
- Form field mapping

### Additional Dependencies: Browser Automation

Certain features (portal analysis & asset extraction) rely on Selenium with Chrome/Chromium in headless mode.  Make sure the following are installed **on the target system (e.g. Kali/Raspberry Pi 5)**:

```bash
# Debian / Kali based
sudo apt update && sudo apt install -y chromium-driver chromium

# OR download the matching ChromeDriver version manually
# <https://chromedriver.chromium.org/downloads>
# and ensure it is accessible in $PATH
```

If you prefer Firefox, update `captiveclone/core/portal_analyzer.py` to use the Gecko driver instead.

### Database Initialization

CaptiveClone uses SQLite by default.  The database file path is configured in `config.yaml` (default: `captiveclone.db`).  The file is created automatically on first run; no manual migration steps are required.  If you wish to use PostgreSQL or another backend, adjust the connection string in `database/models.py` and update `config.yaml` accordingly.

## Project Structure

```
captiveclone/
├── docs/                # Documentation
├── captiveclone/        # Main package
│   ├── core/            # Core functionality
│   │   ├── scanner.py   # Network scanning
│   │   ├── models.py    # Data models
│   │   ├── portal_analyzer.py # Captive portal analysis
│   │   └── portal_cloner.py # Portal cloning
│   ├── utils/           # Utility functions
│   ├── database/        # Database models and operations
│   ├── interface/       # User interface components
│   │   ├── terminal.py  # Terminal UI
│   │   └── web.py       # Web interface
│   ├── templates/       # Web interface templates
│   ├── static/          # Static assets for web interface
│   └── hardware/        # Hardware abstraction layer
├── tests/               # Test suite
├── requirements.txt     # Project dependencies
└── README.md            # Project documentation
```

## Features

* **Network Discovery**: Scan local networks and detect captive portals
* **Hardware Abstraction**: Support for various wireless adapters with automatic capability detection
* **Captive Portal Detection**: Multiple methods to reliably identify captive portals
* **Portal Analysis**: Extract and analyze captive portal structure, forms, and assets
* **Portal Cloning**: Generate standalone clones of captive portals with 95%+ visual accuracy
* **Form Field Mapping**: Map and replicate form logic from original portals
* **Web Interface**: Modern UI for managing portal analysis and cloning
* **Persistent Storage**: Database integration for storing scan results and portal information
* **Rogue Access Point**: Create AP mimicking target networks with traffic redirection
* **Client Deauthentication**: Selective deauthentication of clients from target networks
* **Credential Capture**: Real-time monitoring and capture of submitted credentials

## Development

This project follows a phased implementation approach:

- Phase 1 (Completed): Foundation and Core Scanning
- Phase 2 (Completed): Portal Analysis and Replication
- Phase 3 (Completed): Access Point and Deauthentication
- Phase 4 (Planned): Credential Capture and Advanced UI
- Phase 5 (Planned): Reporting and System Integration

## License

[LICENSE TYPE] - See LICENSE file for details.

## Contributing

Please read CONTRIBUTING.md for details on our code of conduct and the process for submitting pull requests.