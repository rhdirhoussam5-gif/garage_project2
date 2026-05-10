import io
import json
import logging

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .chatbot_utils import (
    ChatbotConfigurationError,
    ChatbotServiceError,
    build_vehicle_context,
    call_groq_chatbot,
    get_accessible_vehicles,
    get_vehicle_for_chat,
)
from .forms import (
    DemandeForm,
    FacturationForm,
    FileUploadForm,
    InterventionForm,
    LoginForm,
    MecanicienRegisterForm,
    ProprietaireRegisterForm,
    RendezVousForm,
    VehiculeForm,
    PieceForm,
)
from .models import Demande, Facturation, Intervention, InterventionPiece, Mecanicien, Piece, Proprietaire, RendezVous, Vehicule


def is_mechanic(user):
    return user.is_authenticated and hasattr(user, "mecanicien")


def is_owner(user):
    return user.is_authenticated and hasattr(user, "proprietaire")


def user_home_url(user):
    if is_mechanic(user):
        return "dashboard"
    if is_owner(user):
        return "client_dashboard"
    return "login"


@login_required
@require_POST
def chatbot_reply(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    user_message = (payload.get("message") or "").strip()
    vehicle_id = payload.get("vehicle_id") or None

    if not user_message:
        return JsonResponse({"error": "Message is required."}, status=400)

    try:
        vehicle = get_vehicle_for_chat(request.user, vehicle_id)
    except (Vehicule.DoesNotExist, ValueError, TypeError):
        return JsonResponse({"error": "Vehicle not found or not allowed."}, status=403)

    accessible_vehicles = get_accessible_vehicles(request.user)

    if vehicle is None and hasattr(request.user, "proprietaire") and accessible_vehicles.count() > 1:
        return JsonResponse(
            {
                "error": "Please choose a vehicle first.",
                "needs_vehicle": True,
            },
            status=400,
        )

    if hasattr(request.user, "mecanicien"):
        role_context = "Connected user role: mechanic."
        if vehicle is None:
            role_context += " Mechanic mode with no selected vehicle."
    elif hasattr(request.user, "proprietaire"):
        role_context = "Connected user role: owner."
    else:
        role_context = "Connected user role: unknown."

    context_text = f"{role_context}\n\n{build_vehicle_context(vehicle)}"

    try:
        reply = call_groq_chatbot(user_message, context_text)
    except ChatbotConfigurationError as exc:
        return JsonResponse({"error": str(exc)}, status=503)
    except ChatbotServiceError as exc:
        return JsonResponse({"error": str(exc)}, status=502)
    except Exception:
        logging.exception("Chatbot error")
        return JsonResponse(
            {
                "error": "Chatbot service unavailable. Check GROQ_API_KEY and internet connection."
            },
            status=500,
        )

    return JsonResponse({"reply": reply})


@login_required
def chatbot_vehicles(request):
    vehicles = get_accessible_vehicles(request.user).order_by("marque", "modele", "matricule")
    data = [
        {
            "id": vehicle.id,
            "label": f"{vehicle.marque} {vehicle.modele} ({vehicle.annee}) - {vehicle.matricule}",
        }
        for vehicle in vehicles
    ]
    return JsonResponse({"vehicles": data})


def login_view(request):
    if request.user.is_authenticated:
        destination = user_home_url(request.user)
        if destination == "login":
            logout(request)
            messages.error(request, "Your account is missing a profile. Contact an administrator.")
            return redirect("login")
        return redirect(destination)

    form = LoginForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        login(request, user)
        destination = user_home_url(user)
        if destination == "login":
            logout(request)
            messages.error(request, "Your account is missing a profile. Contact an administrator.")
            return redirect("login")
        return redirect(destination)
    return render(request, "garage/login.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("login")


def register_choice(request):
    if request.user.is_authenticated:
        return redirect(user_home_url(request.user))
    return render(request, "garage/register_choice.html")


def register_mechanic(request):
    if request.user.is_authenticated:
        return redirect(user_home_url(request.user))

    form = MecanicienRegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save(commit=False)
        user.first_name = form.cleaned_data["first_name"]
        user.last_name = form.cleaned_data["last_name"]
        user.email = form.cleaned_data["email"]
        user.save()

        Mecanicien.objects.create(
            user=user,
            telephone=form.cleaned_data.get("telephone", ""),
            specialite=form.cleaned_data.get("specialite", ""),
        )
        messages.success(request, "Mechanic account created. You can now log in.")
        return redirect("login")
    return render(request, "garage/register_mechanic.html", {"form": form})


def register_owner(request):
    if request.user.is_authenticated:
        return redirect(user_home_url(request.user))

    form = ProprietaireRegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save(commit=False)
        user.first_name = form.cleaned_data["first_name"]
        user.last_name = form.cleaned_data["last_name"]
        user.email = form.cleaned_data["email"]
        user.save()

        Proprietaire.objects.create(
            user=user,
            telephone=form.cleaned_data.get("telephone", ""),
        )
        messages.success(request, "Owner account created. You can now log in.")
        return redirect("login")
    return render(request, "garage/register_owner.html", {"form": form})


@login_required
def dashboard(request):
    if not is_mechanic(request.user):
        messages.error(request, "Access denied. This area is for mechanics only.")
        return redirect(user_home_url(request.user))

    total_vehicles = Vehicule.objects.count()
    total_interventions = Intervention.objects.count()
    pending_requests = Demande.objects.filter(statut="pending").select_related("vehicule").order_by("-date_creation")
    upcoming_rdv = RendezVous.objects.filter(
        statut__in=["scheduled", "confirmed"],
        date_rdv__gte=timezone.now(),
    ).order_by("date_rdv")[:5]
    recent_interventions = Intervention.objects.select_related("demande__vehicule").order_by("-date_debut")[:5]

    return render(
        request,
        "garage/mechanic_dashboard.html",
        {
            "total_vehicles": total_vehicles,
            "total_interventions": total_interventions,
            "pending_demandes": pending_requests.count(),
            "pending_requests": pending_requests,
            "upcoming_rdv": upcoming_rdv,
            "recent_interventions": recent_interventions,
        },
    )


@login_required
def client_dashboard(request):
    if not is_owner(request.user):
        messages.error(request, "Access denied. This area is for vehicle owners only.")
        return redirect(user_home_url(request.user))

    proprietaire = request.user.proprietaire
    my_vehicles = Vehicule.objects.filter(proprietaire=proprietaire).order_by("-date_enregistrement")
    upcoming_rdv = (
        RendezVous.objects.filter(
            vehicule__proprietaire=proprietaire,
            statut__in=["scheduled", "confirmed"],
            date_rdv__gte=timezone.now(),
        )
        .select_related("vehicule", "garage")
        .order_by("date_rdv")[:5]
    )
    recent_interventions = (
        Intervention.objects.filter(demande__vehicule__proprietaire=proprietaire)
        .select_related("demande__vehicule", "mecanicien__user")
        .order_by("-date_debut")[:5]
    )

    return render(
        request,
        "garage/client_dashboard.html",
        {
            "my_vehicles": my_vehicles,
            "upcoming_rdv": upcoming_rdv,
            "recent_interventions": recent_interventions,
            "demande_form": DemandeForm(),
        },
    )


@login_required
def vehicle_list(request):
    if is_mechanic(request.user):
        vehicles = Vehicule.objects.select_related("proprietaire__user").order_by("-date_enregistrement")
    elif is_owner(request.user):
        vehicles = (
            Vehicule.objects.filter(proprietaire=request.user.proprietaire)
            .select_related("proprietaire__user")
            .order_by("-date_enregistrement")
        )
    else:
        return HttpResponseForbidden("Access denied.")

    return render(request, "garage/vehicle_list.html", {"vehicles": vehicles})


@login_required
def vehicle_add(request):
    form = VehiculeForm(request.POST or None)

    if is_owner(request.user):
        form.fields.pop("proprietaire", None)
        if request.method == "POST" and form.is_valid():
            vehicle = form.save(commit=False)
            vehicle.proprietaire = request.user.proprietaire
            vehicle.save()
            messages.success(request, "Vehicle registered successfully.")
            return redirect("vehicle_list")
    elif is_mechanic(request.user):
        if request.method == "POST" and form.is_valid():
            form.save()
            messages.success(request, "Vehicle registered successfully.")
            return redirect("vehicle_list")
    else:
        return HttpResponseForbidden("Access denied.")

    return render(request, "garage/vehicle_form.html", {"form": form, "title": "Register Vehicle"})


@login_required
def vehicle_edit(request, pk):
    vehicle = get_object_or_404(Vehicule, pk=pk)

    if is_owner(request.user):
        if vehicle.proprietaire != request.user.proprietaire:
            return HttpResponseForbidden("You can only edit your own vehicles.")
    elif not is_mechanic(request.user):
        return HttpResponseForbidden("Access denied.")

    form = VehiculeForm(request.POST or None, instance=vehicle)
    if is_owner(request.user):
        form.fields.pop("proprietaire", None)

    if request.method == "POST" and form.is_valid():
        updated_vehicle = form.save(commit=False)
        if is_owner(request.user):
            updated_vehicle.proprietaire = request.user.proprietaire
        updated_vehicle.save()
        messages.success(request, "Vehicle updated.")
        return redirect("vehicle_detail", pk=pk)
    return render(request, "garage/vehicle_form.html", {"form": form, "title": "Edit Vehicle"})


@login_required
def vehicle_detail(request, pk):
    vehicle = get_object_or_404(Vehicule, pk=pk)

    if is_owner(request.user):
        if vehicle.proprietaire != request.user.proprietaire:
            return HttpResponseForbidden("You can only view your own vehicles.")
    elif not is_mechanic(request.user):
        return HttpResponseForbidden("Access denied.")

    interventions = (
        Intervention.objects.filter(demande__vehicule=vehicle)
        .select_related("mecanicien__user")
        .order_by("-date_debut")
    )
    rdvs = RendezVous.objects.filter(vehicule=vehicle).order_by("-date_rdv")[:5]
    return render(
        request,
        "garage/vehicle_detail.html",
        {
            "vehicle": vehicle,
            "interventions": interventions,
            "rdvs": rdvs,
        },
    )


@login_required
def demande_add(request, vehicle_pk):
    vehicle = get_object_or_404(Vehicule, pk=vehicle_pk)

    if is_owner(request.user):
        if vehicle.proprietaire != request.user.proprietaire:
            return HttpResponseForbidden("You can only create requests for your own vehicles.")
    elif not is_mechanic(request.user):
        return HttpResponseForbidden("Access denied.")

    form = DemandeForm(request.POST or None)
    if is_owner(request.user):
        form.fields.pop("statut", None)

    if request.method == "POST" and form.is_valid():
        demande = form.save(commit=False)
        demande.vehicule = vehicle
        if is_owner(request.user):
            demande.statut = "pending"
        if demande.garage is None and vehicle.garage_id:
            demande.garage = vehicle.garage
        demande.save()
        messages.success(request, "Service request created.")

        if is_mechanic(request.user):
            return redirect("intervention_add", demande_pk=demande.pk)
        return redirect("vehicle_detail", pk=vehicle.pk)
    return render(request, "garage/demande_form.html", {"form": form, "vehicle": vehicle})


@login_required
def intervention_add(request, demande_pk):
    if not is_mechanic(request.user):
        return HttpResponseForbidden("Only mechanics can add interventions.")

    demande = get_object_or_404(Demande, pk=demande_pk)
    form = InterventionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        intervention = form.save(commit=False)
        intervention.demande = demande
        intervention.save()
        messages.success(request, "Intervention logged.")
        return redirect("vehicle_detail", pk=demande.vehicule.pk)
    return render(request, "garage/intervention_form.html", {"form": form, "demande": demande})


@login_required
def intervention_detail(request, pk):
    intervention = get_object_or_404(
        Intervention.objects.prefetch_related("fichiers", "intervention_pieces__piece"),
        pk=pk,
    )

    vehicle = intervention.demande.vehicule
    if is_owner(request.user):
        if vehicle.proprietaire != request.user.proprietaire:
            return HttpResponseForbidden("You can only view interventions for your own vehicles.")
    elif not is_mechanic(request.user):
        return HttpResponseForbidden("Access denied.")

    try:
        facture = intervention.facture
    except Facturation.DoesNotExist:
        facture = None

    return render(
        request,
        "garage/intervention_detail.html",
        {
            "intervention": intervention,
            "upload_form": FileUploadForm(),
            "facture": facture,
            "all_pieces": Piece.objects.filter(quantite_stock__gt=0) if is_mechanic(request.user) else [],
        },
    )


@login_required
def upload_file(request, intervention_pk):
    if not is_mechanic(request.user):
        return HttpResponseForbidden("Only mechanics can upload files.")

    intervention = get_object_or_404(Intervention, pk=intervention_pk)
    if request.method == "POST":
        form = FileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            upload = form.save(commit=False)
            upload.intervention = intervention
            upload.save()
            messages.success(request, "File uploaded.")
        else:
            messages.error(request, "Only image files are allowed.")
    return redirect("intervention_detail", pk=intervention_pk)


@login_required
def intervention_add_piece(request, pk):
    if not is_mechanic(request.user):
        return HttpResponseForbidden("Only mechanics can add pieces to interventions.")
    
    intervention = get_object_or_404(Intervention, pk=pk)
    
    if request.method == "POST":
        piece_id = request.POST.get("piece_id")
        quantity = int(request.POST.get("quantity", 1))
        
        piece = get_object_or_404(Piece, pk=piece_id)
        
        if piece.quantite_stock < quantity:
            messages.error(request, f"Not enough stock for {piece.nom}. Available: {piece.quantite_stock}")
        else:
            # Check if piece already added to this intervention
            ip, created = InterventionPiece.objects.get_or_create(
                intervention=intervention, 
                piece=piece,
                defaults={'quantite_utilisee': quantity}
            )
            if not created:
                ip.quantite_utilisee += quantity
                ip.save()
            
            # Decrement stock
            piece.quantite_stock -= quantity
            piece.save()
            
            messages.success(request, f"Added {quantity}x {piece.nom} to intervention.")
            
    return redirect("intervention_detail", pk=pk)


@login_required
def facture_create(request, intervention_pk):
    if not is_mechanic(request.user):
        return HttpResponseForbidden("Only mechanics can create invoices.")

    intervention = get_object_or_404(Intervention, pk=intervention_pk)

    try:
        existing_facture = intervention.facture
    except Facturation.DoesNotExist:
        existing_facture = None

    if existing_facture is not None:
        messages.warning(request, "An invoice already exists for this intervention.")
        return redirect("facture_detail", pk=existing_facture.pk)

    auto_number = f"INV-{timezone.now().year}-{Facturation.objects.count() + 1:04d}"
    form = FacturationForm(request.POST or None, initial={"numero_facture": auto_number})
    if request.method == "POST" and form.is_valid():
        facture = form.save(commit=False)
        facture.numero_facture = auto_number
        facture.intervention = intervention
        facture.save()
        messages.success(request, f"Invoice {facture.numero_facture} created.")
        return redirect("facture_detail", pk=facture.pk)

    return render(
        request,
        "garage/facture_form.html",
        {
            "form": form,
            "intervention": intervention,
        },
    )


@login_required
def facture_detail(request, pk):
    facture = get_object_or_404(Facturation, pk=pk)
    vehicle = facture.intervention.demande.vehicule

    if is_owner(request.user):
        if vehicle.proprietaire != request.user.proprietaire:
            return HttpResponseForbidden("You can only view invoices for your own vehicles.")
    elif not is_mechanic(request.user):
        return HttpResponseForbidden("Access denied.")

    return render(request, "garage/facture_detail.html", {"facture": facture})


@login_required
def facture_pdf(request, pk):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    facture = get_object_or_404(Facturation, pk=pk)
    intervention = facture.intervention
    vehicle = intervention.demande.vehicule

    if is_owner(request.user):
        if vehicle.proprietaire != request.user.proprietaire:
            return HttpResponseForbidden("You can only download invoices for your own vehicles.")
    elif not is_mechanic(request.user):
        return HttpResponseForbidden("Access denied.")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    blue = colors.HexColor("#1a73e8")
    light = colors.HexColor("#f1f5ff")
    elements = []

    title_style = ParagraphStyle("invoice_title", parent=styles["Title"], fontSize=22, textColor=blue, spaceAfter=6)
    elements.append(Paragraph("INVOICE", title_style))
    elements.append(Paragraph(f"<b>{facture.numero_facture}</b>", styles["Normal"]))
    elements.append(Spacer(1, 0.5 * cm))

    for line in [
        f"<b>Vehicle:</b> {vehicle.marque} {vehicle.modele} ({vehicle.annee})",
        f"<b>License Plate:</b> {vehicle.matricule}",
        f"<b>Issue Date:</b> {facture.date_emission.strftime('%Y-%m-%d')}",
        f"<b>Status:</b> {facture.get_statut_display()}",
    ]:
        elements.append(Paragraph(line, styles["Normal"]))
    elements.append(Spacer(1, 0.8 * cm))

    rows = [["Description", "Qty", "Unit Price", "Total"]]
    rows.append(
        [
            f"Labour - {intervention.type_intervention}",
            "1",
            f"{intervention.cout_main_oeuvre} MAD",
            f"{intervention.cout_main_oeuvre} MAD",
        ]
    )
    for ip in intervention.intervention_pieces.all():
        line_total = ip.piece.prix_unitaire * ip.quantite_utilisee
        rows.append(
            [
                ip.piece.nom,
                str(ip.quantite_utilisee),
                f"{ip.piece.prix_unitaire} MAD",
                f"{line_total} MAD",
            ]
        )

    rows.append(["", "", "Subtotal", f"{facture.sous_total} MAD"])
    rows.append(["", "", f"VAT ({facture.tva_percent}%)", f"{facture.montant_tva} MAD"])
    rows.append(["", "", "TOTAL TTC", f"{facture.total_ttc} MAD"])

    table = Table(rows, colWidths=[9 * cm, 2 * cm, 4 * cm, 3 * cm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), blue),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ROWBACKGROUNDS", (0, 1), (-1, -4), [colors.white, light]),
                ("FONTNAME", (0, -3), (-1, -1), "Helvetica-Bold"),
                ("BACKGROUND", (0, -1), (-1, -1), light),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(table)

    if facture.notes:
        elements.append(Spacer(1, 0.8 * cm))
        elements.append(Paragraph(f"<b>Notes:</b> {facture.notes}", styles["Normal"]))

    doc.build(elements)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="invoice_{facture.numero_facture}.pdf"'
    return response


@login_required
def rendezvous_list(request):
    if is_mechanic(request.user):
        rdvs = RendezVous.objects.select_related("vehicule", "mecanicien__user").order_by("date_rdv")
    elif is_owner(request.user):
        rdvs = (
            RendezVous.objects.filter(vehicule__proprietaire=request.user.proprietaire)
            .select_related("vehicule", "mecanicien__user")
            .order_by("date_rdv")
        )
    else:
        return HttpResponseForbidden("Access denied.")

    return render(request, "garage/rendezvous_list.html", {"rdvs": rdvs})


@login_required
def rendezvous_add(request):
    form = RendezVousForm(request.POST or None)

    if is_owner(request.user):
        form.fields["vehicule"].queryset = Vehicule.objects.filter(proprietaire=request.user.proprietaire).order_by(
            "-date_enregistrement"
        )
        form.fields.pop("garage", None)
        form.fields.pop("mecanicien", None)
        form.fields.pop("statut", None)
    elif not is_mechanic(request.user):
        return HttpResponseForbidden("Access denied.")

    if request.method == "POST" and form.is_valid():
        rdv = form.save(commit=False)
        if is_owner(request.user):
            rdv.statut = "scheduled"
            if rdv.garage is None and rdv.vehicule.garage_id:
                rdv.garage = rdv.vehicule.garage
        rdv.save()
        messages.success(request, "Appointment scheduled.")
        return redirect("rendezvous_list")
    return render(request, "garage/rendezvous_form.html", {"form": form, "title": "Schedule Appointment"})


@login_required
def rendezvous_edit(request, pk):
    rdv = get_object_or_404(RendezVous, pk=pk)

    if is_owner(request.user):
        if rdv.vehicule.proprietaire != request.user.proprietaire:
            return HttpResponseForbidden("You can only edit appointments for your own vehicles.")
    elif not is_mechanic(request.user):
        return HttpResponseForbidden("Access denied.")

    form = RendezVousForm(request.POST or None, instance=rdv)
    if is_owner(request.user):
        form.fields["vehicule"].queryset = Vehicule.objects.filter(proprietaire=request.user.proprietaire).order_by(
            "-date_enregistrement"
        )
        form.fields.pop("garage", None)
        form.fields.pop("mecanicien", None)
        form.fields.pop("statut", None)

    if request.method == "POST" and form.is_valid():
        updated_rdv = form.save(commit=False)
        if is_owner(request.user) and updated_rdv.garage is None and updated_rdv.vehicule.garage_id:
            updated_rdv.garage = updated_rdv.vehicule.garage
        updated_rdv.save()
        messages.success(request, "Appointment updated.")
        return redirect("rendezvous_list")
    return render(request, "garage/rendezvous_form.html", {"form": form, "title": "Edit Appointment"})


@login_required
def export_history_pdf(request, matricule):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    vehicle = get_object_or_404(Vehicule, matricule__iexact=matricule)

    if is_owner(request.user):
        if vehicle.proprietaire != request.user.proprietaire:
            return HttpResponseForbidden("You can only export history for your own vehicles.")
    elif not is_mechanic(request.user):
        return HttpResponseForbidden("Access denied.")

    interventions = Intervention.objects.filter(demande__vehicule=vehicle).order_by("-date_debut")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    blue = colors.HexColor("#1a73e8")
    elements = []

    title_style = ParagraphStyle("history_title", parent=styles["Title"], fontSize=20, textColor=blue, spaceAfter=10)
    elements.append(Paragraph("Vehicle Maintenance History", title_style))
    elements.append(Spacer(1, 0.4 * cm))

    for line in [
        f"<b>License Plate:</b> {vehicle.matricule}",
        f"<b>Vehicle:</b> {vehicle.marque} {vehicle.modele} ({vehicle.annee})",
        f"<b>Current Mileage:</b> {vehicle.kilometrage_actuel} km",
        f"<b>Report Date:</b> {timezone.now().strftime('%Y-%m-%d %H:%M')}",
    ]:
        elements.append(Paragraph(line, styles["Normal"]))
    elements.append(Spacer(1, 1 * cm))

    if interventions.exists():
        rows = [["Date", "Type", "Mileage", "Description", "Status", "Cost"]]
        for inv in interventions:
            desc = inv.description_travaux
            rows.append(
                [
                    inv.date_debut.strftime("%Y-%m-%d"),
                    inv.type_intervention,
                    f"{inv.kilometrage} km",
                    (desc[:55] + "...") if len(desc) > 55 else desc,
                    inv.get_etat_display(),
                    f"{inv.total_cost} MAD",
                ]
            )
        table = Table(rows, colWidths=[2.5 * cm, 3.5 * cm, 2.5 * cm, 5 * cm, 2 * cm, 2.5 * cm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), blue),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5ff")]),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        elements.append(table)
    else:
        elements.append(Paragraph("No maintenance records found.", styles["Normal"]))

    doc.build(elements)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="history_{vehicle.matricule}.pdf"'
    return response


# ─── Piece Management ─────────────────────────────────────────────────────────

@login_required
def piece_list(request):
    pieces = Piece.objects.select_related('garage').order_by('nom')
    return render(request, "garage/piece_list.html", {"pieces": pieces})


@login_required
def piece_add(request):
    if not is_mechanic(request.user):
        return HttpResponseForbidden("Access denied. Only mechanics can add parts.")
    
    form = PieceForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Part added successfully.")
        return redirect("piece_list")
    
    return render(request, "garage/piece_form.html", {"form": form, "title": "Add New Part"})


@login_required
def piece_edit(request, pk):
    if not is_mechanic(request.user):
        return HttpResponseForbidden("Access denied. Only mechanics can edit parts.")
    
    piece = get_object_or_404(Piece, pk=pk)
    form = PieceForm(request.POST or None, request.FILES or None, instance=piece)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Part '{piece.nom}' updated.")
        return redirect("piece_list")
    
    return render(request, "garage/piece_form.html", {"form": form, "title": f"Edit Part: {piece.nom}"})


@login_required
def piece_delete(request, pk):
    if not is_mechanic(request.user):
        return HttpResponseForbidden("Access denied. Only mechanics can delete parts.")
    
    piece = get_object_or_404(Piece, pk=pk)
    if request.method == "POST":
        nom = piece.nom
        piece.delete()
        messages.success(request, f"Part '{nom}' deleted.")
        return redirect("piece_list")
    
    return render(request, "garage/piece_confirm_delete.html", {"piece": piece})


@login_required
def piece_buy(request, pk):
    if not is_owner(request.user):
        return HttpResponseForbidden("Access denied. Only vehicle owners can buy parts.")
    
    piece = get_object_or_404(Piece, pk=pk)
    
    if piece.quantite_stock <= 0:
        messages.error(request, f"Sorry, '{piece.nom}' is out of stock.")
        return redirect("piece_list")
    
    proprietaire = request.user.proprietaire
    vehicle = Vehicule.objects.filter(proprietaire=proprietaire).first()
    
    if not vehicle:
        messages.error(request, "You need to register a vehicle before buying parts.")
        return redirect("vehicle_add")
    
    # Create a simple "Purchase" flow
    # 1. Create a hidden service request
    demande = Demande.objects.create(
        vehicule=vehicle,
        garage=piece.garage,
        description_note=f"Direct purchase of {piece.nom}",
        statut="completed",
        priorite="low"
    )
    
    # 2. Create the intervention (service)
    intervention = Intervention.objects.create(
        demande=demande,
        date_debut=timezone.now(),
        date_fin=timezone.now(),
        type_intervention="Part Purchase",
        description_travaux=f"Sold part: {piece.nom}",
        etat="done",
        cout_main_oeuvre=0,
        kilometrage=vehicle.kilometrage_actuel
    )
    
    # 3. Link the piece to the intervention
    InterventionPiece.objects.create(
        intervention=intervention,
        piece=piece,
        quantite_utilisee=1
    )
    
    # 4. Create invoice
    auto_number = f"INV-PURCH-{timezone.now().year}-{Facturation.objects.count() + 1:04d}"
    Facturation.objects.create(
        intervention=intervention,
        numero_facture=auto_number,
        statut="issued",
        notes=f"Invoice for purchase of {piece.nom}"
    )
    
    # 5. Decrement stock
    piece.quantite_stock -= 1
    piece.save()
    
    messages.success(request, f"You successfully purchased '{piece.nom}'! An invoice has been generated.")
    return redirect("piece_list")
