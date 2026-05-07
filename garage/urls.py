from django.urls import path

from . import views


urlpatterns = [
    path("", views.login_view, name="home"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("register/", views.register_choice, name="register_choice"),
    path("register/owner/", views.register_owner, name="register_owner"),
    path("register/mechanic/", views.register_mechanic, name="register_mechanic"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("my-vehicles/", views.client_dashboard, name="client_dashboard"),
    path("vehicles/", views.vehicle_list, name="vehicle_list"),
    path("vehicles/add/", views.vehicle_add, name="vehicle_add"),
    path("vehicles/<int:pk>/", views.vehicle_detail, name="vehicle_detail"),
    path("vehicles/<int:pk>/edit/", views.vehicle_edit, name="vehicle_edit"),
    path("vehicles/<int:vehicle_pk>/request/", views.demande_add, name="demande_add"),
    path("demande/<int:demande_pk>/intervention/add/", views.intervention_add, name="intervention_add"),
    path("interventions/<int:pk>/", views.intervention_detail, name="intervention_detail"),
    path("interventions/<int:intervention_pk>/upload/", views.upload_file, name="upload_file"),
    path("interventions/<int:intervention_pk>/invoice/create/", views.facture_create, name="facture_create"),
    path("invoices/<int:pk>/", views.facture_detail, name="facture_detail"),
    path("invoices/<int:pk>/pdf/", views.facture_pdf, name="facture_pdf"),
    path("appointments/", views.rendezvous_list, name="rendezvous_list"),
    path("appointments/add/", views.rendezvous_add, name="rendezvous_add"),
    path("appointments/<int:pk>/edit/", views.rendezvous_edit, name="rendezvous_edit"),
    path("history/<str:matricule>/pdf/", views.export_history_pdf, name="export_history_pdf"),
]
