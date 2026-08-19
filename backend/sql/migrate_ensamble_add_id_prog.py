"""
Migración: agrega `id_prog` a db_ensambles.

Antes de este cambio, EnsambleService.reportar_multi recalculaba
cantidad_realizada de una ProgramacionEnsamble sumando TODOS los registros
FINALIZADO de db_ensambles que coincidieran en (id_codigo, op_numero) --
sin ningún vínculo real con la meta específica que se estaba reportando.
Esto contamina el avance entre metas distintas del mismo producto (sobre
todo con op_numero en blanco, el caso más común en planta): una meta recién
creada podía aparecer ya "completada" arrastrando producción histórica que
nunca se reportó contra ella. Reproducido en vivo: meta nueva de 10
unidades, sin reportar nada, apareciendo como 200% completada.

Semántica de la columna nueva:
  - id_prog -> FK lógica (sin constraint formal, mismo patrón que
    buje_ensamble/id_ensamble en esta tabla) hacia
    programacion_ensamble.id_prog. Se puebla en EnsambleService.reportar_multi
    a partir de reg_data['id_prog'] cuando el operario reportó contra una
    tarea concreta de la lista de pendientes. Queda NULL en reportes
    manuales sin tarea asociada (Registro Manual Directo).

No destructiva: ADD COLUMN IF NOT EXISTS, sin backfill. Las filas ya
existentes en db_ensambles quedan con id_prog en NULL -- no hay forma de
reconstruir retroactivamente contra qué meta se reportó cada una. Como
consecuencia, el cantidad_realizada de una ProgramacionEnsamble ya existente
en progreso solo se recalculará de forma correcta a partir del PRÓXIMO
reporte que llegue contra ella (los reportes históricos no cuentan).
"""
from backend.core.sql_database import db
from backend.app import app
from sqlalchemy import text

with app.app_context():
    try:
        db.session.execute(text("""
            ALTER TABLE db_ensambles
                ADD COLUMN IF NOT EXISTS id_prog INTEGER;
        """))
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_db_ensambles_id_prog
                ON db_ensambles (id_prog);
        """))

        db.session.commit()
        print("Migración exitosa: 'id_prog' agregada a db_ensambles.")
    except Exception as e:
        db.session.rollback()
        print("Error en migración:", e)
