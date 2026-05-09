from .models import Vehicule


def role_flags(request):
    user = getattr(request, "user", None)
    is_authenticated = bool(user and user.is_authenticated)
    is_mechanic = is_authenticated and hasattr(user, "mecanicien")
    is_owner = is_authenticated and hasattr(user, "proprietaire")

    vehicles = Vehicule.objects.none()
    if is_owner:
        vehicles = Vehicule.objects.filter(proprietaire=user.proprietaire)
    elif is_mechanic:
        vehicles = Vehicule.objects.all()

    vehicle_options = [
        {
            "id": vehicle.id,
            "label": f"{vehicle.marque} {vehicle.modele} ({vehicle.annee}) - {vehicle.matricule}",
        }
        for vehicle in vehicles.order_by("marque", "modele", "matricule")
    ]

    return {
        "is_mechanic": is_mechanic,
        "is_owner": is_owner,
        "chatbot_vehicle_options": vehicle_options,
    }
