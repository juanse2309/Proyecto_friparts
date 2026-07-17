CREATE TABLE IF NOT EXISTS cartera_wo (
    identificacion VARCHAR PRIMARY KEY,
    nombre VARCHAR,
    saldo_total NUMERIC,
    saldo_vencido NUMERIC,
    ultima_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
