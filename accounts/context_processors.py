def user_profile(request):
    """Expose profile on all templates when present."""
    profile = None
    if request.user.is_authenticated:
        profile = getattr(request.user, "profile", None)
    return {"user_profile": profile}
