# Provara Protocol — Development Makefile
# Works in Git Bash (Windows), macOS, and Linux

SHELL := /bin/bash
PYTHONPATH := SNP_Core/bin
PYTHON := python
TEST_DIR := SNP_Core/test
REF_BACKPACK := SNP_Core/examples/reference_backpack

.PHONY: test test-unit test-comply bootstrap verify manifest checksums clean help

## ── Testing ──────────────────────────────────────────────

test: test-unit test-comply ## Run all 110 tests (unit + compliance)

test-unit: ## Run 93 unit tests
	cd $(TEST_DIR) && PYTHONPATH=../bin $(PYTHON) -m unittest test_reducer_v0 test_rekey test_bootstrap test_sync_v0 -v

test-comply: ## Run 17 compliance tests against reference backpack
	cd $(TEST_DIR) && PYTHONPATH=../bin $(PYTHON) backpack_compliance_v1.py ../examples/reference_backpack -v

test-vault: ## Run compliance tests against My_Backpack (if exists)
	@if [ -d "My_Backpack" ]; then \
		cd $(TEST_DIR) && PYTHONPATH=../bin $(PYTHON) backpack_compliance_v1.py ../../My_Backpack -v; \
	else \
		echo "No My_Backpack/ directory found. Run 'make bootstrap' first."; \
	fi

## ── Operations ───────────────────────────────────────────

bootstrap: ## Create a new vault with dual-key authority
	cd SNP_Core/bin && $(PYTHON) bootstrap_v0.py ../../My_Backpack --quorum --self-test

verify: ## Verify My_Backpack integrity (17 compliance tests)
	@if [ -d "My_Backpack" ]; then \
		./check_backpack.sh My_Backpack; \
	else \
		echo "No My_Backpack/ directory found."; \
	fi

manifest: ## Regenerate manifest for My_Backpack
	cd SNP_Core/bin && $(PYTHON) manifest_generator.py ../../My_Backpack --write

## ── Utilities ────────────────────────────────────────────

checksums: ## Regenerate CHECKSUMS.txt
	@echo "Regenerating CHECKSUMS.txt..."
	@find . -type f \
		! -path './.git/*' \
		! -path './__pycache__/*' \
		! -path './venv/*' \
		! -path './.venv/*' \
		! -path './My_Backpack/*' \
		! -path './Backups/*' \
		! -name 'CHECKSUMS.txt' \
		! -name '*.pyc' \
		! -name '.DS_Store' \
		! -name 'Thumbs.db' \
		-exec sha256sum {} \; | sort -k2 > CHECKSUMS.txt
	@echo "Done. $(shell wc -l < CHECKSUMS.txt) files hashed."

clean: ## Remove generated caches (not vaults or keys)
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -name '*.pyc' -delete 2>/dev/null || true

## ── Help ─────────────────────────────────────────────────

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'
