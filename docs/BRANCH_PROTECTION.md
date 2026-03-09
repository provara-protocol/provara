# Branch Protection

This repository enforces merge gates on `main`.

## Required Status Checks

- `Smoke Managed Vault API / smoke-managed-vault`

## Notes

- If workflow or job names change, update this check context in GitHub branch protection.
- Keep smoke workflow names stable to avoid blocking merges unexpectedly.
