from django.urls import path

from . import views

app_name = "solana_badges"

urlpatterns = [
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path("profile/wallet/", views.WalletUpdateView.as_view(), name="profile_wallet"),
    path(
        "badges/claim/quiz-attempt/<int:attempt_id>/",
        views.ClaimQuizBadgeView.as_view(),
        name="claim_quiz_badge",
    ),
    path("leaderboard/", views.GlobalLeaderboardView.as_view(), name="global_leaderboard"),
]
