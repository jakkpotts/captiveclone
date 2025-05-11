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
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

```bash
# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Run the tool
sudo python captiveclone.py
```

### Commands

```
scan - Scan for wireless networks with captive portals
  --interface (-i) - Specify wireless interface to use
  --timeout (-t) - Specify scan timeout in seconds
  
interactive - Start interactive terminal UI (default mode)
```

## Project Structure

```
captiveclone/
├── docs/                # Documentation
├── captiveclone/        # Main package
│   ├── core/            # Core functionality
│   │   ├── scanner.py   # Network scanning
│   │   ├── models.py    # Data models
│   │   └── portal_analyzer.py # Captive portal analysis
│   ├── utils/           # Utility functions
│   ├── database/        # Database models and operations
│   ├── interface/       # User interface components
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
* **Persistent Storage**: Database integration for storing scan results and portal information

## Development

This project follows a phased implementation approach:

- Phase 1 (Completed): Foundation and Core Scanning
- Phase 2 (In Progress): Portal Analysis and Replication
- Phase 3 (Planned): Access Point and Deauthentication
- Phase 4 (Planned): Credential Capture and Advanced UI
- Phase 5 (Planned): Reporting and System Integration

## License

[LICENSE TYPE] - See LICENSE file for details.

## Contributing

Please read CONTRIBUTING.md for details on our code of conduct and the process for submitting pull requests. 