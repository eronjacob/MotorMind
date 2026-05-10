from __future__ import annotations

import copy

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Avg
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from quizzes.models import QuizAttempt

from .models import SkillBadge, SolanaWalletProfile
from .services.solana_client import (
    CLAIM_ERROR_ISSUER_UNFUNDED,
    issuer_public_health_summary,
    load_issuer_keypair,
    preflight_issuer_funds,
    send_skill_badge_transaction,
)
from .validators import is_valid_solana_address


class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = "solana_badges/profile.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        profile, _ = SolanaWalletProfile.objects.get_or_create(user=user)

        attempts = QuizAttempt.objects.filter(student=user).select_related("quiz", "quiz__course")
        passed_attempts = attempts.filter(passed=True)
        passed_quizzes = passed_attempts.values("quiz").distinct().count()
        avg_row = passed_attempts.aggregate(avg=Avg("score"))
        avg_score = avg_row["avg"]
        if avg_score is not None:
            avg_score = round(float(avg_score), 1)

        badges = SkillBadge.objects.filter(student=user).select_related(
            "course", "quiz", "quiz_attempt"
        )
        claimable = badges.filter(status=SkillBadge.Status.CLAIMABLE).order_by("-created_at")
        claimed = badges.filter(status=SkillBadge.Status.CLAIMED).order_by("-claimed_at", "-created_at")
        failed = badges.filter(status=SkillBadge.Status.FAILED).order_by("-updated_at")[:5]

        from accounts.models import Profile

        role = ""
        try:
            p = user.profile
            role = p.get_role_display()
        except Profile.DoesNotExist:
            role = "—"

        show_solana_ops = user.is_staff
        if not show_solana_ops:
            try:
                show_solana_ops = user.profile.role == Profile.Role.TEACHER
            except Profile.DoesNotExist:
                pass
        solana_issuer_diag = None
        if show_solana_ops:
            solana_issuer_diag = issuer_public_health_summary()

        ctx.update(
            {
                "wallet_profile": profile,
                "user_role_display": role,
                "passed_quiz_count": passed_quizzes,
                "avg_passed_score": avg_score,
                "latest_attempts": attempts.order_by("-created_at")[:12],
                "badges_claimable": claimable,
                "badges_claimed": claimed,
                "badges_failed_recent": failed,
                "badges_all": badges,
                "show_solana_ops": show_solana_ops,
                "solana_issuer_diag": solana_issuer_diag,
            }
        )
        return ctx


class WalletUpdateView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        addr = (request.POST.get("wallet_address") or "").strip()
        if addr and not is_valid_solana_address(addr):
            messages.error(request, "That does not look like a valid Solana address.")
            return HttpResponseRedirect(reverse("solana_badges:profile"))

        profile, _ = SolanaWalletProfile.objects.get_or_create(user=request.user)
        profile.wallet_address = addr
        profile.save(update_fields=["wallet_address", "updated_at"])
        messages.success(request, "Wallet address saved.")
        return HttpResponseRedirect(reverse("solana_badges:profile"))


