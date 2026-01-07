# Security Policy for SIPHON

SIPHON is a LiveKit-based telephony AI agent framework. We take the security and privacy of deployments built with SIPHON seriously.

This document explains how to report vulnerabilities and how we handle security issues.

---

## Reporting a Vulnerability

If you discover a security vulnerability in SIPHON, please report it **responsibly and privately** to our security/contact team:

- Email: `siphon@blackdwarf.in`

⚠️ **Please do not open public GitHub issues for security vulnerabilities.** Issues and pull requests are public by default, which can put users at risk if details of a vulnerability are disclosed before a fix is available.

When reporting, please include (as applicable):

- A clear, detailed description of the vulnerability.
- Steps to reproduce the issue.
- Any relevant logs, screenshots, or proof-of-concept code.
- The environment in which you found the issue (e.g. SIPHON version, LiveKit setup, OS, dependencies).

We will acknowledge your report as soon as reasonably possible and work with you to investigate and resolve the issue.

---

## Scope

This policy covers security issues related to:

- The **SIPHON open-source framework** and its official packages.
- Example and reference implementations in this repository that use SIPHON.

It does **not** cover:

- Third-party services or infrastructure (e.g. your own LiveKit deployment, cloud providers, external APIs).
- Custom applications built on top of SIPHON by third parties, unless they expose a vulnerability in SIPHON itself.

If you are unsure whether something falls under this scope, you are still encouraged to contact us; we can help triage and redirect as needed.

---

## Response & Disclosure

Our general process for handling security reports is:

1. **Acknowledge** receipt of your report as soon as we can.
2. **Investigate and verify** the issue, including impact and affected versions.
3. **Develop and test a fix** or mitigation.
4. **Release updates** (new versions or patches) as soon as practical once a fix is verified.
5. **Communicate**:
   - We may publish release notes or advisories describing the issue and the fix, after users have a reasonable opportunity to update.
   - We may credit reporters who wish to be acknowledged, provided doing so does not create additional risk.

Timelines may vary depending on severity and complexity, but we aim to handle all good-faith reports promptly and professionally.

---

## Thank You

Thank you for helping keep SIPHON and the systems built on top of it secure. Responsible disclosure from the community is an important part of maintaining a safe telephony and AI ecosystem.
