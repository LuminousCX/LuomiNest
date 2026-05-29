# Security Policy

## Supported Versions

Security fixes are applied to the latest code on the `main` branch.

| Version | Supported |
| ------- | ---------- |
| main    | ✅ |
| 0.1.x   | ✅ |

## Reporting a Vulnerability

**Do not report security vulnerabilities in public GitHub Issues!**

Please report privately via email:

- Email: `luminouschenxi@outlook.com`
- Subject: `LuomiNest Security Report`

### What to Include

Please include:

- A clear description of the issue
- Steps to reproduce
- Affected versions or commit hashes
- Potential impact assessment
- Suggested fix or mitigation (optional)

### Response Expectations

- Initial acknowledgment target: within 72 hours
- Status updates shared via email while triage is in progress

### Responsible Disclosure

Please allow time for investigation and remediation before public disclosure.

## Security Best Practices

### API Keys and Secrets

**Never hardcode sensitive information in code!**

- Use environment variables to store API Keys
- Use `.env.example` as template, do not commit `.env` files
- Use secure key management services in production

### Database Security

- Always use parameterized queries to prevent SQL injection
- Do not log sensitive data
- Update database passwords regularly

### Authentication

- Use strong password policies
- Set reasonable expiration times for JWT Tokens
- Implement proper access control (RBAC)

### Network Security

- Use HTTPS in production
- Use WSS for WebSocket connections
- Use TLS encryption for MQTT

## Security Features

LuomiNest includes the following security features:

- JWT authentication mechanism
- OAuth integration
- AES data encryption
- TLS/SSL support
- RBAC permission control
- Security audit logs
- Parameterized SQL queries

## Security Audit

We conduct regular security audits:

- Code review process includes security checks
- Dependency vulnerability scanning
- Automated security testing

---

Thank you for helping keep LuomiNest secure!