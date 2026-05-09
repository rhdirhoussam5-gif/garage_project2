import os

from django.utils import timezone
from groq import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    Groq,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
)

from .models import Demande, Intervention, RendezVous, Scan, Vehicule


class ChatbotConfigurationError(Exception):
    pass


class ChatbotServiceError(Exception):
    pass


def get_accessible_vehicles(user):
    if hasattr(user, "proprietaire"):
        return Vehicule.objects.filter(proprietaire=user.proprietaire)
    if hasattr(user, "mecanicien"):
        return Vehicule.objects.all()
    return Vehicule.objects.none()


def get_vehicle_for_chat(user, vehicle_id=None):
    vehicles = get_accessible_vehicles(user)

    if vehicle_id:
        return vehicles.get(pk=vehicle_id)

    if hasattr(user, "proprietaire"):
        if vehicles.count() == 1:
            return vehicles.first()
        return None

    if hasattr(user, "mecanicien"):
        return None

    return None


def _format_value(value):
    if value is None:
        return "N/A"
    if hasattr(value, "strftime"):
        return timezone.localtime(value).strftime("%Y-%m-%d %H:%M")
    return str(value)


def _compact_text(value, max_length=240):
    text = (value or "").strip()
    if len(text) <= max_length:
        return text or "N/A"
    return f"{text[:max_length].rstrip()}..."


def build_vehicle_context(vehicle):
    if vehicle is None:
        return (
            "No specific vehicle selected. The assistant should ask the user to choose "
            "a vehicle if the question needs vehicle-specific advice."
        )

    owner_name = "N/A"
    if vehicle.proprietaire and vehicle.proprietaire.user:
        owner_name = vehicle.proprietaire.user.get_full_name() or vehicle.proprietaire.user.username

    lines = [
        "Vehicle:",
        f"- matricule: {vehicle.matricule}",
        f"- marque: {vehicle.marque}",
        f"- modele: {vehicle.modele}",
        f"- annee: {vehicle.annee}",
        f"- kilometrage_actuel: {vehicle.kilometrage_actuel}",
        f"- garage: {vehicle.garage.nom if vehicle.garage else 'N/A'}",
        f"- owner: {owner_name}",
    ]

    demandes = (
        Demande.objects.filter(vehicule=vehicle)
        .order_by("-date_creation")
        .only("id", "date_creation", "statut", "priorite", "description_note")[:5]
    )
    lines.append("\nRecent service requests:")
    if demandes:
        for demande in demandes:
            lines.append(
                f"- #{demande.id} | {demande.date_creation:%Y-%m-%d %H:%M} | "
                f"status={demande.statut} | priority={demande.priorite} | "
                f"note={_compact_text(demande.description_note)}"
            )
    else:
        lines.append("- None")

    scans = (
        Scan.objects.filter(demande__vehicule=vehicle)
        .select_related("demande")
        .order_by("-date_scan")[:5]
    )
    lines.append("\nRecent scans:")
    if scans:
        for scan in scans:
            lines.append(
                f"- {scan.date_scan:%Y-%m-%d %H:%M} | codes={_compact_text(scan.codes_defaut)} | "
                f"observations={_compact_text(scan.observations)}"
            )
    else:
        lines.append("- None")

    interventions = (
        Intervention.objects.filter(demande__vehicule=vehicle)
        .select_related("demande")
        .order_by("-date_debut")[:5]
    )
    lines.append("\nRecent interventions:")
    if interventions:
        for intervention in interventions:
            lines.append(
                f"- {intervention.date_debut:%Y-%m-%d %H:%M} | type={intervention.type_intervention} | "
                f"state={intervention.etat} | mileage={intervention.kilometrage} | "
                f"diagnostic={_compact_text(intervention.diagnostic)} | "
                f"work={_compact_text(intervention.description_travaux)} | "
                f"future_problems={_compact_text(intervention.problemes_futurs)}"
            )
    else:
        lines.append("- None")

    appointments = (
        RendezVous.objects.filter(
            vehicule=vehicle,
            statut__in=["scheduled", "confirmed"],
            date_rdv__gte=timezone.now(),
        )
        .order_by("date_rdv")[:3]
    )
    lines.append("\nUpcoming appointments:")
    if appointments:
        for appointment in appointments:
            lines.append(
                f"- {appointment.date_rdv:%Y-%m-%d %H:%M} | motif={appointment.motif} | "
                f"status={appointment.statut} | description={_compact_text(appointment.description)}"
            )
    else:
        lines.append("- None")

    return "\n".join(lines)


def call_groq_chatbot(user_message, context_text):
    api_key = (os.getenv("GROQ_API_KEY") or "").strip()
    if not api_key or api_key == "your_groq_api_key_here":
        raise ChatbotConfigurationError("GROQ_API_KEY is not configured.")

    client = Groq(api_key=api_key, timeout=20.0)
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    system_prompt = (
        "You are a helpful assistant inside a garage management web application.\n"
        "You help vehicle owners and mechanics understand vehicle problems, maintenance history, "
        "service requests, appointments, interventions, invoices, and parts.\n"
        "Use the provided database context when available.\n"
        "Do not invent exact mechanical diagnoses.\n"
        "Give possible causes, urgency level, safe checks, and recommend booking a service request "
        "or appointment when needed.\n"
        "If the question is dangerous or needs a real mechanic inspection, say clearly that a "
        "mechanic must inspect the vehicle.\n"
        "Keep answers practical, short, and easy to understand."
    )

    try:
        response = client.chat.completions.create(
            model=model,
            temperature=0.3,
            max_tokens=500,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Database context:\n{context_text}\n\nUser question:\n{user_message}"},
            ],
        )
    except AuthenticationError as exc:
        raise ChatbotServiceError("Groq rejected the API key. Check GROQ_API_KEY in .env.") from exc
    except PermissionDeniedError as exc:
        raise ChatbotServiceError("Groq permission denied for this API key.") from exc
    except NotFoundError as exc:
        raise ChatbotServiceError("Groq model not found. Check GROQ_MODEL in .env.") from exc
    except BadRequestError as exc:
        raise ChatbotServiceError("Groq rejected the request. Check the configured model.") from exc
    except RateLimitError as exc:
        raise ChatbotServiceError("Groq rate limit reached. Try again later.") from exc
    except (APIConnectionError, APITimeoutError) as exc:
        raise ChatbotServiceError("Cannot reach Groq. Check your internet connection.") from exc

    return response.choices[0].message.content.strip()
