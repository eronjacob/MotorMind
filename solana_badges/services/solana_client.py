"""
Solana Devnet memo transactions for skill badge claims.

Uses the official Memo program. Issuer keypair pays fees and signs the memo.
"""

from __future__ import annotations

import json
import logging
import os
from typing import TYPE_CHECKING, Any

from django.conf import settings

if TYPE_CHECKING:
    from solana_badges.models import SkillBadge

logger = logging.getLogger(__name__)

MEMO_PROGRAM_ID_STR = "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr"
LAMPORTS_PER_SOL = 1_000_000_000
# Devnet base fee + small headroom for a single memo ix (~5k lamports typical).
MIN_ISSUER_LAMPORTS_FOR_MEMO = 10_000

CLAIM_ERROR_ISSUER_UNFUNDED = "issuer_unfunded"


def get_solana_client():
    """Return a ``Client`` for the configured RPC URL, or ``(None, error_message)``."""
    try:
        from solana.rpc.api import Client
    except ImportError as e:
        return None, f"solana package not available: {e}"

    url = getattr(settings, "SOLANA_RPC_URL", None) or "https://api.devnet.solana.com"
    if not url:
        return None, "SOLANA_RPC_URL is empty"
    try:
        return Client(url), None
    except Exception as e:
        logger.exception("Solana client init failed")
        return None, str(e)


def load_issuer_keypair():
    """
    Load issuer keypair from ``SOLANA_ISSUER_PRIVATE_KEY`` (env or Django settings).

    Expected format: JSON array of 64 or 32 unsigned byte values (Solana CLI export).
    Returns ``(keypair, None)`` or ``(None, error_message)``.
    """
    try:
        from solders.keypair import Keypair
    except ImportError as e:
        return None, f"solders package not available: {e}"

    raw = (
        os.environ.get("SOLANA_ISSUER_PRIVATE_KEY", "").strip()
        or (getattr(settings, "SOLANA_ISSUER_PRIVATE_KEY", None) or "").strip()
    )
    if not raw:
        return None, "SOLANA_ISSUER_PRIVATE_KEY is not set (issuer cannot sign Devnet memos)."

    try:
        arr = json.loads(raw)
    except json.JSONDecodeError:
        return None, "SOLANA_ISSUER_PRIVATE_KEY must be a JSON array of secret-key bytes."

    if not isinstance(arr, list) or not all(isinstance(x, int) for x in arr):
        return None, "SOLANA_ISSUER_PRIVATE_KEY must be a JSON array of integers."

    try:
        b = bytes(arr)
    except Exception as e:
        return None, f"Invalid key bytes: {e}"

    if len(b) == 64:
        try:
            kp = Keypair.from_bytes(b)
        except Exception as e:
            return None, f"Could not build keypair from 64-byte secret: {e}"
    elif len(b) == 32:
        try:
            kp = Keypair.from_seed(b)
        except Exception as e:
            return None, f"Could not build keypair from 32-byte seed: {e}"
    else:
        return None, "SOLANA_ISSUER_PRIVATE_KEY must be 32 (seed) or 64 (full secret key) bytes."

    return kp, None


def fetch_issuer_balance_lamports(client, issuer_pubkey) -> tuple[int | None, str | None]:
    """Return (lamports, error_message)."""
    try:
        resp = client.get_balance(issuer_pubkey)
        return int(resp.value), None
    except Exception as e:
        logger.exception("get_balance failed")
        return None, str(e)


def preflight_issuer_funds(
    min_lamports: int = MIN_ISSUER_LAMPORTS_FOR_MEMO,
) -> tuple[bool, str | None, int | None, str | None]:
    """
    Check whether the issuer can pay a simple memo transaction.

    Returns ``(ready, error_message, balance_lamports, issuer_pubkey_b58)``.
    ``error_message`` is safe to show users (no secrets).
    """
    client, cerr = get_solana_client()
    if cerr or client is None:
        return False, cerr or "Could not connect to Solana RPC.", None, None

    issuer, kerr = load_issuer_keypair()
    if kerr or issuer is None:
        return False, kerr, None, None

    pk_str = str(issuer.pubkey())
    lamports, berr = fetch_issuer_balance_lamports(client, issuer.pubkey())
    if lamports is None:
        return False, f"Could not read issuer balance: {berr}", None, pk_str

    if lamports < min_lamports:
        msg = (
            "Solana issuer wallet has no Devnet SOL. Fund "
            f"{pk_str} from the Devnet faucet (https://faucet.solana.com/)."
        )
        return False, msg, lamports, pk_str

    return True, None, lamports, pk_str


