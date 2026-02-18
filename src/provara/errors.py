"""
errors.py — Provara Protocol Error Taxonomy (Lane 2B)

Standardized error codes and messages that provide clear feedback and 
links to normative documentation.
"""

from typing import Optional, List

__all__ = [
    "ProvaraError",
    "HashMismatchError",
    "BrokenCausalChainError",
    "InvalidSignatureError",
    "HashFormatError",
    "KeyNotFoundError",
    "RequiredFieldMissingError",
    "VaultStructureInvalidError",
]

class ProvaraError(Exception):
    """Base class for all Provara-related errors."""
    def __init__(
        self, 
        code: str, 
        message: str, 
        context: Optional[str] = None,
        spec_sections: Optional[List[str]] = None
    ):
        self.code = code
        self.message = message
        self.context = context
        self.spec_sections = spec_sections or []
        
        full_msg = f"[{code}] {message}"
        if context:
            full_msg += f" Context: {context}"
        
        super().__init__(full_msg)

    @property
    def doc_url(self) -> str:
        """Link to the human-readable documentation for this error."""
        return f"https://provara.dev/errors/{self.code}"

# Core Integrity Errors (E0xx)
class HashMismatchError(ProvaraError):
    def __init__(self, context: Optional[str] = None):
        super().__init__("PROVARA_E001", "A stored or transmitted hash value does not equal the hash computed from the referenced data.", context, ["1", "6"])

class BrokenCausalChainError(ProvaraError):
    def __init__(self, context: Optional[str] = None):
        super().__init__("PROVARA_E002", "prev_event_hash does not equal the event_id of the actor's immediately preceding event.", context, ["7"])

class InvalidSignatureError(ProvaraError):
    def __init__(self, context: Optional[str] = None):
        super().__init__("PROVARA_E003", "Ed25519 signature verification failed.", context, ["2"])

# Format Errors (E1xx)
class HashFormatError(ProvaraError):
    def __init__(self, context: Optional[str] = None):
        super().__init__("PROVARA_E100", "A hash value is not exactly 64 lowercase hexadecimal characters.", context, ["1"])

# Key Management Errors (E2xx)
class KeyNotFoundError(ProvaraError):
    def __init__(self, context: Optional[str] = None):
        super().__init__("PROVARA_E204", "A key_id referenced in an event signature cannot be matched to any known public key in the vault.", context, ["2"])

# Schema Errors (E3xx)
class RequiredFieldMissingError(ProvaraError):
    def __init__(self, context: Optional[str] = None):
        super().__init__("PROVARA_E300", "A required field is absent from an event object.", context, ["4"])

class VaultStructureInvalidError(ProvaraError):
    def __init__(self, context: Optional[str] = None):
        super().__init__("PROVARA_E302", "The vault is missing required directories or files.", context, ["13"])
