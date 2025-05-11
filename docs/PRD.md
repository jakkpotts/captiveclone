# Product Requirements Document: CaptiveClone

## Overview
CaptiveClone is a network security assessment tool designed for ethical security professionals to evaluate the security of public WiFi networks and their captive portals. This tool demonstrates the risks of insecure public WiFi by scanning, analyzing, replicating, and testing captive portal implementations.

## Key Stakeholders
- Network Security Auditors
- Penetration Testers 
- Network Administrators
- Authorized Security Researchers

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

## Functional Requirements

### 1. Network Discovery Module
- Scan local area for wireless networks
- Identify networks with captive portals
- Classify portal types (authentication-based, agreement-based, etc.)
- Present detailed information (SSID, channel, signal strength, security)
- Filter capabilities for public/hotel/resort networks

### 2. Captive Portal Analysis Engine
- Connect to specified network
- Automated detection of captive portal presence
- Intercept and log HTTP/HTTPS traffic to captive portal
- Identify form elements, authentication processes, and redirect mechanisms
- Extract visual elements (CSS, images, logos)
- Map API endpoints and backend communication

### 3. Asset Replication System
- Automate scraping of all portal assets:
  - HTML structure
  - CSS styles
  - JavaScript functions
  - Images and media
- Process assets to create standalone portal clone
- Asset optimization for local serving
- Preserve form functionality
- Detect and replicate real-time validation

### 4. Rogue Access Point Manager
- Configure virtual interfaces on supported adapters
- Create AP with identical parameters to target:
  - SSID
  - Channel
  - Security settings (if applicable)
  - MAC address spoofing
- DHCP server implementation
- DNS interception for captive portal redirection
- Traffic routing configuration

### 5. Client Deauthentication System
- Targeted deauthentication of clients on original network
- Channel hopping for multi-channel coverage
- Selective targeting (all clients, specific clients)
- Configurable timing/intervals
- Blacklist capability for specific MAC addresses

### 6. Credential Capture Framework
- Intercept and log all form submissions
- Secure storage of captured credentials
- Real-time display of captured data
- Export functions (CSV, JSON)
- Optional forwarding to legitimate portal

### 7. User Interface
- Modern, responsive web interface (accessible via browser)
- Dashboard with real-time statistics:
  - Connected clients
  - Authentication attempts
  - Network status
- Configuration panels for each module
- Dark/light theme options
- Terminal fallback interface
- Interactive network map

### 8. Reporting System
- Comprehensive report generation
- Evidence collection
- Timestamped logs
- Statistical analysis
- Remediation recommendations
- Export in multiple formats (PDF, HTML)

## Non-Functional Requirements

### Performance
- Scan completion within 60 seconds
- Portal analysis within 120 seconds
- Clone generation within 30 seconds
- AP creation within 10 seconds
- Response time < 200ms for web interface

### Reliability
- Automatic recovery from hardware failures
- Connection persistence
- Session recovery
- Auto-save of collected data

### Security
- Encrypted storage of captured credentials
- Secure communication between components
- Role-based access control
- Session timeouts
- Anti-tampering measures

### Usability
- First-time setup wizard
- Contextual help
- Command suggestions
- Progress indicators
- Error explanations

## System Architecture

### Frontend
- Electron-based dashboard for desktop use
- Web interface using React/Vue
- Terminal UI option for headless operation
- RESTful API for custom integrations

### Backend
- Modular Python services
- Central controller for module coordination
- Database for storage (SQLite or PostgreSQL)
- Background workers for heavy operations

### Hardware Interaction
- Direct interface with wireless adapters
- Abstraction layer for hardware differences
- Driver compatibility module
- Power management for reliability

## User Flow
1. Scan local networks to discover captive portals
2. Select target network with captive portal
3. Connect and analyze portal structure
4. Generate and preview portal clone
5. Configure rogue AP parameters
6. Deploy rogue AP and start deauthentication
7. Monitor connections and credential submissions
8. Generate security report

## Technical Implementation Considerations
- Use of Scapy for packet manipulation
- Selenium/Playwright for portal analysis
- Flask/FastAPI for web interface backend
- hostapd for AP creation
- dnsmasq for DHCP/DNS
- pyric for wireless interface management
- Cross-platform wrapper for specific hardware drivers
- Docker containerization option for consistent deployment

## Success Metrics
- Accurate replication of captive portal UI (95%+ visual similarity)
- Successful credential capture rate
- Setup time under 5 minutes
- False positive rate under 5%
- System stability (>98% uptime)

## Ethical Guidelines
- All usage requires explicit written authorization
- Immediate data destruction after testing
- No actual credential use
- Thorough documentation of all activities
- Notification to network owners after testing

## Development Roadmap
The CaptiveClone project will follow a seven-phase implementation approach, with each phase having clear objectives and measurable success criteria. This structured approach enables rapid development while maintaining quality control and regular delivery milestones. See the Detailed Implementation Phases section for specifics on each phase:

