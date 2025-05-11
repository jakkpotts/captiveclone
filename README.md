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

## Project Structure

```
captiveclone/
├── docs/                # Documentation
├── captiveclone/        # Main package
│   ├── core/            # Core functionality
│   ├── utils/           # Utility functions
│   ├── database/        # Database models and operations
│   ├── interface/       # User interface components
│   └── hardware/        # Hardware abstraction layer
├── tests/               # Test suite
├── requirements.txt     # Project dependencies
└── README.md            # Project documentation
```

## Development

This project is currently in Phase 1 (Foundation and Core Scanning).

## License

[LICENSE TYPE] - See LICENSE file for details.

## Contributing

Please read CONTRIBUTING.md for details on our code of conduct and the process for submitting pull requests. 