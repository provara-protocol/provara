# 🎒 Provara Vault Backup Guide — AI Hedge Fund

This project uses the **Provara Protocol** to maintain a verifiable, cryptographic audit trail of all trading signals and decisions.

## 📍 Vault Locations

*   **Project Vault:** `data/signal_vault/` (Signals, Risks, Decisions, Executions)
*   **Global Memory:** `~/.provara/agent-memory/` (Shared agent decisions/milestones)

## 🔑 Security (THE GOLDEN RULE)

**⚠️ NEVER SYNC THE ROOT KEYS TO THE CLOUD.**
The `data/keys/vault_root.json` file contains your Ed25519 private keys. If you lose these, the vault is unreadable. If they are stolen, your audit trail is compromised.
*   **Action:** Store keys in an encrypted password manager (Bitwarden, 1Password, etc.).
*   **Git Status:** These are already ignored via `data/keys/.gitignore`.

## ☁️ Cloud Sync (Rclone)

We use `rclone` to synchronize the vault to Google Drive.

### 🔄 Manual Sync Command
```bash
rclone sync "/home/syncshadow7/ai hedge fund/ai-hedge-fund/data/signal_vault" "gdrive:backups/ai-hedge-fund/signal_vault" -P
```

### 🧠 Global Agent-Memory Sync
```bash
rclone sync "/home/syncshadow7/.provara/agent-memory" "gdrive:backups/provara/agent-memory" -P
```

## 🛠️ Maintenance

1.  **Verify Integrity:** Before backing up, run `provara verify data/signal_vault`.
2.  **Snapshot:** Use `provara backup` to create compressed snapshots if you want a versioned history.

---
*Created by Gemini CLI (The Scout) — 2026-03-01* 🔭
