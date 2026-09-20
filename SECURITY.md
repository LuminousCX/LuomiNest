# Security Policy

[English](SECURITY.md) | [简体中文](SECURITY_zh.md) | [日本語](SECURITY_ja.md)

The LuomiNest team takes the security and privacy of our software and user data very seriously. This policy outlines our supported versions, vulnerability reporting process, and baseline security practices.

---

## Supported Versions

Security patches are actively applied to the `master` branch and released in minor patch updates for supported versions.

| Version | Supported | Status |
| ------- | --------- | ------ |
| `master` branch | ✅ | Actively developed |
| `0.8.x` | ✅ | Current stable release branch |
| `0.7.x` | ⚠️ | Security critical fixes only |
| `< 0.7.0` | ❌ | End of Life (upgrade recommended) |

---

## Reporting a Vulnerability

**Please do NOT report security vulnerabilities through public GitHub Issues or public pull requests!**

If you discover a security vulnerability or suspect a security flaw in LuomiNest, please report it privately via email:

- **Email**: [luminouschenxi@outlook.com](mailto:luminouschenxi@outlook.com)
- **Subject**: `[SECURITY] LuomiNest Vulnerability Report`

### What to Include in Your Report
To help us triage and resolve the issue quickly, please provide:
1. **Description**: A clear summary of the vulnerability and its potential impact.
2. **Reproduction Steps**: Step-by-step instructions or a Minimal Working Example (PoC) to reproduce the vulnerability.
3. **Affected Versions**: The release version, commit hash, or affected operating environment (Windows / Linux / macOS / Docker).
4. **Proposed Fix / Mitigation**: Any suggested remediation steps or code patches (if available).

### Response SLA & Coordination
- **Initial Acknowledgment**: We target an initial response within **72 hours** of receiving your report.
- **Triage & Patching**: We will assess the severity, keep you updated on progress, and prepare a fix privately.
- **Coordinated Disclosure**: We follow the principle of [Coordinated Vulnerability Disclosure](https://en.wikipedia.org/wiki/Coordinated_vulnerability_disclosure). We kindly request that you allow sufficient time for remediation before any public disclosure. Once fixed, release notes will credit your contribution (unless you prefer anonymity).

---

## Security Architecture & Built-in Protections

LuomiNest incorporates multi-layered security controls designed for safe multi-user agent execution:

1. **Authentication & Token Governance**:
   - Dual-mode JWT and local internal token authentication for API and WebSocket connections.
   - Granular RBAC definitions and route-level dependency injection guardrails.
2. **Local Isolation & Command Sandbox**:
   - Untrusted system command tools run through a Command Guard with whitelist enforcement.
   - Built-in sandboxing prevents unauthorized system tampering or arbitrary code execution.
3. **Prompt Safety & Injection Filtering**:
   - Built-in defense against prompt injection and jailbreak payloads across user inputs and external platform adapters.
4. **Data Privacy & Storage Encryption**:
   - 100% local database storage (SQLite in WAL mode) for conversation histories and distilled memory.
   - AES-256 encryption for stored provider credentials and sensitive keys in application settings.
5. **Rate Limiting & Anti-Abuse**:
   - Request throttling using SlowAPI middleware on critical authentication and dialogue endpoints.
6. **Diagnostic Privacy Redaction**:
   - Exported and uploaded diagnostic logs automatically redact authentication tokens, private credentials, and binary attachments. Logs are never uploaded without explicit user action.

---

## Security Best Practices for Operators & Developers

- **Secrets Handling**: Never commit `.env` files or hardcode API keys. Use `.env.example` as a template and set production secrets via environment variables.
- **Network Deployment**: Always front public deployments with TLS/HTTPS for web traffic and WSS for WebSockets. Ensure MQTT brokers utilize encrypted TLS ports.
- **Sandboxed Execution**: Keep the Command Guard and sandbox enabled when allowing autonomous Agent tool calls on production systems.

---

## Security Auditing

We practice continuous security assessment:
- Automated code reviews and security policy verification (CodeRabbit).
- Automated dependency vulnerability scanning.
- Regular integration test suites verifying authentication barriers and domain access controls.

Thank you for helping keep LuomiNest and our community secure!