class ClaimQuizBadgeView(LoginRequiredMixin, View):
    def post(self, request, attempt_id, *args, **kwargs):
        attempt = get_object_or_404(
            QuizAttempt.objects.select_related("quiz", "quiz__course"),
            pk=attempt_id,
            student=request.user,
        )
        if not attempt.passed:
            messages.error(request, "Only passed quiz runs can mint a badge proof.")
            return HttpResponseRedirect(
                reverse("quizzes:quiz_result", kwargs={"quiz_id": attempt.quiz_id})
            )

        badge = SkillBadge.objects.filter(
            quiz_attempt=attempt,
            student=request.user,
            badge_type=SkillBadge.BadgeType.QUIZ_PASS,
        ).first()
        if not badge:
            messages.error(request, "No claimable badge for this attempt.")
            return HttpResponseRedirect(
                reverse("quizzes:quiz_result", kwargs={"quiz_id": attempt.quiz_id})
            )

        if badge.status == SkillBadge.Status.CLAIMED and badge.transaction_signature:
            messages.info(request, "This badge is already claimed.")
            return HttpResponseRedirect(
                reverse("quizzes:quiz_result", kwargs={"quiz_id": attempt.quiz_id})
            )

        posted_wallet = (request.POST.get("wallet_address") or "").strip()
        profile, _ = SolanaWalletProfile.objects.get_or_create(user=request.user)
        wallet = posted_wallet or (profile.wallet_address or "").strip()
        if not wallet:
            messages.error(request, "Enter a Solana Devnet wallet address or save one on your profile.")
            return HttpResponseRedirect(
                reverse("quizzes:quiz_result", kwargs={"quiz_id": attempt.quiz_id})
            )
        if not is_valid_solana_address(wallet):
            messages.error(request, "Invalid Solana wallet address.")
            return HttpResponseRedirect(
                reverse("quizzes:quiz_result", kwargs={"quiz_id": attempt.quiz_id})
            )

        profile.wallet_address = wallet
        profile.save(update_fields=["wallet_address", "updated_at"])

        if badge.status == SkillBadge.Status.FAILED:
            md_clear = copy.deepcopy(badge.metadata or {})
            for k in ("claim_error_code", "issuer_public_key", "faucet_url", "network", "detail"):
                md_clear.pop(k, None)
            badge.metadata = md_clear
            badge.error_message = ""
            badge.transaction_signature = ""
            badge.status = SkillBadge.Status.CLAIMABLE

        badge.wallet_address = wallet
        badge.save(
            update_fields=[
                "wallet_address",
                "status",
                "error_message",
                "transaction_signature",
                "metadata",
                "updated_at",
            ]
        )

        ready, fund_msg, _lamports, pk_str = preflight_issuer_funds()
        if not ready:
            md = copy.deepcopy(badge.metadata or {})
            md["claim_error_code"] = CLAIM_ERROR_ISSUER_UNFUNDED
            if pk_str:
                md["issuer_public_key"] = pk_str
            md["faucet_url"] = "https://faucet.solana.com/"
            md["network"] = "devnet"
            if fund_msg:
                md["detail"] = fund_msg
            badge.metadata = md
            badge.status = SkillBadge.Status.FAILED
            badge.error_message = (
                "Badge not claimed yet: the project issuer wallet needs Devnet SOL."
            )
            badge.save(
                update_fields=["metadata", "status", "error_message", "updated_at"]
            )
            messages.warning(request, badge.error_message)
            return HttpResponseRedirect(
                reverse("quizzes:quiz_result", kwargs={"quiz_id": attempt.quiz_id})
            )

        sig, err = send_skill_badge_transaction(badge)
        if sig:
            badge.transaction_signature = sig
            badge.status = SkillBadge.Status.CLAIMED
            badge.claimed_at = timezone.now()
            badge.error_message = ""
            badge.save(
                update_fields=[
                    "transaction_signature",
                    "status",
                    "claimed_at",
                    "error_message",
                    "updated_at",
                ]
            )
            md_ok = copy.deepcopy(badge.metadata or {})
            for k in ("claim_error_code", "issuer_public_key", "faucet_url", "network", "detail"):
                md_ok.pop(k, None)
            badge.metadata = md_ok
            badge.save(update_fields=["metadata", "updated_at"])
            messages.success(
                request,
                "Badge recorded on Solana Devnet. Signature saved.",
            )
        else:
            err_l = (err or "").lower()
            md = copy.deepcopy(badge.metadata or {})
            if err and (
                "no devnet sol" in err_l
                or "insufficient" in err_l
                or "prior credit" in err_l
                or "accountnotfound" in err_l.replace(" ", "")
            ):
                md["claim_error_code"] = CLAIM_ERROR_ISSUER_UNFUNDED
                issuer, _ = load_issuer_keypair()
                if issuer:
                    md["issuer_public_key"] = str(issuer.pubkey())
                md["faucet_url"] = "https://faucet.solana.com/"
                md["network"] = "devnet"
                md["detail"] = (err or "")[:2000]
                badge.error_message = (
                    "Badge not claimed yet: the project issuer wallet needs Devnet SOL."
                )
            else:
                md.pop("claim_error_code", None)
                badge.error_message = (err or "Unknown error")[:4000]
            badge.metadata = md
            badge.status = SkillBadge.Status.FAILED
            badge.save(update_fields=["status", "error_message", "metadata", "updated_at"])
            messages.error(
                request,
                badge.error_message[:500]
                if md.get("claim_error_code") == CLAIM_ERROR_ISSUER_UNFUNDED
                else f"Devnet transaction failed: {badge.error_message[:500]}",
            )

        return HttpResponseRedirect(
            reverse("quizzes:quiz_result", kwargs={"quiz_id": attempt.quiz_id})
        )


class GlobalLeaderboardView(LoginRequiredMixin, TemplateView):
    """Off-chain aggregate: passed quizzes, average score, claimed badges."""

    template_name = "solana_badges/global_leaderboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from django.contrib.auth import get_user_model

        User = get_user_model()

        rows = []
        for u in User.objects.filter(is_active=True).order_by("id"):
            passed_qs = QuizAttempt.objects.filter(student=u, passed=True)
            distinct_passed = passed_qs.values("quiz").distinct().count()
            avg_sc = passed_qs.aggregate(a=Avg("score"))["a"]
            if avg_sc is not None:
                avg_sc = round(float(avg_sc), 1)
            badge_n = SkillBadge.objects.filter(
                student=u, status=SkillBadge.Status.CLAIMED
            ).count()
            if distinct_passed == 0 and badge_n == 0:
                continue
            rows.append(
                {
                    "user": u,
                    "passed_quizzes": distinct_passed,
                    "avg_score": avg_sc,
                    "badges_claimed": badge_n,
                }
            )

        rows.sort(
            key=lambda r: (
                -r["badges_claimed"],
                -r["passed_quizzes"],
                -(r["avg_score"] or 0),
            )
        )
        for i, r in enumerate(rows, start=1):
            r["rank"] = i

        ctx["leaderboard_rows"] = rows
        return ctx
