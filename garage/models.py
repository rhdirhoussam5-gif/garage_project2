from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


# ─── Garage ───────────────────────────────────────────────────────────────────

class Garage(models.Model):
    nom          = models.CharField(max_length=150)
    adresse      = models.TextField()
    telephone    = models.CharField(max_length=20)
    max_capacite = models.IntegerField(default=10)

    def __str__(self):
        return self.nom


# ─── User Roles ───────────────────────────────────────────────────────────────

class Proprietaire(models.Model):
    """Vehicle owner — extends Django User."""
    user             = models.OneToOneField(User, on_delete=models.CASCADE, related_name='proprietaire')
    telephone        = models.CharField(max_length=20, blank=True)
    date_inscription = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.get_full_name()} (Owner)"


class Mecanicien(models.Model):
    """Mechanic — extends Django User, belongs to a Garage."""
    user       = models.OneToOneField(User, on_delete=models.CASCADE, related_name='mecanicien')
    garage     = models.ForeignKey(Garage, on_delete=models.SET_NULL, null=True, blank=True, related_name='mecaniciens')
    telephone  = models.CharField(max_length=20, blank=True)
    specialite = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.user.get_full_name()} (Mechanic)"

    @property
    def total_gains(self):
        from django.db.models import Sum
        total = TacheIntervention.objects.filter(
            intervention__mecanicien=self, 
            est_terminee=True
        ).aggregate(Sum('gain'))['gain__sum']
        return total or 0.00


# ─── Vehicle ──────────────────────────────────────────────────────────────────

class Vehicule(models.Model):
    """License plate is the unique identifier for every vehicle."""
    proprietaire       = models.ForeignKey(Proprietaire, on_delete=models.SET_NULL, null=True, blank=True, related_name='vehicules')
    garage             = models.ForeignKey(Garage, on_delete=models.SET_NULL, null=True, blank=True, related_name='vehicules')
    matricule          = models.CharField(max_length=20, unique=True, verbose_name="License Plate")
    marque             = models.CharField(max_length=100, verbose_name="Brand")
    modele             = models.CharField(max_length=100, verbose_name="Model")
    annee              = models.IntegerField(verbose_name="Year")
    kilometrage_actuel = models.IntegerField(verbose_name="Current Mileage (km)")
    date_enregistrement = models.DateTimeField(auto_now_add=True)

    # --- OPTIONAL FEATURE: Photo ---
    photo = models.ImageField(upload_to='vehicules/', null=True, blank=True, verbose_name="Vehicle Photo")

    def __str__(self):
        return f"{self.matricule} — {self.marque} {self.modele} ({self.annee})"


# ─── Service Request ──────────────────────────────────────────────────────────

class Demande(models.Model):
    STATUS_CHOICES = [
        ('pending',     'Pending'),
        ('in_progress', 'In Progress'),
        ('completed',   'Completed'),
        ('cancelled',   'Cancelled'),
    ]
    PRIORITY_CHOICES = [
        ('low',    'Low'),
        ('medium', 'Medium'),
        ('high',   'High'),
        ('urgent', 'Urgent'),
    ]

    vehicule         = models.ForeignKey(Vehicule, on_delete=models.CASCADE, related_name='demandes')
    garage           = models.ForeignKey(Garage, on_delete=models.SET_NULL, null=True, blank=True)
    date_creation    = models.DateTimeField(auto_now_add=True)
    description_note = models.TextField(blank=True)
    statut           = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    priorite         = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')

    def __str__(self):
        return f"Demande #{self.pk} — {self.vehicule.matricule} [{self.statut}]"


# ─── Diagnostic & Planning ────────────────────────────────────────────────────

class Scan(models.Model):
    """Diagnostic scan performed by a mechanic."""
    demande      = models.ForeignKey(Demande, on_delete=models.CASCADE, related_name='scans')
    mecanicien   = models.ForeignKey(Mecanicien, on_delete=models.SET_NULL, null=True, blank=True, related_name='scans')
    date_scan    = models.DateTimeField(auto_now_add=True)
    codes_defaut = models.TextField(verbose_name="Fault Codes", blank=True)
    observations = models.TextField(blank=True)

    def __str__(self):
        return f"Scan #{self.pk} — {self.demande.vehicule.matricule}"


class Configuration(models.Model):
    """Defines the planned scope of work for a service request."""
    demande       = models.ForeignKey(Demande, on_delete=models.CASCADE, related_name='configurations')
    description   = models.TextField()
    date_creation = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Config #{self.pk} for Demande #{self.demande.pk}"


# ─── Parts Inventory ──────────────────────────────────────────────────────────

class Piece(models.Model):
    """Spare part stocked at the garage."""
    garage          = models.ForeignKey(Garage, on_delete=models.CASCADE, related_name='pieces')
    reference       = models.CharField(max_length=100, unique=True)
    nom             = models.CharField(max_length=150)
    prix_unitaire   = models.DecimalField(max_digits=10, decimal_places=2)
    quantite_stock  = models.IntegerField(default=0)

    # --- OPTIONAL FEATURE: Photo ---
    photo = models.ImageField(upload_to='pieces/', null=True, blank=True, verbose_name="Part Photo")

    def __str__(self):
        return f"{self.nom} (Ref: {self.reference})"


# ─── Intervention ─────────────────────────────────────────────────────────────

