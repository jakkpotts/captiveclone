# CaptiveClone Security Best Practices

This document outlines security best practices for using CaptiveClone. As a powerful security assessment tool, CaptiveClone must be used responsibly and securely to maintain the integrity and legality of your security testing activities.

## Legal and Ethical Considerations

### Authorization Requirements

- **Written Permission**: Always obtain explicit, written permission from the network owner before testing.
- **Scope Definition**: Clearly define the scope of testing in writing, including which networks will be tested.
- **Time Windows**: Agree on specific time windows for testing to minimize disruption.
- **Documentation**: Keep copies of all authorization documents during testing.

### Testing Boundaries

- **Stay Within Scope**: Only test networks explicitly listed in your authorization.
- **Avoid Service Disruption**: Limit deauthentication testing to minimize impact on legitimate users.
- **User Privacy**: Respect user privacy; do not intercept or store real user credentials unnecessarily.
- **Data Handling**: Have a clear plan for secure storage and disposal of any captured data.

## Secure Installation

### System Security

- **Dedicated System**: Use a dedicated system for CaptiveClone, preferably with full disk encryption.
- **System Updates**: Keep the operating system and all packages up-to-date.
- **Minimal Installation**: Install only necessary packages and tools.
- **Firewall**: Configure a firewall to restrict incoming connections to the system.

### User Permissions

- **Dedicated User**: Create a dedicated user account with limited privileges for running CaptiveClone.
- **Least Privilege**: Only elevate privileges when necessary for specific operations.
- **Secure Storage**: Store configuration files and credentials securely with appropriate permissions.

## Operational Security

### Network Operations

- **MAC Randomization**: Enable MAC address randomization for non-testing activities.
- **Separate Testing Network**: Use a separate network connection for internet access during testing.
- **VPN Usage**: Consider using a VPN for additional anonymity when appropriate.
- **RF Isolation**: When possible, conduct testing in an RF-isolated environment.

### Data Protection

- **Encryption**: Always enable encryption for stored credentials and sensitive data.
- **Key Management**: Securely manage and regularly rotate encryption keys.
- **Data Minimization**: Only collect the minimum data necessary for your assessment.
- **Secure Deletion**: Implement secure deletion procedures for test data after completion.

### Access Control

- **Authentication**: Always enable authentication for the web interface.
- **Strong Passwords**: Use strong, unique passwords for all accounts.
- **Session Management**: Enable session timeouts and automatic logouts.
- **IP Restriction**: Consider restricting web interface access to specific IP addresses.

## Secure Configuration

### Web Interface Security

- **HTTPS**: Enable HTTPS for the web interface using a valid SSL certificate.
- **CSRF Protection**: Ensure CSRF protection is enabled.
- **XSS Prevention**: Configure appropriate Content Security Policy headers.
- **Port Selection**: Use non-standard ports for the web interface to avoid casual discovery.

### API Security

- **API Keys**: Use API keys with appropriate expiration for programmatic access.
- **Rate Limiting**: Enable rate limiting to prevent abuse.
- **Input Validation**: Ensure all API inputs are properly validated.
- **Logging**: Enable comprehensive logging for API access.

### Reporting Security

- **Report Encryption**: Encrypt security reports containing sensitive information.
- **Secure Delivery**: Use secure channels for delivering reports to stakeholders.
- **Data Redaction**: Redact sensitive information from reports where appropriate.

## System Hardening

### File System Security

- **File Permissions**: Set appropriate file permissions for all CaptiveClone files.
- **Temporary Files**: Secure or disable temporary file creation when possible.
- **Log Rotation**: Implement log rotation to prevent disk space issues.

### Process Isolation

- **Container Usage**: Consider running CaptiveClone in a container for additional isolation.
- **Service Separation**: Run different components with different user accounts if possible.

### Monitoring and Alerting

- **Abnormal Usage**: Monitor for and alert on abnormal usage patterns.
- **Resource Monitoring**: Set up monitoring for system resources to detect issues.
- **Audit Logging**: Enable comprehensive audit logging for security events.

## Credential Management

### Stored Credentials

- **Encryption Method**: Use strong encryption (Argon2 for hashing, Fernet for encryption).
- **Key Protection**: Store encryption keys separately from encrypted data.
- **Regular Rotation**: Regularly rotate encryption keys and credentials.

### User Credentials

- **Strong Passwords**: Enforce strong password policies for user accounts.
- **MFA**: Enable multi-factor authentication when available.
- **Account Lockout**: Implement account lockout after failed login attempts.

## Testing Security

### Secure Testing Procedures

- **Pre-Testing Checklist**: Develop and follow a security checklist before each test.
- **Testing Time Windows**: Conduct testing during agreed-upon time windows.
- **Notifications**: Notify relevant parties before starting testing.
- **Monitoring**: Monitor the impact of testing on the target environment.

### Incident Response

- **Emergency Contacts**: Maintain a list of emergency contacts for the network being tested.
- **Rollback Plan**: Have a clear plan for rolling back changes if issues occur.
- **Issue Documentation**: Document any issues or incidents that occur during testing.

### Post-Testing

- **Data Cleanup**: Securely delete all captured data after testing is complete.
- **System Reset**: Reset systems to a known good state after testing.
- **Reporting**: Provide clear, detailed reports on testing activities and findings.

## Secure Development

If you're contributing to CaptiveClone development:

- **Code Review**: All code should undergo security-focused code review.
- **Dependency Scanning**: Regularly scan dependencies for known vulnerabilities.
- **Static Analysis**: Use static analysis tools to identify potential security issues.
- **Security Testing**: Implement security-focused tests for all components.

## Security Checklist

Use this checklist before conducting security testing with CaptiveClone:

- [ ] Obtained written permission for testing
- [ ] Defined and documented test scope
- [ ] Scheduled testing during approved time windows
- [ ] Notified relevant parties of testing schedule
- [ ] Verified system is up-to-date with security patches
- [ ] Enabled encryption for credential storage
- [ ] Configured authentication for web interface
- [ ] Set up secure communications (HTTPS)
- [ ] Tested in an isolated environment if possible
- [ ] Prepared incident response procedures
- [ ] Configured appropriate logging
- [ ] Planned for secure data disposal after testing

## Security Incident Response

If a security incident occurs during testing:

1. **Stop Testing**: Immediately halt all testing activities.
2. **Document**: Record the nature of the incident and any relevant details.
3. **Notify**: Inform the appropriate contacts as defined in your authorization.
4. **Contain**: Take steps to contain the incident and prevent further impact.
5. **Resolve**: Work with the network owner to resolve the issue.
6. **Review**: After resolution, review what happened and update procedures.

## Resources

- [OWASP Testing Guide](https://owasp.org/www-project-web-security-testing-guide/)
- [Pentest Standard](http://www.pentest-standard.org/)
- [WiFi Security Best Practices](https://www.ncsc.gov.uk/collection/device-security-guidance/infrastructure/wi-fi)

## Reporting Security Issues

If you discover a security issue in CaptiveClone itself, please report it responsibly to the project maintainers: 