# Contributing to Provara

**Self-sovereign cryptographic event logs.**

Thank you for your interest in contributing to Provara! This document provides guidelines and instructions for contributing to the project.

---

## Welcome

Provara is a protocol for append-only cryptographic event logs with per-actor causal chains, deterministic replay, and 50-year readability guarantees. We welcome contributions from anyone interested in verifiable audit trails, AI governance, supply chain provenance, or long-term data preservation.

Whether you're reporting a bug, suggesting a feature, writing documentation, or implementing the protocol in a new language, your contributions help make Provara more robust and accessible.

---

## Ways to Contribute

### 1. Report Bugs

Found a bug? Open an issue using the [bug report template](.github/ISSUE_TEMPLATE/bug_report.md).

**Before reporting:**
- Search existing issues to avoid duplicates.
- Verify the bug exists in the latest version.
- Include steps to reproduce, expected behavior, and actual behavior.

### 2. Suggest Features

Have an idea? Start a [GitHub Discussion](https://github.com/provara-protocol/provara/discussions) or open a [feature request issue](.github/ISSUE_TEMPLATE/feature_request.md).

**Before suggesting:**
- Check existing discussions and issues.
- Consider whether the feature aligns with Provara's design goals.
- Be prepared to discuss trade-offs.

### 3. Write Documentation

Documentation improvements are always welcome:
- Fix typos or unclear explanations.
- Add examples or tutorials.
- Improve API documentation.
- Translate documentation into other languages.

### 4. Add Test Coverage

Help us maintain reliability:
- Add unit tests for uncovered code paths.
- Add integration tests for complex workflows.
- Add property-based tests for invariants.
- Add fuzzing tests for edge cases.

### 5. Build Plugins/Extensions

Extend Provara without modifying core:
- Custom event types (see [docs/PLUGIN_API.md](docs/PLUGIN_API.md)).
- Custom reducers for domain-specific state derivation.
- Custom export formats (CSV, SIEM, legal bundles).

### 6. Implement in New Languages

Provara is designed for cross-language implementation:
- Read [PROTOCOL_PROFILE.txt](PROTOCOL_PROFILE.txt) for normative requirements.
- Validate against [test_vectors/vectors.json](test_vectors/vectors.json).
- Run the [17 compliance tests](tests/backpack_compliance_v1.py).
- Share your implementation with the community.

---

## Development Setup

### Prerequisites

- **Python 3.10+** — [python.org](https://python.org)
- **Git** — [git-scm.com](https://git-scm.com)
- **Node.js 20+** (for playground) — [nodejs.org](https://nodejs.org)

### Clone and Install

```bash
# Clone the repository
git clone https://github.com/provara-protocol/provara
cd provara

# Install Python dependencies
pip install -e ".[dev]"

# Install Node.js dependencies (for playground)
cd playground && npm install && cd ..
```

### Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/provara --cov-report=html

# Run specific test suite
pytest tests/test_plugins.py -v

# Run compliance tests
python tests/backpack_compliance_v1.py tests/fixtures/reference_backpack -v
```

### Type Checking

```bash
# Run mypy (strict mode)
mypy --strict src/provara/
```

### Code Formatting

```bash
# Format code with ruff
ruff format src/ tests/

# Lint code
ruff check src/ tests/
```

---

## Code Standards

### Conventional Commits

We use [Conventional Commits](https://www.conventionalcommits.org/) for commit messages:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types:**
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `test:` Test additions or fixes
- `chore:` Maintenance tasks
- `refactor:` Code refactoring
- `perf:` Performance improvements

**Examples:**
```
feat(plugins): add custom event type validation
fix(crypto): handle edge case in Ed25519 signature verification
docs: update PLUGIN_API.md with export examples
test: add fuzzing tests for canonical JSON
chore(deps): bump cryptography to 42.0.0
```

### Code Quality Requirements

All contributions must:

- **Pass mypy --strict:** No type errors allowed.
- **Maintain coverage:** Coverage must not decrease.
- **Pass all tests:** CI must be green before merge.
- **No new dependencies:** Runtime dependencies require discussion.
- **Follow existing patterns:** Match code style and architecture.

### Testing Requirements

All code changes must include tests:

| Change Type | Test Requirement |
|-------------|------------------|
| Bug fix | Regression test for the bug |
| New feature | Unit tests + integration tests |
| Refactoring | Existing tests must pass |
| Performance | Benchmark comparison |

### Security Guidelines

- Never commit secrets, API keys, or credentials.
- Use environment variables for sensitive configuration.
- Validate all external inputs.
- Follow cryptographic best practices (see [PROTOCOL_PROFILE.txt](PROTOCOL_PROFILE.txt)).

---

## Pull Request Process

### Before Opening a PR

1. **Fork the repository** and create a branch:
   ```bash
   git checkout -b feat/my-feature
   ```

2. **Make your changes** following code standards.

3. **Run tests locally:**
   ```bash
   pytest
   mypy --strict src/provara/
   ruff check src/ tests/
   ```

4. **Update documentation** if behavior changes.

5. **Commit with conventional commits:**
   ```bash
   git commit -m "feat(scope): add my feature"
   ```

### Opening a PR

1. **Fill out the PR template** (what, why, how, testing).

2. **Link related issues** (e.g., "Closes #123").

3. **Add reviewers** familiar with the affected code.

4. **Wait for CI** — all checks must pass.

### PR Template

```markdown
## What

Brief description of changes.

## Why

Motivation and context. Link to issues.

## How

Implementation details and design decisions.

## Testing

- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Compliance tests pass
- [ ] mypy --strict passes
- [ ] Coverage maintained

## Checklist

- [ ] Code follows project conventions
- [ ] Documentation updated
- [ ] No new warnings
- [ ] Breaking changes documented
```

### Review Process

1. **CI must be green** — automated checks pass.
2. **One approval required** — from a maintainer.
3. **Address feedback** — respond to review comments.
4. **Squash commits** — if requested by maintainer.
5. **Merge** — maintainer merges the PR.

---

## Architecture Overview

### Repository Structure

```
provara/
├── src/provara/          # Core Python package
│   ├── bootstrap_v0.py   # Vault initialization
│   ├── reducer_v0.py     # Deterministic reducer
│   ├── reducer_v1.py     # Streaming reducer
│   ├── sync_v0.py        # Sync protocol
│   ├── plugins.py        # Plugin system
│   ├── cli.py            # Command-line interface
│   └── mcp/              # MCP server
├── tests/                # Test suites
│   ├── test_*.py         # Unit tests
│   ├── fuzz/             # Fuzzing tests
│   └── fixtures/         # Test fixtures
├── docs/                 # Documentation
│   ├── PLUGIN_API.md     # Plugin specification
│   ├── EXTENSION_REGISTRY.md
│   └── draft-hunt-provara-protocol-00.xml  # IETF I-D
├── examples/             # Example code
│   └── plugins/          # Example plugins
├── tools/                # Development tools
│   ├── benchmarks/       # Performance benchmarks
│   └── ietf/             # I-D build tools
├── playground/           # Browser playground
└── PROTOCOL_PROFILE.txt  # Frozen specification
```

### Key Modules

| Module | Purpose |
|--------|---------|
| `bootstrap_v0.py` | Vault initialization with Ed25519 keys |
| `reducer_v0.py` | Full replay reducer (deterministic) |
| `reducer_v1.py` | Streaming reducer (performance) |
| `sync_v0.py` | Multi-device sync with fork detection |
| `plugins.py` | Plugin registry and discovery |
| `cli.py` | Unified CLI interface |
| `mcp/` | Model Context Protocol server |

### PROTOCOL_PROFILE.txt

**This file is immutable.** It is the frozen normative specification for Provara v1.0. Do not modify it.

If you find an error or ambiguity:
1. Open a GitHub issue describing the problem.
2. Propose a fix in a new profile version (e.g., PROTOCOL_PROFILE_v1.1.txt).
3. Discuss with maintainers before implementing.

---

## Extension Development

### Plugin API

Provara supports three extension points:

1. **Custom Event Types** — Define new event types with JSON Schema validation.
2. **Custom Reducers** — Add derived state computation.
3. **Custom Export Formats** — Export to CSV, SIEM, legal bundles.

See [docs/PLUGIN_API.md](docs/PLUGIN_API.md) for the full specification.

### Extension Registry

To propose a new event type for community adoption:

1. Read [docs/EXTENSION_REGISTRY.md](docs/EXTENSION_REGISTRY.md).
2. Open a GitHub issue with your proposal.
3. Include: type name, schema, security considerations.
4. Wait for community review.

### Example Plugin

See [examples/plugins/audit_plugin/](examples/plugins/audit_plugin/) for a complete working plugin:

```bash
# Install the example plugin
cd examples/plugins/audit_plugin
pip install -e .

# List plugins (should show audit plugin)
provara plugins list

# Use custom event type
provara append my-vault --type com.example.audit.login \
  --data '{"user_id":"alice","success":true,"ip_address":"192.168.1.1"}'
```

---

## Code of Conduct

We follow the [Contributor Covenant 2.1](CODE_OF_CONDUCT.md). Key points:

- Be respectful and inclusive.
- Accept constructive criticism.
- Focus on what's best for the community.
- Report unacceptable behavior to conduct@provara.dev.

---

## Security Policy

See [SECURITY.md](SECURITY.md) for our security policy.

**To report a vulnerability:**
1. Email security@provara.dev (do not open a public issue).
2. Include: description, steps to reproduce, impact assessment.
3. We will respond within 48 hours.
4. We request 90 days for patch development before public disclosure.

**Scope:**
- Cryptographic vulnerabilities (signature bypass, hash collisions).
- Remote code execution.
- Data corruption or loss.
- Authentication bypass.

**Out of scope:**
- Denial of service (availability is user responsibility).
- Information disclosure (Provara does not encrypt).
- Social engineering.

---

## Questions?

- **General questions:** [GitHub Discussions](https://github.com/provara-protocol/provara/discussions)
- **Bug reports:** [GitHub Issues](https://github.com/provara-protocol/provara/issues)
- **Security issues:** security@provara.dev
- **Conduct issues:** conduct@provara.dev

---

## Thank You

Your contributions make Provara better for everyone. Whether you're fixing a typo, adding a test, or implementing the protocol in a new language, we appreciate your time and effort.

**Golden Rule:** *Truth is not merged. Evidence is merged. Truth is recomputed.*
