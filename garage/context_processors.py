def role_flags(request):
    user = getattr(request, "user", None)
    is_authenticated = bool(user and user.is_authenticated)

    return {
        "is_mechanic": is_authenticated and hasattr(user, "mecanicien"),
        "is_owner": is_authenticated and hasattr(user, "proprietaire"),
    }
