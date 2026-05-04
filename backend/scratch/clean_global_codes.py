from backend.app import app
from backend.models.sql_models import db, ProduccionInyeccion, Ensamble
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def clean_global_contaminated_records():
    with app.app_context():
        # 1. Limpiar Inyección
        iny_contaminated = ProduccionInyeccion.query.filter(ProduccionInyeccion.id_codigo.like('FR-%')).all()
        logger.info(f"Inyección: {len(iny_contaminated)} registros contaminados.")
        for reg in iny_contaminated:
            reg.id_codigo = reg.id_codigo.replace('FR-', '').replace('fr-', '').strip().upper()
        
        # 2. Limpiar Ensamble
        ens_contaminated = Ensamble.query.filter(Ensamble.id_codigo.like('FR-%')).all()
        logger.info(f"Ensamble: {len(ens_contaminated)} registros contaminados.")
        for reg in ens_contaminated:
            reg.id_codigo = reg.id_codigo.replace('FR-', '').replace('fr-', '').strip().upper()
            if reg.buje_ensamble:
                reg.buje_ensamble = reg.buje_ensamble.replace('FR-', '').replace('fr-', '').strip().upper()
            
        try:
            db.session.commit()
            logger.info("✅ Limpieza GLOBAL completada con éxito.")
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Error al limpiar registros globales: {e}")

if __name__ == "__main__":
    clean_global_contaminated_records()
