# Security Policy

## Supported Versions

Security fixes are applied to the latest code on the `master` branch and backported
to the most recent stable release when applicable.

| Version | Supported |
| ------- | --------- |
| master  | ✅ |
| 0.7.x   | ✅ |
| 0.1.x   | ❌ |

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
- A patch and release advisory will be coordinated before public disclosure

### Responsible Disclosure

Please allow time for investigation and remediation before public disclosure.
We ask reporters to follow the [Coordinated Disclosure](https://en.wikipedia.org/wiki/Coordinated_vulnerability_disclosure)
guideline and refrain from sharing details publicly until a fix is available.

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
- All WebSocket connections require authentication

### Network Security

- Use HTTPS in production
- Use WSS for WebSocket connections
- Use TLS encryption for MQTT

### Command and Prompt Security

- Run untrusted commands inside the local sandbox
- Command Guard and rate limiting are enabled by default
- Prompt injection filters are applied to user input

## Security Features

LuomiNest includes the following security features:

- JWT authentication mechanism (local token issuance and validation)
- OAuth integration
- AES-256 data encryption
- TLS/SSL support
- RBAC permission control
- Local sandbox for untrusted commands
- Command Guard and command policy enforcement
- Rate limiting (SlowAPI)
- Prompt security filtering
- Security audit logs
- Parameterized SQL queries
- WebSocket connection authentication
- Safe URL validation for external requests

## Security Audit

We conduct regular security audits:

- Code review process includes security checks (CodeRabbit)
- Dependency vulnerability scanning
- Automated security testing

---

Thank you for helping keep LuomiNest secure!
