# CaptiveClone Installation Guide

This guide provides detailed instructions for installing CaptiveClone on various Linux distributions, with a primary focus on Kali Linux and Raspberry Pi 5 environments.

## System Requirements

- Linux-based operating system (Kali/Parrot OS recommended)
- Two compatible wireless adapters:
  - Primary: Panda PAU09 or adapter with MT7612U chipset
  - Secondary: Any adapter with monitor mode support
- 4GB+ RAM
- Python 3.8+
- Root access

## Basic Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/captiveclone.git
cd captiveclone
```

### 2. Create and Activate Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install Python Dependencies

```bash
pip install -r requirements.txt
```

## System Dependencies 

CaptiveClone requires several system packages, particularly for access point creation and network manipulation features (Phase 3+).

### Debian/Kali/Ubuntu

```bash
sudo apt update
sudo apt install -y hostapd dnsmasq iptables wireless-tools iw \
    net-tools procps chromium-driver chromium \
    build-essential libssl-dev libffi-dev python3-dev
```

### Arch Linux

```bash
sudo pacman -S hostapd dnsmasq iptables wireless_tools iw net-tools procps \
    chromium chromedriver base-devel openssl
```

### Fedora/RHEL/CentOS

```bash
sudo dnf install hostapd dnsmasq iptables wireless-tools iw net-tools procps \
    chromium chromedriver openssl-devel gcc python3-devel
```

## Raspberry Pi 5 Specific Setup

For optimal performance on a Raspberry Pi 5 running Kali Linux:

### 1. Update and Upgrade Packages

```bash
sudo apt update
sudo apt upgrade -y
```

### 2. Install Additional Packages

```bash
sudo apt install -y kali-linux-headless python3-venv python3-pip \
    hostapd dnsmasq iptables wireless-tools iw net-tools procps \
    chromium-driver chromium
```

### 3. Configure Wireless Adapters

Ensure your wireless adapters are recognized:

```bash
sudo iw dev
```

If the chipsets are not recognized properly, you may need to install additional drivers:

#### For MT7612U (Panda PAU09):

```bash
sudo apt install -y build-essential git
git clone https://github.com/aircrack-ng/rtl8812au.git
cd rtl8812au
make
sudo make install
```

#### For RTL8812AU (Alpha AWUS036ACH):

```bash
sudo apt install -y build-essential git
git clone https://github.com/aircrack-ng/rtl8812au.git
cd rtl8812au
make
sudo make install
```

## Browser Automation Dependencies

CaptiveClone uses browser automation for portal analysis. By default, it uses Chromium/Chrome in headless mode.

### Chrome/Chromium

Chrome or Chromium is installed as part of the system dependencies above. For manual installation:

```bash
# On Debian/Kali:
sudo apt install -y chromium chromium-driver

# On Arch:
sudo pacman -S chromium chromedriver

# On Fedora:
sudo dnf install chromium chromedriver
```

### Alternative: Using Firefox/Gecko Driver

If you prefer Firefox, update `captiveclone/core/portal_analyzer.py` to use the Gecko driver:

```bash
# Install Firefox and GeckoDriver
sudo apt install -y firefox-esr

# Download and install GeckoDriver
wget https://github.com/mozilla/geckodriver/releases/download/v0.32.0/geckodriver-v0.32.0-linux64.tar.gz
tar -xvzf geckodriver-v0.32.0-linux64.tar.gz
chmod +x geckodriver
sudo mv geckodriver /usr/local/bin/
```

## Database Setup

CaptiveClone uses SQLite by default, which requires no additional setup. The database file is automatically created on first run.

If you prefer to use PostgreSQL:

```bash
# Install PostgreSQL
sudo apt install -y postgresql postgresql-contrib

# Start PostgreSQL service
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create database and user
sudo -u postgres psql -c "CREATE USER captiveclone WITH PASSWORD 'your_password';"
sudo -u postgres psql -c "CREATE DATABASE captiveclone OWNER captiveclone;"

# Update config.yaml with PostgreSQL connection string
# Edit database section to use: postgresql://captiveclone:your_password@localhost/captiveclone
```

## Email Notification Setup (Optional)

For email notifications:

1. Install additional dependencies:
   ```bash
   pip install flask-mail
   ```

2. Configure email settings in `config.yaml`:
   ```yaml
   notifications:
     mail:
       enabled: true
       server: smtp.example.com
       port: 587
       use_tls: true
       username: your_username
       password: your_password
       default_sender: alerts@example.com
   ```

## Authentication Setup (Optional)

To enable user authentication:

1. Ensure the required packages are installed:
   ```bash
   pip install flask-login passlib[argon2]
   ```

2. Configure authentication in `config.yaml`:
   ```yaml
   security:
     enable_login: true
   ```

3. When you first start the application with authentication enabled, you'll be prompted to create an admin user.

## Verification

To verify your installation is working correctly:

```bash
sudo python captiveclone.py --version
```

This should display the current version of CaptiveClone.

To verify wireless adapter detection:

```bash
sudo python captiveclone.py hardware-check
```

This will list detected wireless adapters and their capabilities.

## Troubleshooting

### Wireless Adapter Issues

If wireless adapters are not detected:

1. Check if the adapter is recognized by the system:
   ```bash
   sudo lsusb
   sudo iwconfig
   ```

2. Make sure the necessary kernel modules are loaded:
   ```bash
   sudo modprobe rt2800usb  # For RT2800 chipsets
   sudo modprobe rtl8xxxu   # For Realtek chipsets
   ```

3. Check if the adapter supports monitor mode:
   ```bash
   sudo iw list | grep -A 10 "Supported interface modes"
   ```

### Browser Automation Issues

If browser automation fails:

1. Make sure Chrome/Chromium is installed:
   ```bash
   chromium --version
   ```

2. Verify ChromeDriver is in PATH:
   ```bash
   chromedriver --version
   ```

3. Add ChromeDriver to PATH if needed:
   ```bash
   sudo ln -s /usr/bin/chromedriver /usr/local/bin/chromedriver
   ```

### Python Dependency Issues

If you encounter issues with Python dependencies:

1. Update pip:
   ```bash
   pip install --upgrade pip
   ```

2. Reinstall dependencies with verbose output:
   ```bash
   pip install -v -r requirements.txt
   ```

## Next Steps

After installation, proceed to the [USER_GUIDE.md](USER_GUIDE.md) for usage instructions. 