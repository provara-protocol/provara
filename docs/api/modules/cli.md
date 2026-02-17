# CLI

**Module:** `src/provara/cli.py`

Command-line interface for vault operations.

## Commands

### `provara init <path>`

Create a new vault.

```bash
provara init My_Backpack
```

### `provara verify <vault>`

Verify vault integrity (17 compliance tests).

```bash
provara verify My_Backpack
```

### `provara append <vault> <event.json>`

Add an event to the vault.

```bash
provara append My_Backpack event.json
```

### `provara sync <vault_a> <vault_b> <output>`

Merge two vaults.

```bash
provara sync Desktop_Vault Phone_Vault Merged_Vault
```

### `provara export <vault> --format markdown`

Export vault as markdown.

```bash
provara export My_Backpack --format markdown > vault.md
```

## References

- [Provara: CLI Usage](https://provara.dev/docs/)
