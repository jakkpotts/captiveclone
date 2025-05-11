# CaptiveClone Troubleshooting Guide

This guide addresses common issues you might encounter when using CaptiveClone and provides solutions to help resolve them.

## Table of Contents

1. [Installation Issues](#installation-issues)
2. [Wireless Adapter Problems](#wireless-adapter-problems)
3. [Scanning Issues](#scanning-issues)
4. [Portal Analysis Problems](#portal-analysis-problems)
5. [Cloning Errors](#cloning-errors)
6. [Access Point Issues](#access-point-issues)
7. [Deauthentication Problems](#deauthentication-problems)
8. [Credential Capture Issues](#credential-capture-issues)
9. [Web Interface Problems](#web-interface-problems)
10. [Database Issues](#database-issues)
11. [Permission and Privilege Problems](#permission-and-privilege-problems)
12. [Performance Optimization](#performance-optimization)
13. [Diagnostic Commands](#diagnostic-commands)

## Installation Issues

### Python Dependency Installation Failures

**Issue**: `pip install -r requirements.txt` fails with build errors.

**Solution**:
1. Ensure you have the required development libraries:
   ```bash
   sudo apt install -y build-essential libssl-dev libffi-dev python3-dev
   ```
2. Update pip to the latest version:
   ```bash
   pip install --upgrade pip
   ```
3. Install dependencies one by one to identify the problematic package:
   ```bash
   pip install package_name
   ```

### System Package Installation Failures

**Issue**: Unable to install required system packages like hostapd or dnsmasq.

**Solution**:
1. Update your package lists:
   ```bash
   sudo apt update
   ```
2. If packages are unavailable, check for alternative repositories:
   ```bash
   sudo add-apt-repository universe
   sudo apt update
   ```

### Virtual Environment Issues

**Issue**: Virtual environment creation fails or `source .venv/bin/activate` doesn't work.

**Solution**:
1. Ensure you have Python venv installed:
   ```bash
   sudo apt install python3-venv
   ```
2. Try creating the environment with the full Python path:
   ```bash
   /usr/bin/python3 -m venv .venv
   ```
3. If activation doesn't work, check your shell and use the appropriate activation command:
   - Bash/Zsh: `source .venv/bin/activate`
   - Fish: `source .venv/bin/activate.fish`
   - Csh/Tcsh: `source .venv/bin/activate.csh`

## Wireless Adapter Problems

### Adapter Not Detected

**Issue**: CaptiveClone doesn't detect your wireless adapter.

**Solution**:
1. Verify the adapter is recognized by the system:
   ```bash
   sudo lsusb
   sudo iwconfig
   ```
2. Ensure the adapter is compatible with monitor mode:
   ```bash
   sudo iw list | grep -A 10 "Supported interface modes"
   ```
3. Check if the driver is loaded:
   ```bash
   lsmod | grep rt2800usb  # For RT2800 chipsets
   lsmod | grep rtl8xxxu   # For Realtek chipsets
   ```
4. Manually load the driver if needed:
   ```bash
   sudo modprobe rt2800usb  # For RT2800 chipsets
   sudo modprobe rtl8xxxu   # For Realtek chipsets
   ```

### Monitor Mode Issues

**Issue**: Unable to enable monitor mode on the adapter.

**Solution**:
1. Check if any network manager is controlling the interface:
   ```bash
   sudo service NetworkManager status
   sudo service wpa_supplicant status
   ```
2. Temporarily disable these services:
   ```bash
   sudo systemctl stop NetworkManager
   sudo systemctl stop wpa_supplicant
   ```
3. Manually bring down the interface and set monitor mode:
   ```bash
   sudo ip link set wlan0 down
   sudo iw dev wlan0 set type monitor
   sudo ip link set wlan0 up
   ```
4. Verify monitor mode is enabled:
   ```bash
   iwconfig wlan0
   ```

### Device Busy Errors

**Issue**: "Device or resource busy" error when trying to use the adapter.

**Solution**:
1. Identify processes using the wireless interface:
   ```bash
   sudo airmon-ng check
   ```
2. Kill interfering processes:
   ```bash
   sudo airmon-ng check kill
   ```
3. Alternatively, manually kill processes:
   ```bash
   sudo pkill -9 wpa_supplicant
   sudo pkill -9 dhclient
   ```

## Scanning Issues

### No Networks Found

**Issue**: CaptiveClone scan doesn't detect any networks.

**Solution**:
1. Verify your adapter is working properly:
   ```bash
   sudo iwlist wlan0 scan
   ```
2. Try specifying channels explicitly:
   ```bash
   sudo python captiveclone.py scan --interface wlan0 --channels 1,6,11
   ```
3. Increase scan duration:
   ```bash
   sudo python captiveclone.py scan --interface wlan0 --timeout 60
   ```
4. Try with another adapter if available.

### Scan Crashes or Freezes

**Issue**: Scanner crashes or freezes during scanning.

**Solution**:
1. Enable debug output:
   ```bash
   sudo python captiveclone.py scan --interface wlan0 --debug
   ```
2. Check system logs for kernel or driver issues:
   ```bash
   dmesg | tail -n 50
   ```
3. Try with single channel scanning to isolate the issue:
   ```bash
   sudo python captiveclone.py scan --interface wlan0 --channels 1
   ```

### Captive Portal Detection Failures

**Issue**: CaptiveClone doesn't detect captive portals on networks that have them.

**Solution**:
1. Try using all detection methods:
   ```bash
   sudo python captiveclone.py scan --interface wlan0 --detection-methods dns,http,redirect,content
   ```
2. Check your internet connectivity (required for comparison).
3. Manually connect to the network and verify the captive portal:
   ```bash
   sudo python captiveclone.py analyze --url http://captive.detected.ip
   ```

## Portal Analysis Problems

### Browser Automation Failures

**Issue**: Selenium/Chrome errors during portal analysis.

**Solution**:
1. Verify Chrome and ChromeDriver versions match:
   ```bash
   chromium --version
   chromedriver --version
   ```
2. Update ChromeDriver if necessary.
3. Try running in non-headless mode for debugging:
   ```bash
   sudo python captiveclone.py analyze http://example.com --headless false
   ```
4. Check for X server issues if running on a headless system:
   ```bash
   sudo apt install xvfb
   xvfb-run sudo python captiveclone.py analyze http://example.com
   ```

### Asset Download Failures

**Issue**: Unable to download assets from the captive portal.

**Solution**:
1. Check network connectivity to the portal.
2. Try with increased timeout:
   ```bash
   sudo python captiveclone.py analyze http://example.com --timeout 120
   ```
3. Enable cookies and JavaScript:
   ```bash
   sudo python captiveclone.py analyze http://example.com --js-enabled true --cookies-enabled true
   ```

### Form Detection Failures

**Issue**: Forms on the portal are not properly detected.

**Solution**:
1. Try with advanced form detection:
   ```bash
   sudo python captiveclone.py analyze http://example.com --advanced-form-detection
   ```
2. Manually specify form selectors:
   ```bash
   sudo python captiveclone.py analyze http://example.com --form-selector "form#login"
   ```

## Cloning Errors

### Missing Assets in Clone

**Issue**: Cloned portal is missing images, CSS, or other assets.

**Solution**:
1. Increase max depth for asset discovery:
   ```bash
   sudo python captiveclone.py clone http://example.com --max-depth 5
   ```
2. Allow external domain asset fetching:
   ```bash
   sudo python captiveclone.py clone http://example.com --proxy-external --external-domains "cdn.example.com"
   ```
3. Check for cross-origin resource restrictions in the original portal.

### Form Functionality Issues

**Issue**: Forms in the cloned portal don't function correctly.

**Solution**:
1. Enable advanced form replication:
   ```bash
   sudo python captiveclone.py clone http://example.com --advanced-form-replication
   ```
2. Manually map form fields:
   ```bash
   sudo python captiveclone.py clone http://example.com --map-field "username:email" --map-field "pass:password"
   ```
3. Inject custom JavaScript to handle form validation:
   ```bash
   sudo python captiveclone.py clone http://example.com --inject-js custom_validation.js
   ```

### CSS/Layout Problems

**Issue**: Cloned portal doesn't look like the original.

**Solution**:
1. Enable full layout preservation:
   ```bash
   sudo python captiveclone.py clone http://example.com --preserve-layout
   ```
2. Try different user agent strings:
   ```bash
   sudo python captiveclone.py clone http://example.com --user-agent "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
   ```
3. Adjust viewport size during analysis:
   ```bash
   sudo python captiveclone.py clone http://example.com --window-size 1920x1080
   ```

## Access Point Issues

### AP Creation Failures

**Issue**: Unable to create the access point.

**Solution**:
1. Verify hostapd is installed correctly:
   ```bash
   sudo hostapd -v
   ```
2. Check if the interface supports AP mode:
   ```bash
   sudo iw list | grep -A 10 "Supported interface modes" | grep AP
   ```
3. Ensure no other process is using the interface:
   ```bash
   sudo airmon-ng check
   sudo rfkill list
   ```
4. If the interface is blocked:
   ```bash
   sudo rfkill unblock all
   ```

### DHCP/DNS Configuration Issues

**Issue**: Clients connect but don't get IP addresses or DNS doesn't work.

**Solution**:
1. Check dnsmasq configuration:
   ```bash
   sudo cat /tmp/captiveclone/dnsmasq.conf
   ```
2. Verify dnsmasq is running:
   ```bash
   sudo ps aux | grep dnsmasq
   ```
3. Check for IP conflicts in your network range.
4. Ensure IP forwarding is enabled:
   ```bash
   cat /proc/sys/net/ipv4/ip_forward
   sudo sysctl -w net.ipv4.ip_forward=1
   ```

### Captive Portal Redirection Problems

**Issue**: Clients connect but are not redirected to the captive portal.

**Solution**:
1. Check iptables rules:
   ```bash
   sudo iptables -t nat -L
   ```
2. Manually add redirection rules:
   ```bash
   sudo iptables -t nat -A PREROUTING -i wlan1 -p tcp --dport 80 -j DNAT --to-destination 192.168.87.1:8080
   sudo iptables -t nat -A PREROUTING -i wlan1 -p tcp --dport 443 -j DNAT --to-destination 192.168.87.1:8080
   ```
3. Verify the captive portal server is running:
   ```bash
   sudo netstat -tuln | grep 8080
   ```

## Deauthentication Problems

### Deauthentication Not Working

**Issue**: Clients don't disconnect from target network.

**Solution**:
1. Verify your adapter supports packet injection:
   ```bash
   sudo aireplay-ng --test wlan0
   ```
2. Try increasing the number of deauth packets:
   ```bash
   sudo python captiveclone.py deauth 00:11:22:33:44:55 --interface wlan0 --burst 20
   ```
3. Verify you're on the correct channel:
   ```bash
   sudo iwconfig wlan0 channel 6  # Match target AP channel
   ```
4. Try targeting specific clients:
   ```bash
   sudo python captiveclone.py deauth 00:11:22:33:44:55 --interface wlan0 --client AA:BB:CC:DD:EE:FF
   ```

### Deauthentication Affects Wrong Clients

**Issue**: Unintended clients are disconnected.

**Solution**:
1. Use more precise targeting:
   ```bash
   sudo python captiveclone.py deauth 00:11:22:33:44:55 --interface wlan0 --client AA:BB:CC:DD:EE:FF --client 11:22:33:44:55:66
   ```
2. Add important clients to blacklist:
   ```bash
   sudo python captiveclone.py deauth 00:11:22:33:44:55 --interface wlan0 --all --blacklist AA:BB:CC:DD:EE:FF
   ```
3. Reduce deauthentication power/range if your adapter supports it.

## Credential Capture Issues

### No Credentials Being Captured

**Issue**: Forms are submitted, but no credentials are captured.

**Solution**:
1. Verify form fields are properly mapped:
   ```bash
   sudo python captiveclone.py capture --port 8080 --debug
   ```
2. Check the credential interception script in the cloned portal.
3. Ensure the submission endpoint is properly set up.
4. Try with a simpler form for testing:
   ```bash
   sudo python captiveclone.py clone http://example.com --simplified-forms
   ```

### Credential Storage Issues

**Issue**: Credentials are captured but not stored properly.

**Solution**:
1. Check database connectivity:
   ```bash
   sudo python captiveclone.py db-check
   ```
2. Verify encryption key is accessible:
   ```bash
   sudo python captiveclone.py check-encryption
   ```
3. Try with temporary file storage:
   ```bash
   sudo python captiveclone.py capture --port 8080 --output /tmp/credentials --format json
   ```

## Web Interface Problems

### Web Interface Not Starting

**Issue**: Unable to start the web interface.

**Solution**:
1. Check if the port is already in use:
   ```bash
   sudo netstat -tuln | grep 5000
   ```
2. Try a different port:
   ```bash
   sudo python captiveclone.py web --port 8888
   ```
3. Verify Flask and its dependencies are installed:
   ```bash
   pip list | grep Flask
   ```
4. Check for errors in the logs:
   ```bash
   tail -n 50 captiveclone.log
   ```

### Authentication Issues

**Issue**: Problems with login/registration.

**Solution**:
1. Reset the admin password:
   ```bash
   sudo python captiveclone.py reset-password --username admin
   ```
2. Check if Flask-Login is installed:
   ```bash
   pip install flask-login
   ```
3. Verify the database user table exists:
   ```bash
   sudo python captiveclone.py db-check --table users
   ```

### WebSocket Connection Failures

**Issue**: Real-time updates not working in the web interface.

**Solution**:
1. Check if SocketIO is installed:
   ```bash
   pip install flask-socketio
   ```
2. Verify browser WebSocket support (use modern browser).
3. Check for browser console errors (F12 > Console).
4. Try without proxy servers that might block WebSockets.

## Database Issues

### Database Connection Failures

**Issue**: Unable to connect to the database.

**Solution**:
1. For SQLite, check file permissions:
   ```bash
   ls -la captiveclone.db
   sudo chmod 664 captiveclone.db
   ```
2. For PostgreSQL, verify connection details and service status:
   ```bash
   sudo systemctl status postgresql
   sudo -u postgres psql -c "ALTER USER captiveclone WITH PASSWORD 'new_password';"
   ```
3. Try recreating the database:
   ```bash
   sudo python captiveclone.py db-reset
   ```

### Database Schema Issues

**Issue**: Database schema errors or missing tables.

**Solution**:
1. Run database initialization:
   ```bash
   sudo python captiveclone.py db-init
   ```
2. Check for migration errors:
   ```bash
   sudo python captiveclone.py db-migrate
   ```
3. Manually create required tables (see documentation for schema).

## Permission and Privilege Problems

### Permission Denied Errors

**Issue**: "Permission denied" errors when running commands.

**Solution**:
1. Run CaptiveClone with sudo for hardware access:
   ```bash
   sudo python captiveclone.py
   ```
2. Check file and directory permissions:
   ```bash
   sudo chown -R $(whoami):$(whoami) /path/to/captiveclone
   sudo chmod -R 755 /path/to/captiveclone
   ```
3. Verify the user has permissions for network operations:
   ```bash
   sudo usermod -a -G netdev $(whoami)
   ```

### Privilege Escalation Issues

**Issue**: CaptiveClone needs root but you want to minimize root access.

**Solution**:
1. Use sudo only for specific modules:
   ```bash
   sudo python captiveclone.py hardware-setup
   python captiveclone.py web
   ```
2. Configure specific capabilities instead of full root:
   ```bash
   sudo setcap cap_net_raw,cap_net_admin=eip $(which python)
   ```

## Performance Optimization

### High CPU Usage

**Issue**: CaptiveClone uses excessive CPU resources.

**Solution**:
1. Enable low memory mode in config:
   ```yaml
   performance:
     low_memory_mode: true
   ```
2. Reduce polling intervals:
   ```yaml
   performance:
     polling_interval: 5
   ```
3. Disable browser preview:
   ```bash
   sudo python captiveclone.py web --disable-browser-preview
   ```

### Memory Leaks

**Issue**: CaptiveClone consumes increasing amounts of memory over time.

**Solution**:
1. Enable garbage collection:
   ```yaml
   performance:
     aggressive_gc: true
   ```
2. Restart long-running processes periodically:
   ```bash
   sudo python captiveclone.py with-auto-restart ap "Free WiFi" --interface wlan1
   ```
3. Monitor memory usage:
   ```bash
   watch -n 5 "ps aux | grep python"
   ```

## Diagnostic Commands

CaptiveClone includes several diagnostic commands to help troubleshoot issues:

### Hardware Check

```bash
sudo python captiveclone.py hardware-check
```
This provides detailed information about your wireless adapters and their capabilities.

### Network Interface Status

```bash
sudo python captiveclone.py interface-status --interface wlan0
```
Shows the current status of a network interface.

### Database Validation

```bash
sudo python captiveclone.py db-check
```
Verifies the database structure and connectivity.

### Config Validation

```bash
sudo python captiveclone.py config-check
```
Validates the configuration file for errors.

### Dependency Check

```bash
sudo python captiveclone.py dependency-check
```
Verifies all required dependencies are installed and at the correct versions.

### System Environment Check

```bash
sudo python captiveclone.py system-check
```
Checks the system environment for compatibility issues.

### Log Analysis

```bash
sudo python captiveclone.py analyze-logs
```
Analyzes log files for common error patterns and suggests solutions.

## Getting Help

If you continue to experience issues not covered in this guide:

1. Check the detailed logs:
   ```bash
   tail -n 100 captiveclone.log
   ```

2. Enable debug mode for more detailed logging:
   ```bash
   sudo python captiveclone.py --debug
   ```

3. Open an issue on the GitHub repository with:
   - Detailed description of the issue
   - Steps to reproduce
   - System information (OS, Python version, etc.)
   - Relevant log output

4. Search the existing issues on GitHub for similar problems and solutions. 