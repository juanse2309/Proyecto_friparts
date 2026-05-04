
from backend.core.sql_database import db
from backend.models.sql_models import Molde
from backend.app import app

def seed_moldes():
    with app.app_context():
        # Check if table is empty
        count = db.session.query(Molde).count()
        if count == 0:
            print("🌱 Seeding moldes...")
            moldes = [
                Molde(nombre="9304-4C", cavidades_max=4, descripcion="Buje 9304 - 4 Cavidades"),
                Molde(nombre="7097-2C", cavidades_max=2, descripcion="Buje 7097 - 2 Cavidades"),
                Molde(nombre="9289-4C", cavidades_max=4, descripcion="Buje 9289 - 4 Cavidades"),
                Molde(nombre="UNIVERSAL-1C", cavidades_max=1, descripcion="Molde Universal - 1 Cavidad"),
                Molde(nombre="INY-1050-2C", cavidades_max=2, descripcion="Iny 1050 - 2 Cavidades")
            ]
            db.session.add_all(moldes)
            db.session.commit()
            print("✅ Moldes creados con éxito.")
        else:
            print(f"ℹ️ La tabla db_moldes ya tiene {count} registros.")

if __name__ == "__main__":
    seed_moldes()