1. **Phase 1**: Foundation and Core Scanning (4 Weeks)
2. **Phase 2**: Portal Analysis and Replication (5 Weeks)
3. **Phase 3**: Access Point and Deauthentication (4 Weeks)
4. **Phase 4**: Credential Capture and Advanced UI (5 Weeks)
5. **Phase 5**: Reporting and System Integration (3 Weeks)
6. **Phase 6**: Security, Testing, and Documentation (3 Weeks)
7. **Phase 7**: Packaging and Release (2 Weeks)

Total estimated timeline: 26 weeks (approximately 6 months)

## Detailed Implementation Phases
To ensure rapid yet structured development, the CaptiveClone project will be implemented according to the following phased approach. Each phase has clear objectives and measurable success criteria to facilitate focused development, regular delivery milestones, and quality assurance.

### Phase 1: Foundation and Core Scanning (4 Weeks)
**Objectives:**
- Establish project foundation
- Implement core network discovery functionality
- Create basic terminal-based UI for testing
- Define database schema
- Set up hardware abstraction for wireless devices
- Integrate testing framework

**Success Criteria:**
- Successfully scan networks and detect captive portals from CLI
- Hardware abstraction works on multiple known-good adapters
- 85%+ test coverage on discovery components
- No crashes or critical errors during normal operation

### Phase 2: Portal Analysis and Replication (5 Weeks)
**Objectives:**
- Detect captive portals and analyze their structure
- Intercept portal HTTP/HTTPS traffic
- Scrape and replicate assets (HTML/CSS/JS/images)
- Map form fields and API calls
- Generate standalone clones
- Develop basic web UI for managing portal analysis

**Success Criteria:**
- 95%+ visual accuracy for cloned portals
- Detect and replicate form logic for majority of targets
- Basic UI allows preview and download of clone
- Secure handling of all intercepted data

### Phase 3: Access Point and Deauthentication (4 Weeks)
**Objectives:**
- Create a rogue access point mimicking the target network
- Configure DHCP/DNS services
- Implement traffic redirection
- Execute selective client deauthentication

**Success Criteria:**
- Stable rogue AP operation on supported adapters
- All connected clients redirected to clone page
- Deauthentication reaches 90%+ coverage on busy networks
- No persistent interference with host system networking

### Phase 4: Credential Capture and Advanced UI (5 Weeks)
**Objectives:**
- Implement form submission interception
- Securely log and store submitted credentials
- Add frontend dashboard for real-time monitoring
- Package desktop UI with Electron

**Success Criteria:**
- Successful capture of credential input for >90% of tested portals
- Real-time dashboard updates under load
- UI responsiveness under 200ms latency
- Cross-platform desktop client build succeeds

### Phase 5: Reporting and System Integration (3 Weeks)
**Objectives:**
- Build a detailed reporting system
- Finalize end-to-end system integration
- Test system performance and optimize bottlenecks
- Conduct hardware compatibility checks

**Success Criteria:**
- Reports generate without errors or omissions
- System shows <10% performance degradation with full load
- Compatibility confirmed with 3+ adapter chipsets

### Phase 6: Security, Testing, and Documentation (3 Weeks)
**Objectives:**
- Implement robust security practices
- Harden system against tampering or misuse
- Finalize documentation for developers and users

**Success Criteria:**
- 100% test pass rate on core flows
- Security audit checklist passes
- Docs enable new user to deploy and scan in <10 minutes

### Phase 7: Packaging and Release (2 Weeks)
**Objectives:**
- Prepare and package the final software release
- Ensure deployment options are stable
- Finalize QA testing and build community resources

**Success Criteria:**
- End-to-end deployment from Docker/Kali verified
- Clean install and uninstall processes
- Clear onboarding for users and contributors
- CaptiveClone publicly released with usage protections

### Benefits of the Phased Implementation Approach

This structured implementation plan facilitates rapid yet controlled development through:

1. **Modular Development**: Each phase focuses on specific functional components, allowing parallel development and isolated testing of features.

2. **Clear Milestones**: Well-defined success criteria per phase enable objective progress tracking and timely feedback.

3. **Risk Management**: Early implementation of core functionality reduces technical risk, with complex components built on stable foundations.

4. **Regular Deliverables**: The phased approach produces usable components at each milestone, allowing for early testing and stakeholder feedback.

5. **Resource Optimization**: Team resources can be allocated more efficiently with focused sprints on specific functional areas.

6. **Quality Assurance**: Each phase includes dedicated testing and validation, ensuring robust components before integration.

7. **Adaptation Opportunity**: The structured approach allows for course correction between phases based on findings and emerging requirements.

This methodology balances speed and quality, producing a robust, reliable security assessment tool while maintaining an aggressive development timeline.

## Licensing and Distribution
- Open-source with restricted use license
- Educational/research focus
- Required authorization acknowledgment
- Contributor guidelines emphasizing ethical use

## Competitive Analysis
Compared to existing tools like Wifiphisher, this solution provides:
- Specialized focus on captive portal replication
- More sophisticated portal analysis
- Better hardware support for specific adapters
- Modern UI with real-time monitoring
- Comprehensive reporting

This PRD outlines a tool with significant capabilities for legitimate security testing while emphasizing the ethical and legal requirements for its use.
