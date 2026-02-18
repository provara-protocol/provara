# Provara Verify GitHub Action

This GitHub Action verifies the cryptographic integrity and protocol compliance of a Provara vault (Backpack). It runs all 17 normative compliance tests defined in the Provara Protocol v1.0.

## Usage

Add this step to your GitHub Actions workflow:

```yaml
jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          
      - name: Provara Verify
        uses: provara-protocol/provara/tools/provara-verify-action@main
        with:
          path: 'path/to/your/vault'
          verbose: true
```

## Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `path` | Path to the vault directory relative to the repository root. | Yes | `vault` |
| `verbose` | If set to `true`, the action will output detailed test results for each of the 17 compliance checks. | No | `false` |

## Why use this?

Provara vaults are designed for 50-year longevity. By verifying your vault on every push, you ensure that:
1. **Chain Integrity:** The causal event chain is unbroken.
2. **Signature Validity:** Every event is correctly signed by an authorized actor.
3. **Merkle Consistency:** All files in the vault match the signed manifest.
4. **Spec Compliance:** The vault remains compliant with the Provara Protocol v1.0.

## License

This action is licensed under the Apache 2.0 License, just like the Provara Protocol.
