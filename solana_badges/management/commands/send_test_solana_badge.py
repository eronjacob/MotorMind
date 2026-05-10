from django.core.management.base import BaseCommand, CommandError

from solana_badges.services.solana_client import (
    LAMPORTS_PER_SOL,
    MIN_ISSUER_LAMPORTS_FOR_MEMO,
    load_issuer_keypair,
    send_test_memo_transaction,
)
from solana_badges.validators import is_valid_solana_address


class Command(BaseCommand):
    help = (
        "Send a test Memo program transaction on Solana Devnet using the issuer keypair. "
        "Memo text: Car-Hoot test badge transaction"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--wallet",
            type=str,
            default="",
            help="Optional Devnet address (validated; informational only for this test memo).",
        )

    def handle(self, *args, **options):
        wallet = (options.get("wallet") or "").strip()
        if wallet and not is_valid_solana_address(wallet):
            raise CommandError("Invalid --wallet Solana address.")

        issuer, kerr = load_issuer_keypair()
        if kerr or issuer is None:
            raise CommandError(kerr or "Issuer key not configured.")

        pk = str(issuer.pubkey())
        self.stdout.write(f"Issuer public key: {pk}")
        if wallet:
            self.stdout.write(f"Note (--wallet): {wallet}")

        sig, err = send_test_memo_transaction("Car-Hoot test badge transaction")
        if sig:
            url = f"https://explorer.solana.com/tx/{sig}?cluster=devnet"
            self.stdout.write(self.style.SUCCESS(f"Signature: {sig}"))
            self.stdout.write(f"Explorer: {url}")
            return

        self.stdout.write(self.style.ERROR(f"Send failed: {err}"))
        if err and ("Devnet SOL" in err or "lamports" in err.lower()):
            self.stdout.write("")
            self.stdout.write("Fund the issuer from:")
            self.stdout.write("https://faucet.solana.com/")
            self.stdout.write("")
            self.stdout.write("Network: Devnet")
            self.stdout.write(f"Address: {pk}")
            self.stdout.write(
                f"(Need at least ~{MIN_ISSUER_LAMPORTS_FOR_MEMO} lamports "
                f"≈ {MIN_ISSUER_LAMPORTS_FOR_MEMO / LAMPORTS_PER_SOL:.9f} SOL for fees.)"
            )
