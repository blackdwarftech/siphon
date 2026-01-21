# Contributing to SIPHON

Thank you for your interest in contributing to **SIPHON**, a LiveKit-based telephony AI agent framework.

This document explains how to get set up for development, the types of contributions we welcome, and the standards we expect in this project.

---

## 1. Code of Conduct & Responsible Use

By participating in this project, you agree to follow the:

- **[SIPHON Code of Conduct](./CODE_OF_CONDUCT.md)**

In addition, because SIPHON is used for **telephony and AI calling systems**, we expect contributors to:

- Avoid building or promoting **harassing, deceptive, or non-consensual** calling flows.
- Respect **privacy, telecom, and AI-related regulations** in your jurisdiction.
- Treat call metadata, audio, and transcripts as **sensitive data** by default.

---

## 2. Ways to Contribute

### 2.1 Good first issues

- We may tag some GitHub issues with a label such as **"good first issue"** when they are well-scoped and suitable for newcomers.
- If you’d like to work on one, please leave a short comment like **“Can I take this?”** so maintainers can assign it to you and avoid duplicate work.

### 2.2 Bug reports

- Use the issue tracker to report reproducible bugs.
- Include environment details, SIP/telephony settings (without secrets), logs, and clear steps to reproduce.

### 2.3 Feature requests & design proposals

- Open an issue describing the **use case and motivation**, not only the implementation idea.
- For larger or potentially breaking changes, start with a brief design discussion (via GitHub issue, discussion, or the project’s preferred chat channel) before writing a lot of code.

### 2.4 Code contributions (PRs)

- Fix bugs or add features that align with SIPHON’s goals: LiveKit-based AI telephony, agents, and tooling.
- Keep changes focused and well-scoped; avoid huge PRs that mix unrelated changes.

### 2.5 Documentation & examples

- Improve docs, comments, and README sections.
- Add small examples for common patterns (e.g. inbound agent, outbound dialer, provider-specific configs).

---

## 3. Development Setup

### 3.1 Prerequisites

- Python **3.10+**
- Git
- A LiveKit cloud / self-hosted project (for actual telephony tests)
- Optionally: conda/virtualenv/uv/poetry to manage environments

### 3.2 Clone the repository

```bash
git clone https://github.com/blackdwarftech/siphon.git
cd siphon
```

### 3.3 Create a virtual environment (recommended)

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\\Scripts\\activate
```

### 3.4 Install SIPHON in editable mode

SIPHON uses `pyproject.toml` with `hatchling`. For local development, install dependencies in editable mode:

```bash
pip install -e .
```

This will install `siphon-ai` and all required runtime dependencies (LiveKit, providers, etc.).

### 3.5 Environment configuration

- Copy the example environment file:

```bash
cp .env.example .env
```

- Fill in the secrets and configuration required for your setup, for example:
  - LiveKit API keys / URLs
  - Provider API keys (OpenAI, Anthropic, Groq, Deepgram, etc.)
  - Storage / database connection strings if you want recording/metadata persistence

Do **not** commit real secrets to the repository.

---

## 4. Running SIPHON During Development

SIPHON is organized around:

- `siphon.agent`  – agent runner and core entrypoint.
- `siphon.telephony.inbound`  – inbound SIP trunk + dispatch helpers.
- `siphon.telephony.outbound`  – outbound call helpers.
- `siphon.plugins`  – model/STT/TTS provider integrations.

Typical workflows during development:

- **Run an agent worker locally** using `siphon.agent.runner.Agent`.
- **Configure inbound calling** via `siphon.telephony.inbound.Dispatch`.
- **Place outbound calls** via `siphon.telephony.outbound.Call`.

---

## 5. Coding Style & Guidelines

- **Python style**
  - Follow idiomatic Python and PEP 8 where practical.
  - Prefer explicit over implicit; write clear, maintainable code over clever one-liners.

- **Types**
  - Use type hints where reasonable.
  - Keep function signatures clear; use `Dict[str, Any]` only when the structure cannot be strongly typed yet.

- **Logging & errors**
  - Use the project’s `get_logger` helper for logging.
  - Include enough context in error logs to debug telephony/agent issues (IDs, trunk/number, but no secrets).

- **Abstractions**
  - Keep **LiveKit-specific wiring** localized in `siphon.telephony` and `siphon.agent.core`.
  - Keep provider-specific logic in `siphon.plugins.<provider>`; higher-level code should talk to provider-agnostic interfaces.

---

## 6. Tests & Quality

If/when tests are added to the project:

- Write tests for new behavior where possible.
- Ensure existing tests pass before opening a PR.

Example:

```bash
pytest
```

If there is no test suite yet, consider contributing small, focused tests around:

- SIP trunk helpers (inbound/outbound trunk creation and lookup).
- Metadata handling in `siphon.agent.core.entrypoint`.
- Provider config parsing in `siphon.agent.agent_components`.

---

## 7. Pull Request Process

1. **Fork** the repository and create a feature branch:

   ```bash
   git checkout -b feature/my-change
   ```

2. **Make your changes** in small, logical commits.

3. **Add or update documentation** if your change affects public APIs, configuration, or behavior.

4. **Run tests / sanity checks** locally.

5. **Open a Pull Request**
   - In the PR description, briefly explain:
     - What changed.
     - Why the change is needed (link the related issue if there is one).
     - How you tested it (and whether it might be a breaking change).
   - If relevant, mention how it impacts telephony flows or AI/LLM behavior.

6. Engage in review
   - Be open to feedback and iterate as needed.

Once tests pass and reviews are resolved, a maintainer will merge your PR (often using squash-merge to keep history tidy).

---

## 8. Security, Privacy & Abuse

If you discover a vulnerability, privacy issue, or a way SIPHON could be abused in production deployments, please **do not** open a public issue with exploit details.

Instead, contact the maintainers privately so we can assess and respond responsibly.

---

## 9. Questions & Support

If you’re unsure how best to contribute or want guidance on an idea:

- Open a GitHub issue marked as **question** or **proposal**.
- Or reach out via the project’s listed contact channels.

Thank you again for helping improve SIPHON!