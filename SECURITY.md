# Security Policy

## Supported Versions

HotChords is actively developed. We support security updates for the current minor release:

| Version | Supported          |
| ------- | ------------------ |
| 0.4.x   | :white_check_mark: |
| 0.3.x   | :x:                |
| < 0.3.0 | :x:                |

---

## Reporting a Vulnerability

The HotChords team takes the security and privacy of our users seriously. Because HotChords runs entirely on local machines and does not maintain centralized servers, the majority of potential security concerns involve local file parsing, audio buffer handling, or untrusted network exposure when hosting on `0.0.0.0`.

If you discover a security vulnerability:

1. **Do NOT open a public GitHub issue** to report suspected vulnerabilities.
2. **Privately report** the issue through GitHub's [Private Vulnerability Reporting](https://github.com/itshotfix/HotChords/security/advisories/new) interface.
3. Include detailed steps to reproduce the vulnerability, including:
   - Operating system and Python version
   - Malicious or corrupted audio file payloads (if applicable)
   - Proof of concept scripts or reproduction steps
   - Potential impact of the vulnerability

We will acknowledge receipt within 48 hours and work with you to issue a patched release promptly.
