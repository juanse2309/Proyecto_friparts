"""
backfill_horas_fin_semana.py — Recalcula horas_ordinarias/horas_extras historicas
de sabados y domingos usando el motor de reglas ya corregido (ReglasAsistencia).

Motivo: antes de la correccion en nomina_service.py, un fallo de parseo de hora
(formato distinto a 'HH:MM') hacia que calcular_jornada_y_extras devolviera
0.0/0.0 silenciosamente, incluso en sabado/domingo donde deberia asignarse
el 100% del tiempo neto a horas_extras.

Uso:
    python -m backend.scripts.backfill_horas_fin_semana              # dry-run (no escribe nada)
    python -m backend.scripts.backfill_horas_fin_semana --commit     # aplica los cambios

Reglas de seguridad:
    - NUNCA modifica registros con estado_pago == 'PROCESADO' (nomina ya liquidada).
      Esos casos se listan aparte para ajuste contable manual en el proximo corte.
    - Solo recalcula registros de sabado/domingo (weekday >= 5) cuyo valor
      almacenado difiere del recalculado.
    - Corre dentro de una unica transaccion; si algo falla, rollback total.
"""
import os
import sys
import argparse
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("backfill_fin_semana")

# Asegurar que el path del proyecto esté disponible (igual que el resto de scripts en backend/scripts)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', action='store_true', help='Aplica los cambios (default: dry-run)')
    args = parser.parse_args()

    from backend.app import app
    from backend.core.sql_database import db
    from backend.models.sql_models import RegistroAsistencia
    from backend.models.nomina_models import RegistroAsistencia as RegistroAsistenciaDTO
    from backend.services.nomina_service import ReglasAsistencia

    with app.app_context():
        registros = (
            db.session.query(RegistroAsistencia)
            .filter(RegistroAsistencia.ingreso_real.isnot(None))
            .filter(RegistroAsistencia.salida_real.isnot(None))
            .all()
        )

        candidatos = [r for r in registros if r.fecha and r.fecha.weekday() >= 5]

        corregidos = []
        bloqueados_procesados = []
        sin_cambios = 0
        no_calculables = []

        for r in candidatos:
            if not r.ingreso_real or not r.salida_real or str(r.ingreso_real).upper() == 'AUSENTE':
                continue

            dto = RegistroAsistenciaDTO(
                fecha=r.fecha,
                ingreso_real=r.ingreso_real,
                salida_real=r.salida_real,
            )
            calculo = ReglasAsistencia.calcular_jornada_y_extras(dto)
            nuevo_ord = calculo['horas_ordinarias']
            nuevo_ext = calculo['horas_extras']

            actual_ord = float(r.horas_ordinarias or 0)
            actual_ext = float(r.horas_extras or 0)

            if nuevo_ord == actual_ord and nuevo_ext == actual_ext:
                sin_cambios += 1
                continue

            if nuevo_ord == 0.0 and nuevo_ext == 0.0:
                # El motor de reglas sigue sin poder calcular este registro
                # (dato irrecuperable, ej. salida <= ingreso). Ya quedo logueado
                # como warning por calcular_jornada_y_extras.
                no_calculables.append(r)
                continue

            entrada = {
                'id': r.id,
                'fecha': r.fecha,
                'colaborador': r.colaborador,
                'ingreso_real': r.ingreso_real,
                'salida_real': r.salida_real,
                'antes': (actual_ord, actual_ext),
                'despues': (nuevo_ord, nuevo_ext),
            }

            if r.estado_pago == 'PROCESADO':
                bloqueados_procesados.append(entrada)
                continue

            corregidos.append(entrada)
            if args.commit:
                r.horas_ordinarias = nuevo_ord
                r.horas_extras = nuevo_ext

        logger.info(f"Registros sabado/domingo evaluados: {len(candidatos)}")
        logger.info(f"Sin cambios (ya correctos):          {sin_cambios}")
        logger.info(f"No calculables (dato irrecuperable):  {len(no_calculables)}")
        logger.info(f"PROCESADOS bloqueados (requieren ajuste manual): {len(bloqueados_procesados)}")
        logger.info(f"A corregir en este run:               {len(corregidos)}")
        print()

        if corregidos:
            print("--- Registros a corregir ---")
            for e in corregidos:
                print(
                    f"  id={e['id']:<6} {e['fecha']} {e['colaborador']:<25} "
                    f"{e['ingreso_real']}-{e['salida_real']}  "
                    f"ord/ext {e['antes']} -> {e['despues']}"
                )
            print()

        if bloqueados_procesados:
            print("--- PROCESADOS con discrepancia (NO tocados, requieren nota contable manual) ---")
            for e in bloqueados_procesados:
                print(
                    f"  id={e['id']:<6} {e['fecha']} {e['colaborador']:<25} "
                    f"{e['ingreso_real']}-{e['salida_real']}  "
                    f"ord/ext {e['antes']} -> {e['despues']}"
                )
            print()

        if no_calculables:
            print("--- No calculables (revisar ingreso_real/salida_real manualmente) ---")
            for r in no_calculables:
                print(f"  id={r.id:<6} {r.fecha} {r.colaborador:<25} '{r.ingreso_real}'-'{r.salida_real}'")
            print()

        if not args.commit:
            print(f"[DRY-RUN] No se escribio nada en la base de datos. "
                  f"Ejecuta con --commit para aplicar los {len(corregidos)} cambios listados arriba.")
            db.session.rollback()
            return

        if not corregidos:
            print("Nada que aplicar.")
            return

        try:
            db.session.commit()
            print(f"[COMMIT] {len(corregidos)} registros actualizados correctamente.")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Fallo al aplicar cambios, rollback total: {e}")
            sys.exit(1)


if __name__ == '__main__':
    main()