class Intervention(models.Model):
    ETAT_CHOICES = [
        ('planned', 'Planned'),
        ('ongoing', 'Ongoing'),
        ('done',    'Done'),
    ]

    demande            = models.ForeignKey(Demande, on_delete=models.CASCADE, related_name='interventions')
    mecanicien         = models.ForeignKey(Mecanicien, on_delete=models.SET_NULL, null=True, blank=True, related_name='interventions')
    date_debut         = models.DateTimeField()
    date_fin           = models.DateTimeField(null=True, blank=True)
    type_intervention  = models.CharField(max_length=100, verbose_name="Type of Service")
    description_travaux = models.TextField(verbose_name="Work Description")
    diagnostic         = models.TextField(blank=True)
    etat               = models.CharField(max_length=20, choices=ETAT_CHOICES, default='planned')
    cout_main_oeuvre   = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    kilometrage        = models.IntegerField(verbose_name="Mileage at Service", default=0)

    # --- OPTIONAL FEATURE: Due Dates ---
    date_estimee_fin   = models.DateTimeField(null=True, blank=True, verbose_name="Estimated Completion")

    @property
    def is_overdue(self):
        from django.utils import timezone
        if self.date_estimee_fin and self.etat != 'done':
            return timezone.now() > self.date_estimee_fin
        return False

    class Meta:
        ordering = ['-date_debut']

    def __str__(self):
        return f"Intervention #{self.pk} — {self.demande.vehicule.matricule}"

    @property
    def total_parts_cost(self):
        return sum(
            ip.piece.prix_unitaire * ip.quantite_utilisee
            for ip in self.intervention_pieces.all()
        )

    @property
    def total_cost(self):
        return self.cout_main_oeuvre + self.total_parts_cost


class InterventionPiece(models.Model):
    """Tracks which parts were used in an intervention and how many."""
    intervention      = models.ForeignKey(Intervention, on_delete=models.CASCADE, related_name='intervention_pieces')
    piece             = models.ForeignKey(Piece, on_delete=models.CASCADE)
    quantite_utilisee = models.IntegerField(default=1)

    def __str__(self):
        return f"{self.quantite_utilisee}x {self.piece.nom} in Intervention #{self.intervention.pk}"

    @property
    def total_line_cost(self):
        return self.piece.prix_unitaire * self.quantite_utilisee


class TacheIntervention(models.Model):
    """Specific task checklist for an intervention."""
    intervention = models.ForeignKey(Intervention, on_delete=models.CASCADE, related_name='taches')
    nom = models.CharField(max_length=200, verbose_name="Task Description")
    est_terminee = models.BooleanField(default=False, verbose_name="Is Completed?")
    gain = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Gain Mécanicien")

    def __str__(self):
        status = "[x]" if self.est_terminee else "[ ]"
        return f"{status} {self.nom}"


# ─── File Uploads ─────────────────────────────────────────────────────────────

class FileUpload(models.Model):
    """Image or invoice attached to an intervention."""
    intervention = models.ForeignKey(Intervention, on_delete=models.CASCADE, related_name='fichiers')
    fichier      = models.ImageField(upload_to='interventions/%Y/%m/%d/')
    description  = models.CharField(max_length=200, blank=True)
    date_upload  = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"File for Intervention #{self.intervention.pk}"


# ─── NEW: Facturation (Invoicing) ─────────────────────────────────────────────

class Facturation(models.Model):
    """
    Invoice generated after an intervention is completed.
    Automatically sums labour cost + parts cost from the linked Intervention.
    """
    STATUT_CHOICES = [
        ('draft',  'Draft'),
        ('issued', 'Issued'),
        ('paid',   'Paid'),
    ]

    intervention    = models.OneToOneField(Intervention, on_delete=models.CASCADE, related_name='facture')
    numero_facture  = models.CharField(max_length=50, unique=True, verbose_name="Invoice Number")
    date_emission   = models.DateField(default=timezone.now, verbose_name="Issue Date")
    statut          = models.CharField(max_length=20, choices=STATUT_CHOICES, default='draft')
    tva_percent     = models.DecimalField(max_digits=5, decimal_places=2, default=20.00, verbose_name="VAT %")
    notes           = models.TextField(blank=True)

    def __str__(self):
        return f"Invoice {self.numero_facture} — {self.intervention.demande.vehicule.matricule}"

    @property
    def sous_total(self):
        """Subtotal before VAT."""
        return self.intervention.total_cost

    @property
    def montant_tva(self):
        from decimal import Decimal
        return (self.sous_total * self.tva_percent / Decimal('100')).quantize(Decimal('0.01'))

    @property
    def total_ttc(self):
        """Total including VAT."""
        return self.sous_total + self.montant_tva


# ─── NEW: Rendez-vous (Appointments) ─────────────────────────────────────────

class RendezVous(models.Model):
    """
    A scheduled service appointment booked by an owner or mechanic.
    Tied to a vehicle and optionally a mechanic.
    """
    STATUT_CHOICES = [
        ('scheduled',  'Scheduled'),
        ('confirmed',  'Confirmed'),
        ('cancelled',  'Cancelled'),
        ('completed',  'Completed'),
    ]

    vehicule         = models.ForeignKey(Vehicule, on_delete=models.CASCADE, related_name='rendez_vous')
    garage           = models.ForeignKey(Garage, on_delete=models.SET_NULL, null=True, blank=True)
    mecanicien       = models.ForeignKey(Mecanicien, on_delete=models.SET_NULL, null=True, blank=True, related_name='rendez_vous')
    date_rdv         = models.DateTimeField(verbose_name="Appointment Date & Time")
    motif            = models.CharField(max_length=200, verbose_name="Reason for Visit")
    description      = models.TextField(blank=True)
    statut           = models.CharField(max_length=20, choices=STATUT_CHOICES, default='scheduled')
    date_creation    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date_rdv']
        verbose_name = "Rendez-vous"
        verbose_name_plural = "Rendez-vous"

    def __str__(self):
        return f"RDV {self.date_rdv.strftime('%Y-%m-%d %H:%M')} — {self.vehicule.matricule}"