from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User

from .models import (
    Demande,
    Facturation,
    FileUpload,
    Intervention,
    Mecanicien,
    Proprietaire,
    RendezVous,
    Vehicule,
)


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Username"})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Password"})
    )


class MecanicienRegisterForm(UserCreationForm):
    first_name = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "First name"})
    )
    last_name = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Last name"})
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "Email"})
    )
    specialite = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Engine, Brakes"}),
    )
    telephone = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Phone number"}),
    )

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "password1", "password2"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ["username", "password1", "password2"]:
            self.fields[field_name].widget.attrs["class"] = "form-control"


class ProprietaireRegisterForm(UserCreationForm):
    first_name = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "First name"})
    )
    last_name = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Last name"})
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "Email"})
    )
    telephone = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Phone number"}),
    )

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "password1", "password2"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ["username", "password1", "password2"]:
            self.fields[field_name].widget.attrs["class"] = "form-control"


class VehiculeForm(forms.ModelForm):
    class Meta:
        model = Vehicule
        fields = ["proprietaire", "garage", "matricule", "marque", "modele", "annee", "kilometrage_actuel"]
        widgets = {
            "proprietaire": forms.Select(attrs={"class": "form-select"}),
            "garage": forms.Select(attrs={"class": "form-select"}),
            "matricule": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. 123-A-45"}),
            "marque": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Toyota"}),
            "modele": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Corolla"}),
            "annee": forms.NumberInput(attrs={"class": "form-control", "placeholder": "e.g. 2019"}),
            "kilometrage_actuel": forms.NumberInput(
                attrs={"class": "form-control", "placeholder": "e.g. 75000"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["proprietaire"].queryset = Proprietaire.objects.select_related("user").order_by(
            "user__first_name", "user__last_name", "user__username"
        )


class DemandeForm(forms.ModelForm):
    class Meta:
        model = Demande
        fields = ["garage", "description_note", "statut", "priorite"]
        widgets = {
            "garage": forms.Select(attrs={"class": "form-select"}),
            "description_note": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "statut": forms.Select(attrs={"class": "form-select"}),
            "priorite": forms.Select(attrs={"class": "form-select"}),
        }


class InterventionForm(forms.ModelForm):
    class Meta:
        model = Intervention
        fields = [
            "mecanicien",
            "date_debut",
            "date_fin",
            "type_intervention",
            "description_travaux",
            "diagnostic",
            "etat",
            "cout_main_oeuvre",
            "kilometrage",
        ]
        widgets = {
            "mecanicien": forms.Select(attrs={"class": "form-select"}),
            "date_debut": forms.DateTimeInput(attrs={"class": "form-control", "type": "datetime-local"}),
            "date_fin": forms.DateTimeInput(attrs={"class": "form-control", "type": "datetime-local"}),
            "type_intervention": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "e.g. Oil Change"}
            ),
            "description_travaux": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "diagnostic": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "etat": forms.Select(attrs={"class": "form-select"}),
            "cout_main_oeuvre": forms.NumberInput(attrs={"class": "form-control"}),
            "kilometrage": forms.NumberInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["mecanicien"].queryset = Mecanicien.objects.select_related("user").order_by(
            "user__first_name", "user__last_name", "user__username"
        )


class FileUploadForm(forms.ModelForm):
    class Meta:
        model = FileUpload
        fields = ["fichier", "description"]
        widgets = {
            "fichier": forms.ClearableFileInput(attrs={"class": "form-control", "accept": "image/*"}),
            "description": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "e.g. Before/after photo"}
            ),
        }


class FacturationForm(forms.ModelForm):
    class Meta:
        model = Facturation
        fields = ["numero_facture", "date_emission", "statut", "tva_percent", "notes"]
        widgets = {
            "numero_facture": forms.TextInput(attrs={"class": "form-control", "readonly": "readonly"}),
            "date_emission": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "statut": forms.Select(attrs={"class": "form-select"}),
            "tva_percent": forms.NumberInput(attrs={"class": "form-control"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }


class RendezVousForm(forms.ModelForm):
    class Meta:
        model = RendezVous
        fields = ["vehicule", "garage", "mecanicien", "date_rdv", "motif", "description", "statut"]
        widgets = {
            "vehicule": forms.Select(attrs={"class": "form-select"}),
            "garage": forms.Select(attrs={"class": "form-select"}),
            "mecanicien": forms.Select(attrs={"class": "form-select"}),
            "date_rdv": forms.DateTimeInput(attrs={"class": "form-control", "type": "datetime-local"}),
            "motif": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Annual service"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "statut": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["mecanicien"].queryset = Mecanicien.objects.select_related("user").order_by(
            "user__first_name", "user__last_name", "user__username"
        )
