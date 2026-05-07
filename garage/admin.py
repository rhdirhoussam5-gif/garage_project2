from django.contrib import admin
from .models import (
    Garage, Proprietaire, Mecanicien, Vehicule,
    Demande, Piece, Intervention, InterventionPiece,
    Scan, Configuration, FileUpload, Facturation, RendezVous,
    TacheIntervention
)


@admin.register(Garage)
class GarageAdmin(admin.ModelAdmin):
    list_display = ['nom', 'adresse', 'telephone', 'max_capacite']


@admin.register(Vehicule)
class VehiculeAdmin(admin.ModelAdmin):
    list_display  = ['matricule', 'marque', 'modele', 'annee', 'kilometrage_actuel']
    search_fields = ['matricule', 'marque', 'modele']


class TacheInterventionInline(admin.TabularInline):
    model = TacheIntervention
    extra = 1

@admin.register(Intervention)
class InterventionAdmin(admin.ModelAdmin):
    list_display  = ['id', 'demande', 'type_intervention', 'etat', 'date_debut', 'date_estimee_fin', 'is_overdue', 'cout_main_oeuvre']
    list_filter   = ['etat', 'date_debut']
    search_fields = ['demande__vehicule__matricule', 'type_intervention']
    inlines = [TacheInterventionInline]


@admin.register(Demande)
class DemandeAdmin(admin.ModelAdmin):
    list_display = ['id', 'vehicule', 'statut', 'priorite', 'date_creation']
    list_filter  = ['statut', 'priorite']


# --- OPTIONAL FEATURE: CSV Export ---
import csv
from django.http import HttpResponse

@admin.action(description="Export Selected as CSV")
def export_as_csv(modeladmin, request, queryset):
    meta = modeladmin.model._meta
    field_names = [field.name for field in meta.fields]

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename={meta.model_name}.csv'
    writer = csv.writer(response)

    writer.writerow(field_names)
    for obj in queryset:
        writer.writerow([getattr(obj, field) for field in field_names])
    return response

@admin.register(Facturation)
class FacturationAdmin(admin.ModelAdmin):
    list_display  = ['numero_facture', 'intervention', 'date_emission', 'statut', 'tva_percent']
    list_filter   = ['statut']
    search_fields = ['numero_facture', 'intervention__demande__vehicule__matricule']
    actions = [export_as_csv] # --- OPTIONAL FEATURE ---


@admin.register(RendezVous)
class RendezVousAdmin(admin.ModelAdmin):
    list_display = ['vehicule', 'date_rdv', 'motif', 'statut', 'mecanicien']
    list_filter  = ['statut', 'date_rdv']
    search_fields = ['vehicule__matricule', 'motif']


admin.site.register(Proprietaire)
@admin.register(Mecanicien)
class MecanicienAdmin(admin.ModelAdmin):
    list_display = ['user', 'garage', 'telephone', 'specialite', 'total_gains']
admin.site.register(Piece)
admin.site.register(InterventionPiece)
admin.site.register(Scan)
admin.site.register(Configuration)
admin.site.register(FileUpload)