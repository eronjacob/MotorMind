from django.contrib import admin
from django.utils.html import format_html

from .models import SkillBadge, SolanaWalletProfile


@admin.register(SolanaWalletProfile)
class SolanaWalletProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "wallet_address", "updated_at")
    search_fields = ("user__username", "wallet_address")


@admin.register(SkillBadge)
class SkillBadgeAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "student",
        "badge_type",
        "status",
        "score",
        "solana_network",
        "claimed_at",
    )
    list_filter = ("status", "badge_type", "solana_network")
    search_fields = ("title", "student__username", "transaction_signature")
    readonly_fields = ("created_at", "updated_at", "explorer_link")

    @admin.display(description="Explorer")
    def explorer_link(self, obj):
        if obj.explorer_url:
            return format_html(
                '<a href="{}" target="_blank" rel="noopener">{}</a>',
                obj.explorer_url,
                obj.transaction_signature[:20] + "…",
            )
        return "—"