def issuer_public_health_summary() -> dict[str, Any]:
    """
    Safe diagnostics for templates / teachers (never includes private key).
    """
    network = getattr(settings, "SOLANA_NETWORK", "devnet") or "devnet"
    rpc_url = getattr(settings, "SOLANA_RPC_URL", "") or "https://api.devnet.solana.com"

    out: dict[str, Any] = {
        "network": network,
        "rpc_url": rpc_url,
        "pubkey": None,
        "balance_lamports": None,
        "balance_sol": None,
        "ready": False,
        "configured": False,
        "message": "",
    }

    issuer, kerr = load_issuer_keypair()
    if kerr or issuer is None:
        out["message"] = kerr or "Issuer key not configured."
        return out

    out["configured"] = True
    out["pubkey"] = str(issuer.pubkey())

    client, cerr = get_solana_client()
    if cerr or client is None:
        out["message"] = cerr or "RPC client unavailable."
        return out

    lamports, berr = fetch_issuer_balance_lamports(client, issuer.pubkey())
    if lamports is None:
        out["message"] = f"Balance check failed: {berr}"
        return out

    out["balance_lamports"] = lamports
    out["balance_sol"] = round(lamports / LAMPORTS_PER_SOL, 9)
    if lamports >= MIN_ISSUER_LAMPORTS_FOR_MEMO:
        out["ready"] = True
        out["message"] = "READY — issuer can pay Devnet memo transactions."
    else:
        out["message"] = (
            "NOT READY — fund the issuer wallet with Devnet SOL "
            f"(https://faucet.solana.com/). Address: {out['pubkey']}"
        )

    return out


def _build_memo_text(badge: "SkillBadge") -> str:
    course_id = badge.course_id or 0
    quiz_id = badge.quiz_id or 0
    score = int(badge.score) if badge.score is not None else 0
    return f"Car-Hoot Skill Badge | Course:{course_id} | Quiz:{quiz_id} | Passed | Score:{score}"


def _create_signed_memo_transaction(memo_bytes: bytes) -> tuple[Any | None, str | None]:
    """Build and sign a legacy transaction with one signed memo instruction."""
    from solders.instruction import AccountMeta, Instruction
    from solders.message import Message
    from solders.pubkey import Pubkey
    from solders.transaction import Transaction

    client, err = get_solana_client()
    if err or client is None:
        return None, err or "Solana client unavailable"

    issuer, err = load_issuer_keypair()
    if err or issuer is None:
        return None, err

    if len(memo_bytes) > 500:
        memo_bytes = memo_bytes[:500]

    memo_program = Pubkey.from_string(MEMO_PROGRAM_ID_STR)
    ix = Instruction(
        program_id=memo_program,
        accounts=[AccountMeta(issuer.pubkey(), is_signer=True, is_writable=True)],
        data=memo_bytes,
    )

    try:
        bh_resp = client.get_latest_blockhash()
        blockhash = bh_resp.value.blockhash
    except Exception as e:
        logger.exception("get_latest_blockhash failed")
        return None, f"RPC error (blockhash): {e}"

    try:
        msg = Message.new_with_blockhash([ix], issuer.pubkey(), blockhash)
        tx = Transaction.new_unsigned(msg)
        tx.sign([issuer], blockhash)
    except Exception as e:
        logger.exception("transaction build/sign failed")
        return None, str(e)

    return tx, None


def create_skill_badge_transaction(badge: "SkillBadge") -> tuple[Any | None, str | None]:
    """
    Build and sign a Devnet transaction containing a signed memo instruction.

    Returns ``(transaction, None)`` or ``(None, error_message)``.
    """
    ready, msg, _lamports, _pk = preflight_issuer_funds()
    if not ready:
        return None, msg

    memo_text = _build_memo_text(badge)
    try:
        memo_bytes = memo_text.encode("utf-8")
    except Exception as e:
        return None, str(e)

    return _create_signed_memo_transaction(memo_bytes)


def send_skill_badge_transaction(badge: "SkillBadge") -> tuple[str | None, str | None]:
    """
    Submit the memo transaction to Devnet.

    Returns ``(signature_str, None)`` or ``(None, error_message)``.
    """
    tx, err = create_skill_badge_transaction(badge)
    if err or tx is None:
        return None, err

    client, cerr = get_solana_client()
    if cerr or client is None:
        return None, cerr

    try:
        resp = client.send_transaction(tx)
        sig = str(resp.value) if resp.value is not None else None
        if not sig:
            return None, "Empty signature from RPC"
        return sig, None
    except Exception as e:
        logger.exception("send_transaction failed")
        return None, str(e)


def send_test_memo_transaction(memo_utf8: str) -> tuple[str | None, str | None]:
    """
    Send a standalone memo transaction (e.g. management command smoke test).

    Returns ``(signature, None)`` or ``(None, error_message)``.
    """
    ready, msg, _lam, _pk = preflight_issuer_funds()
    if not ready:
        return None, msg

    try:
        memo_bytes = memo_utf8.encode("utf-8")
    except Exception as e:
        return None, str(e)

    tx, err = _create_signed_memo_transaction(memo_bytes)
    if err or tx is None:
        return None, err

    client, cerr = get_solana_client()
    if cerr or client is None:
        return None, cerr

    try:
        resp = client.send_transaction(tx)
        sig = str(resp.value) if resp.value is not None else None
        if not sig:
            return None, "Empty signature from RPC"
        return sig, None
    except Exception as e:
        logger.exception("send_test_memo_transaction failed")
        return None, str(e)
