# `cli`

provara.py — Unified CLI for Provara Protocol v1.0

Commands:
  init      Create a new Memory Vault (Backpack)
  verify    Run all integrity and compliance checks
  backup    Create an integrity-verified timestamped backup
  manifest  Regenerate manifest.json and Merkle root
  checkpoint Create a signed state snapshot for faster loading
  replay    Show current derived belief state
  append    Append a signed observation or assertion

## Functions

### `cmd_init(args: argparse.Namespace) -> None`

Handle ``provara init``.

Args:
    args: Parsed CLI arguments containing vault path/bootstrap options.

Returns:
    None: Writes vault files and prints result details.

### `cmd_verify(args: argparse.Namespace) -> None`

Handle ``provara verify`` integrity/compliance execution.

Args:
    args: Parsed CLI arguments with target vault and verbosity.

### `cmd_backup(args: argparse.Namespace) -> None`

Handle ``provara backup``.

Args:
    args: Parsed CLI arguments with source vault and backup settings.

### `cmd_manifest(args: argparse.Namespace) -> None`

Handle ``provara manifest`` regeneration.

Args:
    args: Parsed CLI arguments with target vault path.

### `cmd_checkpoint(args: argparse.Namespace) -> None`

Handle ``provara checkpoint``.

Args:
    args: Parsed CLI arguments with vault path and keyfile path.

### `cmd_replay(args: argparse.Namespace) -> None`

Handle ``provara replay`` state reconstruction.

Args:
    args: Parsed CLI arguments with vault path.

### `cmd_append(args: argparse.Namespace) -> None`

Handle ``provara append`` event creation/signing.

Args:
    args: Parsed CLI arguments including type, payload, and signing keys.

### `cmd_redact(args: argparse.Namespace) -> None`

No docstring provided.

### `cmd_market_alpha(args: argparse.Namespace) -> None`

Handle ``provara market-alpha``.

Args:
    args: Parsed CLI arguments for market signal attributes.

### `cmd_hedge_fund_sim(args: argparse.Namespace) -> None`

Handle ``provara hedge-fund-sim``.

Args:
    args: Parsed CLI arguments for simulation result attributes.

### `cmd_oracle_validate(args: argparse.Namespace) -> None`

Handle ``provara oracle-validate``.

Args:
    args: Parsed CLI arguments for oracle attestation run.

### `cmd_resume(args: argparse.Namespace) -> None`

Handle ``provara resume`` output generation.

Args:
    args: Parsed CLI arguments with vault path.

### `cmd_check_safety(args: argparse.Namespace) -> None`

Handle ``provara check-safety`` policy decision lookup.

Args:
    args: Parsed CLI arguments with action class and vault path.

### `cmd_wallet_export(args: argparse.Namespace) -> None`

Handle ``provara wallet-export``.

Args:
    args: Parsed CLI arguments with source keyfile and output path.

### `cmd_wallet_import(args: argparse.Namespace) -> None`

Handle ``provara wallet-import``.

Args:
    args: Parsed CLI arguments containing Solana keypair path.

### `cmd_agent_loop(args: argparse.Namespace) -> None`

Handle ``provara agent-loop`` autonomous cycle execution.

Args:
    args: Parsed CLI arguments for loop cycles and actor identity.

### `cmd_send_message(args: argparse.Namespace) -> None`

Handle ``provara send-message`` encrypted P2P dispatch.

Args:
    args: Parsed CLI arguments with sender/recipient key material.

### `cmd_read_messages(args: argparse.Namespace) -> None`

Handle ``provara read-messages`` inbox decryption.

Args:
    args: Parsed CLI arguments with vault and recipient keys.

### `cmd_timestamp(args: argparse.Namespace) -> None`

Handle ``provara timestamp`` external TSA anchoring.

Args:
    args: Parsed CLI arguments for TSA URL and signing key file.

### `cmd_export(args: argparse.Namespace) -> None`

Export vault with SCITT events to standalone bundle.

### `cmd_scitt_statement(args: argparse.Namespace) -> None`

Handle ``provara scitt statement`` event creation.

Args:
    args: Parsed CLI arguments for SCITT statement metadata.

### `cmd_scitt_receipt(args: argparse.Namespace) -> None`

Handle ``provara scitt receipt`` event creation.

Args:
    args: Parsed CLI arguments for SCITT receipt metadata.

### `main() -> None`

CLI entrypoint.

Parses command-line arguments, routes to a subcommand handler, and exits
with subcommand status semantics.
