from backend.app import app
from backend.models.sql_models import db, TrazabilidadLote

with app.app_context():
    lotes_a_eliminar = TrazabilidadLote.query.filter(
        TrazabilidadLote.id_lote.ilike('%PRUEBA%') | TrazabilidadLote.id_lote.ilike('%9999%')
    ).all()
    
    count = len(lotes_a_eliminar)
    
    for lote in lotes_a_eliminar:
        db.session.delete(lote)
        
    db.session.commit()
    print(f"Limpieza de SandBox completada: {count} registros eliminados.")
