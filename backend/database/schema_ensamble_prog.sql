-- Script para la tabla de programación de ensamble
CREATE TABLE IF NOT EXISTS db_programacion_ensamble (
    id_prog SERIAL PRIMARY KEY,
    id_codigo VARCHAR(50) NOT NULL,
    cantidad_objetivo INTEGER NOT NULL,
    cantidad_realizada INTEGER DEFAULT 0,
    fecha_programada DATE NOT NULL,
    estado VARCHAR(20) DEFAULT 'PENDIENTE' -- PENDIENTE, EN_PROCESO, COMPLETADO
);

-- Index para búsquedas rápidas
CREATE INDEX IF NOT EXISTS idx_prog_ensamble_codigo ON db_programacion_ensamble(id_codigo);
CREATE INDEX IF NOT EXISTS idx_prog_ensamble_estado ON db_programacion_ensamble(estado);
