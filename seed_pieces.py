import os
import django
import sys

# Set up Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mygarageproject.settings')
django.setup()

from garage.models import Piece, Garage

def seed_pieces():
    # Get or create a default garage
    garage, _ = Garage.objects.get_or_create(
        nom="Default Garage",
        defaults={"adresse": "123 Main St", "telephone": "0522000000", "max_capacite": 20}
    )

    data = [
        {
            "reference": "REF-COUR-001",
            "nom": "Courroie de distribution",
            "prix_unitaire": 1200.00,
            "quantite_stock": 10,
        },
        {
            "reference": "REF-ALT-002",
            "nom": "Alternateur",
            "prix_unitaire": 2500.00,
            "quantite_stock": 5,
        },
        {
            "reference": "REF-POMP-003",
            "nom": "Pompe à eau",
            "prix_unitaire": 850.00,
            "quantite_stock": 8,
        },
        {
            "reference": "REF-AMOR-004",
            "nom": "Amortisseur",
            "prix_unitaire": 1100.00,
            "quantite_stock": 12,
        },
        {
            "reference": "REF-TPMS-005",
            "nom": "Capteur de pression des pneus (TPMS)",
            "prix_unitaire": 450.00,
            "quantite_stock": 20,
        },
        {
            "reference": "REF-JOIN-006",
            "nom": "Joint de culasse",
            "prix_unitaire": 3200.00,
            "quantite_stock": 3,
        },
    ]

    for item in data:
        piece, created = Piece.objects.update_or_create(
            reference=item["reference"],
            defaults={
                "nom": item["nom"],
                "prix_unitaire": item["prix_unitaire"],
                "quantite_stock": item["quantite_stock"],
                "garage": garage
            }
        )
        if created:
            print(f"Created piece: {piece.nom}")
        else:
            print(f"Updated piece: {piece.nom}")

if __name__ == "__main__":
    seed_pieces()
