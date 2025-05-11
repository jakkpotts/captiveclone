# CaptiveClone User Guide

## Overview

CaptiveClone is a network security assessment tool designed for ethical security professionals to evaluate and test captive portal implementations on public WiFi networks. This guide provides instructions for using the core features of CaptiveClone.

## Ethical Usage

CaptiveClone is to be used **ONLY** with proper written authorization from the network owner. Unauthorized use is illegal in most jurisdictions and may result in severe penalties. Always ensure you have explicit permission before testing any network.

## Getting Started

### Prerequisites

Before using CaptiveClone, ensure you have:

- A Linux-based operating system (Kali/Parrot OS recommended)
- Two compatible wireless adapters
- Python 3.8+ installed
- Root access
- All dependencies installed (see [INSTALLATION.md](INSTALLATION.md))

### Basic Workflow

The typical CaptiveClone workflow consists of the following steps:

1. **Network Discovery**: Scan for networks with captive portals
2. **Portal Analysis**: Analyze a captive portal's structure
3. **Portal Cloning**: Clone the captive portal
4. **Deployment**: Create a rogue access point serving the cloned portal
5. **Client Redirection**: Redirect clients to the cloned portal
6. **Credential Capture**: Capture authentication attempts
7. **Reporting**: Generate security assessment reports

## Using the Web Interface

The web interface provides a user-friendly way to interact with CaptiveClone. To start the web interface:

```bash
sudo python captiveclone.py web
```

Then access http://127.0.0.1:5000 in your browser (or the configured host/port).

### Dashboard

The dashboard provides an overview of:

- Active scans and their progress
- Detected networks with captive portals
- Active access points
- Captured credentials (if any)
- System status

### Network Scanning

1. Navigate to the "Scan" tab
2. Select your wireless interface
3. Configure scan parameters (duration, channels, etc.)
4. Click "Start Scan"
5. Review the results to identify networks with captive portals

### Portal Analysis

1. Navigate to the "Analyze" tab
2. Enter the URL of the captive portal to analyze
3. Alternatively, select a detected network from the scan results
4. Click "Analyze Portal"
5. Review the analysis results, including form fields, assets, and structure

### Portal Cloning

1. Navigate to the "Clone" tab
2. Select a previously analyzed portal or enter a URL
3. Configure cloning options
4. Click "Clone Portal"
5. Preview the cloned portal to verify its appearance

### Access Point Creation

1. Navigate to the "Access Point" tab
2. Select the wireless interface to use
3. Configure AP settings (SSID, channel, encryption)
4. Select the cloned portal to serve
5. Click "Create AP"
6. Monitor the AP status and connected clients

### Credential Capture

1. Navigate to the "Capture" tab
2. Review captured credentials in real-time
3. Export captured data in various formats
4. Configure notification settings

### Reporting

1. Navigate to the "Reports" tab
2. Select the data to include in the report
3. Choose the report format
4. Generate and download the report

## Using the Command Line Interface

CaptiveClone also provides a powerful command-line interface for advanced users and scripting:

### Interactive Mode

The default mode provides a terminal-based UI:

```bash
sudo python captiveclone.py interactive
```

### Direct Commands

#### Scanning Networks

```bash
sudo python captiveclone.py scan --interface wlan0 --timeout 30
```

#### Analyzing a Portal

```bash
sudo python captiveclone.py analyze http://captive.portal.example.com
```

#### Cloning a Portal

```bash
sudo python captiveclone.py clone http://captive.portal.example.com --output hotel_wifi
```

#### Creating an Access Point

```bash
sudo python captiveclone.py ap "Free WiFi" --interface wlan1 --channel 6
```

#### Deauthenticating Clients

```bash
sudo python captiveclone.py deauth 00:11:22:33:44:55 --interface wlan0 --all
```

#### Capturing Credentials

```bash
sudo python captiveclone.py capture --port 8080 --output captures/
```

## Understanding Results

### Network Scan Results

Scan results show discovered networks with their properties:
- SSID: Network name
- BSSID: MAC address of the access point
- Channel: Operating channel
- Signal: Signal strength in dBm
- Security: Security protocol in use
- Captive: Indicates presence of a captive portal

### Portal Analysis Results

Analysis results include:
- Form fields and their types
- Authentication endpoints
- Assets (images, CSS, JS files)
- Redirect patterns
- Authentication mechanisms

### Credential Capture Results

Capture results show:
- Timestamp of the capture
- Source client MAC address
- Username/email field value
- Password field value (encrypted)
- Additional form fields
- Source network information

## Recommended Hardware

For optimal performance, we recommend:
- Primary adapter: Panda PAU09 or any adapter with MT7612U chipset
- Secondary adapter: Alpha AWUS036ACH or any adapter with RTL8812AU chipset

## Next Steps

For more advanced usage, refer to the [ADVANCED_USAGE.md](ADVANCED_USAGE.md) guide.

For troubleshooting, see the [TROUBLESHOOTING.md](TROUBLESHOOTING.md) document.

## Support

For support, please open an issue on the GitHub repository or contact the project maintainers. 