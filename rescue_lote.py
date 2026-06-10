from backend.app import app
from backend.models.sql_models import db, TrazabilidadLote

with app.app_context():
    lotes = TrazabilidadLote.query.filter(TrazabilidadLote.id_lote.ilike('%9999%') | TrazabilidadLote.id_lote.ilike('%PRUEBA%') | TrazabilidadLote.id_inyeccion.ilike('%9999%')).all()
    if lotes:
        for lote in lotes:
            lote.estado_actual = 'ABIERTO_PULIDO'
            if not lote.por_pulir or lote.por_pulir <= 0:
                lote.por_pulir = 100
            db.session.commit()
            print(f"SUCCESS: Lote {lote.id_lote} (Iny: {lote.id_inyeccion}) forzado a ABIERTO_PULIDO con por_pulir={lote.por_pulir}")
    else:
        print("ERROR: Ningún lote de prueba encontrado")
