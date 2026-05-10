"""Basic Solana address validation (Devnet demo)."""

import re

_BASE58_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")


def is_valid_solana_address(value: str) -> bool:
    s = (value or "").strip()
    if not s or not _BASE58_RE.match(s):
        return False
    try:
        from solders.pubkey import Pubkey

        Pubkey.from_string(s)
        return True
    except Exception:
        return False
