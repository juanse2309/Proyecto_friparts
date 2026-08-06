"""
Migración: base de datos para el simulador de programación (moldes, portamoldes,
machos) — fundamento de datos discutido con el usuario 2026-08-05/06.

Agrega:
  - db_productos: 4 columnas geométricas (diametro_interno, diametro_externo,
    altura, pared) — vienen de "Base de datos ext e int.xlsx". `pared` no es
    solo geometría: es el proxy de tiempo de ciclo que se usa para agrupar
    referencias compatibles, porque no existe una base de datos de ciclo real
    por referencia.
  - rel_producto_molde: que molde produce cada referencia Friparts.
  - db_portamoldes: catalogo de portamoldes fisicos (A-P, Ñ), 1 unidad fisica
    por letra (confirmado por el usuario).
  - rel_molde_portamoldes: que portamolde(s) necesita cada molde.
  - rel_maquina_portamolde: que portamoldes acepta cada maquina (1/4 = mayor
    capacidad: M,N,Ñ,O,P; 2/3 = menor capacidad: A-M), pendiente de verificar
    en planta en la proxima visita del usuario.
  - db_machos: inventario de machos independientes (diametro_interno_mm +
    cantidad_fisica_disponible), tolerancia +/-1mm al calzar contra una
    referencia (distinta de la tolerancia de pared, que es +/-1.5mm).

No destructiva: ADD COLUMN IF NOT EXISTS / CREATE TABLE IF NOT EXISTS, sin
backfill. Los datos (339 referencias mapeadas, 16 machos, 17 portamoldes, la
tabla maquina-portamolde) se cargan en un script aparte una vez exista la
tabla — este script solo crea la forma, no inserta filas.
"""
from backend.core.sql_database import db
from backend.app import app
from sqlalchemy import text

with app.app_context():
    try:
        db.session.execute(text("""
            ALTER TABLE db_productos
                ADD COLUMN IF NOT EXISTS diametro_interno NUMERIC(10, 2),
                ADD COLUMN IF NOT EXISTS diametro_externo NUMERIC(10, 2),
                ADD COLUMN IF NOT EXISTS altura            NUMERIC(10, 2),
                ADD COLUMN IF NOT EXISTS pared             NUMERIC(10, 2);
        """))

        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS rel_producto_molde (
                id                 SERIAL PRIMARY KEY,
                codigo_molde       VARCHAR(50) NOT NULL,
                codigo_referencia  VARCHAR(50) NOT NULL,
                cavidades          INTEGER DEFAULT 1,
                tipo_vinculo       VARCHAR(30) DEFAULT 'CAVIDAD_FIJA',
                activo             BOOLEAN DEFAULT TRUE
            );
            CREATE INDEX IF NOT EXISTS ix_rel_producto_molde_codigo_molde
                ON rel_producto_molde (codigo_molde);
            CREATE INDEX IF NOT EXISTS ix_rel_producto_molde_codigo_referencia
                ON rel_producto_molde (codigo_referencia);
        """))

        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS db_portamoldes (
                id               SERIAL PRIMARY KEY,
                codigo           VARCHAR(10) NOT NULL UNIQUE,
                cantidad_fisica  INTEGER DEFAULT 1,
                activo           BOOLEAN DEFAULT TRUE
            );
        """))

        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS rel_molde_portamoldes (
                id                 SERIAL PRIMARY KEY,
                codigo_molde       VARCHAR(50) NOT NULL,
                codigo_portamolde  VARCHAR(10) NOT NULL
            );
            CREATE INDEX IF NOT EXISTS ix_rel_molde_portamoldes_codigo_molde
                ON rel_molde_portamoldes (codigo_molde);
            CREATE INDEX IF NOT EXISTS ix_rel_molde_portamoldes_codigo_portamolde
                ON rel_molde_portamoldes (codigo_portamolde);
        """))

        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS rel_maquina_portamolde (
                id                 SERIAL PRIMARY KEY,
                maquina            VARCHAR(80) NOT NULL,
                codigo_portamolde  VARCHAR(10) NOT NULL
            );
            CREATE INDEX IF NOT EXISTS ix_rel_maquina_portamolde_maquina
                ON rel_maquina_portamolde (maquina);
            CREATE INDEX IF NOT EXISTS ix_rel_maquina_portamolde_codigo_portamolde
                ON rel_maquina_portamolde (codigo_portamolde);
        """))

        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS db_machos (
                id                          SERIAL PRIMARY KEY,
                codigo_macho                VARCHAR(50) NOT NULL UNIQUE,
                diametro_interno_mm         NUMERIC(10, 2),
                cantidad_fisica_disponible  INTEGER DEFAULT 0,
                activo                      BOOLEAN DEFAULT TRUE
            );
        """))

        db.session.commit()
        print("Migración exitosa: columnas geométricas en db_productos + "
              "rel_producto_molde, db_portamoldes, rel_molde_portamoldes, "
              "rel_maquina_portamolde, db_machos creadas.")
    except Exception as e:
        db.session.rollback()
        print("Error en migración:", e)
