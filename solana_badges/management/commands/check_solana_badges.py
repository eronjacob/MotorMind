from django.conf import settings
from django.core.management.base import BaseCommand

from solana_badges.services.solana_client import (
    LAMPORTS_PER_SOL,
    MIN_ISSUER_LAMPORTS_FOR_MEMO,
    issuer_public_health_summary,
    load_issuer_keypair,
)


class Command(BaseCommand):
    help = "Check Solana Devnet configuration and issuer wallet balance (never prints private keys)."

    def handle(self, *args, **options):
        network = getattr(settings, "SOLANA_NETWORK", "devnet") or "devnet"
        rpc_url = getattr(settings, "SOLANA_RPC_URL", "") or "https://api.devnet.solana.com"

        self.stdout.write(f"Solana network: {network}")
        self.stdout.write(f"RPC URL: {rpc_url}")

        issuer, kerr = load_issuer_keypair()
        if kerr or issuer is None:
            self.stdout.write(self.style.ERROR(f"Issuer key: NOT CONFIGURED — {kerr}"))
            self.stdout.write(
                self.style.WARNING("Status: NOT READY — set SOLANA_ISSUER_PRIVATE_KEY in .env")
            )
            return

        pk = str(issuer.pubkey())
        self.stdout.write(f"Issuer public key: {pk}")

        diag = issuer_public_health_summary()
        lamports = diag.get("balance_lamports")
        if lamports is None:
            self.stdout.write(self.style.ERROR(f"Balance: unknown ({diag.get('message', '')})"))
            self.stdout.write(self.style.WARNING("Status: NOT READY"))
            return

        sol = lamports / LAMPORTS_PER_SOL
        self.stdout.write(f"Balance: {sol:.9f} SOL ({lamports} lamports)")

        if lamports >= MIN_ISSUER_LAMPORTS_FOR_MEMO:
            self.stdout.write(self.style.SUCCESS("Status: READY"))
        else:
            self.stdout.write(
                self.style.WARNING(
                    "Status: NOT READY — fund this wallet with Devnet SOL."
                )
            )
            self.stdout.write("")
            self.stdout.write("Use Devnet faucet:")
            self.stdout.write("https://faucet.solana.com/")
            self.stdout.write("")
            self.stdout.write("Network: Devnet")
            self.stdout.write(f"Address: {pk}")
