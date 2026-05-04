from backend.app import app
from backend.models.sql_models import db, ProduccionPulido
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def clean_contaminated_records():
    with app.app_context():
        # Buscar registros que contengan 'FR-'
        contaminated = ProduccionPulido.query.filter(ProduccionPulido.codigo.like('FR-%')).all()
        
        if not contaminated:
            logger.info("No se encontraron registros contaminados con 'FR-'.")
            return

        logger.info(f"Se encontraron {len(contaminated)} registros contaminados.")
        
        for reg in contaminated:
            old_code = reg.codigo
            new_code = old_code.replace('FR-', '').replace('fr-', '').strip().upper()
            logger.info(f"Limpiando: {old_code} -> {new_code}")
            reg.codigo = new_code
            
        try:
            db.session.commit()
            logger.info("✅ Limpieza de registros completada con éxito.")
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Error al limpiar registros: {e}")

if __name__ == "__main__":
    clean_contaminated_records()
