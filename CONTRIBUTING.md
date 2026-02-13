# Contributing to Provara Protocol

Welcome, and thank you for your interest in contributing to the Provara Protocol (formerly SNP Legacy Kit). Provara is a Python-based cryptographic memory vault protocol developed by Hunt Information Systems. It uses Ed25519 signatures, SHA-256 hashing, and RFC 8785 canonical JSON to provide verifiable, tamper-evident memory vaults.

This document explains how to get involved, what we expect from contributions, and how the project is structured.

---

## Code of Conduct

We expect all participants to act professionally and respectfully. In short:

- Be constructive in discussions, code reviews, and issue reports.
- Assume good faith from other contributors.
- Provide clear, actionable feedback rather than dismissive commentary.
- Harassment, personal attacks, and discriminatory language will not be tolerated.

Maintainers reserve the right to remove, edit, or reject contributions that do not meet these standards.

---

## How to Contribute

### Bug Reports

If you find a bug, please open an issue and include:

- A clear description of the problem.
- Steps to reproduce the issue.
- Expected behavior vs. actual behavior.
- Python version, OS, and `cryptography` library version.
- Any relevant tracebacks or log output.

### Feature Requests

Feature requests are welcome. Open an issue describing:

- The problem you are trying to solve.
- Your proposed approach or solution.
- Whether you are willing to implement it yourself.

Please note that protocol-level changes follow a separate process (see [Protocol Changes](#protocol-changes) below).

### Code Contributions

Code improvements, bug fixes, documentation corrections, and new test cases are all welcome. For anything beyond a trivial fix, consider opening an issue first to discuss the approach before investing significant effort.

---

## Development Setup

1. **Clone the repository:**

   ```
   git clone https://github.com/hunt-information-systems/provara-protocol.git
   cd provara-protocol
   ```

2. **Create a virtual environment (recommended):**

   ```
   python -m venv venv
   source venv/bin/activate        # Linux / macOS
   venv\Scripts\activate           # Windows
   ```

3. **Install dependencies:**

   ```
   pip install cryptography>=41.0
   ```

   The project has a single runtime dependency: `cryptography >= 41.0`. Python 3.10 or later is required.

4. **Verify your setup by running the test suite:**

   ```
   python -m pytest
   ```

---

## Testing Requirements

The project maintains a suite of 74 tests (57 unit tests and 17 compliance tests). All tests must pass before you submit a pull request.

Run the full test suite:

```
python -m pytest
```

Run with verbose output:

```
python -m pytest -v
```

Run only unit tests or compliance tests as needed during development, but always confirm the full suite passes before submitting.

If your change adds new functionality, include corresponding tests. If your change fixes a bug, include a regression test that fails without the fix and passes with it.

---

## Pull Request Process

1. **Fork the repository** and create a feature branch from `main`.
2. **Keep changes focused.** One logical change per pull request.
3. **Write clear commit messages** that explain what changed and why.
4. **Ensure all 74 tests pass** with no failures or errors.
5. **Update documentation** if your change affects usage or behavior.
6. **Describe your PR clearly.** Include:
   - What the change does.
   - Why it is needed.
   - How it was tested.
   - Any breaking changes or migration notes.
7. **Be responsive to review feedback.** Maintainers may request changes before merging.

Pull requests that introduce test failures, reduce coverage without justification, or lack a clear description will not be merged.

---

## Protocol Changes

The file `PROTOCOL_PROFILE.txt` defines the canonical specification for the Provara Protocol. **This file is frozen.** Direct modifications to the protocol profile will not be accepted through regular pull requests.

If you believe a protocol-level change is necessary, it must go through an RFC process:

1. Open an issue tagged as an RFC.
2. Describe the proposed change, its motivation, and its impact on existing implementations and test vectors.
3. Allow time for community and maintainer discussion.
4. Protocol changes will only be accepted after thorough review and with maintainer approval.

Code improvements, performance optimizations, better error handling, and new tests that operate within the existing protocol specification are always welcome without an RFC.

---

## Style Guide

- Follow the existing code conventions in the project. Consistency matters more than personal preference.
- Use type hints where they are already present in the codebase. Add them to new code where practical.
- Keep functions focused and reasonably sized.
- Write docstrings for public functions, classes, and modules.
- Use meaningful variable and function names.
- Avoid introducing new dependencies unless absolutely necessary and discussed in advance.
- Format code cleanly. If the project uses a formatter or linter configuration, follow it.

---

## Reimplementations in Other Languages

Reimplementations of the Provara Protocol in other languages are welcomed and encouraged. The protocol is designed to be language-agnostic.

To build a compliant implementation:

- Use `PROTOCOL_PROFILE.txt` as the authoritative specification. Your implementation must conform to the protocol as defined there.
- Use the existing test vectors to validate your implementation against the reference behavior.
- If you build a reimplementation, consider opening an issue or discussion to let the community know. We are happy to link to conforming implementations.

---

## Questions

If you have questions about contributing that are not covered here, open an issue and we will do our best to help.

Thank you for contributing to Provara Protocol.
