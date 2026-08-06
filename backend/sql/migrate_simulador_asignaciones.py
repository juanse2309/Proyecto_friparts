"""
Migración: tabla simulador_asignaciones — estado propio y aislado del
simulador de programación (2026-08-06). NO toca db_programacion/db_inyeccion
ni ninguna tabla del MES real; el usuario pidió explícitamente que el
simulador viva aparte hasta que se valide que funciona.

Uso:
  - origen='SNAPSHOT_INICIAL': lo que el Jefe de Planta reporta manualmente
    como montado ahora mismo (punto de partida, ya que el simulador no lee
    el estado real de planta — db_inyeccion/db_programacion no guardan
    código de molde, solo cavidades).
  - origen='SUGERIDO_ACEPTADO': lo que el simulador propuso y el usuario
    aceptó dentro de su propio sandbox.
  - estado='ACTIVA' mientras el recurso (máquina+portamolde+macho) sigue
    ocupado en la simulación; 'LIBERADA' cuando se termina esa corrida.

codigo_macho es nullable: no todos los moldes usan macho. La compatibilidad
molde<->macho no se guarda como relación fija — se calcula por diámetro
(diametro_interno de la referencia vs diametro_interno_mm del macho, +/-1mm),
confirmado por el usuario 2026-08-06.

No destructiva: CREATE TABLE IF NOT EXISTS.
"""
from backend.core.sql_database import db
from backend.app import app
from sqlalchemy import text

with app.app_context():
    try:
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS simulador_asignaciones (
                id                  SERIAL PRIMARY KEY,
                maquina             VARCHAR(80) NOT NULL,
                codigo_portamolde   VARCHAR(10) NOT NULL,
                codigo_molde        VARCHAR(50) NOT NULL,
                codigo_referencia   VARCHAR(50) NOT NULL,
                codigo_macho        VARCHAR(50),
                cavidades           INTEGER DEFAULT 1,
                origen              VARCHAR(30) NOT NULL,
                estado              VARCHAR(20) NOT NULL DEFAULT 'ACTIVA',
                responsable         VARCHAR(150),
                creado_en           TIMESTAMP DEFAULT now(),
                liberado_en         TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS ix_simulador_asignaciones_estado
                ON simulador_asignaciones (estado);
            CREATE INDEX IF NOT EXISTS ix_simulador_asignaciones_maquina
                ON simulador_asignaciones (maquina);
        """))
        db.session.commit()
        print("Migración exitosa: simulador_asignaciones creada.")
    except Exception as e:
        db.session.rollback()
        print("Error en migración:", e)
