# -*- coding: utf-8 -*-
"""
SimuladorService — motor "what-if" de programación de inyección (2026-08-06).

Aislado del MES real a propósito (decisión del usuario): solo LEE
db_productos, db_pedidos, rel_producto_molde, rel_molde_portamoldes,
rel_maquina_portamolde, db_portamoldes, db_machos, y el histórico
db_inyeccion (para tiempo de ciclo real). Nunca escribe en esas tablas.
El único estado que este servicio escribe es 'simulador_asignaciones',
su propio sandbox.

Reglas de negocio confirmadas por el usuario:
  - Brecha a producir por referencia = GREATEST(0, comprometido - p_terminado)
    en db_productos. db_pedidos.estado/cant_alistada no son confiables para
    esto (verificado: hasta pedidos DESPACHADO muestran "pendiente" con esa
    cuenta), así que NO se usan para calcular la brecha.
  - Portamolde y macho son recursos de 1-a-la-vez (portamolde: 1 unidad
    física por letra; macho: cantidad_fisica_disponible limita cuántos se
    pueden usar a la vez). Máquina también es de 1 trabajo a la vez (mismo
    criterio que MaquinaOcupadaException del MES real).
  - Compatibilidad molde<->macho NO es una tabla fija: se calcula por
    diámetro (db_productos.diametro_interno vs db_machos.diametro_interno_mm,
    tolerancia +/-1mm). Si ningún macho calza, se asume que el molde no
    necesita macho (restricción blanda, no bloquea la sugerencia).
  - IMPORTANTE (corregido 2026-08-06): cuando un molde tiene más de un
    portamolde en rel_molde_portamoldes (ej. '9629' -> M, N, Ñ), son
    ALTERNATIVAS intercambiables, no una necesidad simultánea — confirmado
    por el usuario ("si ya está ocupado el M se pasa al N"). El molde se
    monta en UNO solo de esos portamoldes a la vez, el que esté libre. Un
    molde bloquea solo cuando TODAS sus alternativas están ocupadas.
  - Tiempo de ciclo: se usa el promedio de segundos_por_unidad del histórico
    real en db_inyeccion cuando existe (match por id_codigo con o sin
    prefijo 'FR-'); si no hay historial, se usa 'pared' como agrupador de
    referencia (tolerancia +/-1.5mm) solo para visibilidad, no como número.
  - El estado "qué está ocupado ahora" tiene 3 fuentes, en este orden de
    preferencia: (1) AUTO_DETECTADO — se lee (solo SELECT, nunca se escribe)
    db_inyeccion WHERE estado='EN_PROCESO' para inferir que esta corriendo
    en cada maquina AHORA MISMO, sin que nadie digite nada. Confirmado
    2026-08-06 contra el caso real de Maquina 1: 'EN_PROCESO' en
    db_inyeccion coincidio exacto con lo que el usuario reporto a mano.
    db_programacion NO sirve para esto — su 'EN_PROCESO' es historico, se
    acumula desde julio sin limpiarse, no representa el estado actual.
    (2) SNAPSHOT_INICIAL — snapshot manual para las maquinas que la
    deteccion automatica no pudo resolver (el molde no esta en
    rel_producto_molde, o el codigo mapea a mas de un molde/portamolde
    ambiguo dentro de lo que esa maquina acepta - no se adivina cual).
    (3) SUGERIDO_ACEPTADO — lo que el propio simulador va asignando.
"""
import logging
import re
from datetime import datetime

from sqlalchemy import text

from backend.core.sql_database import db
from backend.models.sql_models import SimuladorAsignacion
from backend.utils.formatters import normalizar_codigo_sin_prefijo

logger = logging.getLogger(__name__)

TOLERANCIA_MACHO_MM = 1.0
TOLERANCIA_PARED_MM = 1.5


class SimuladorService:

    # ------------------------------------------------------------------
    # Snapshot / estado del sandbox
    # ------------------------------------------------------------------

    @staticmethod
    def cargar_snapshot_inicial(asignaciones, responsable):
        """Reemplaza el snapshot inicial completo (no acumula con corridas
        previas de snapshot — cada carga manual describe el estado completo
        de planta en ese momento). Las asignaciones ya aceptadas del
        simulador (SUGERIDO_ACEPTADO) no se tocan.

        asignaciones: lista de dicts {maquina, codigo_molde, codigo_portamolde,
        codigo_referencia, codigo_macho (opcional), cavidades (opcional)}.
        codigo_portamolde es OBLIGATORIO y debe ser el portamolde específico
        realmente montado (un molde puede tener varias alternativas en
        rel_molde_portamoldes — aquí se declara cuál de ellas está en uso
        ahora mismo, no todas)."""
        try:
            maquinas_auto = {r[0] for r in db.session.execute(text(
                "SELECT DISTINCT maquina FROM simulador_asignaciones WHERE origen = 'AUTO_DETECTADO' AND estado = 'ACTIVA'"
            )).fetchall()}

            db.session.execute(text(
                "DELETE FROM simulador_asignaciones WHERE origen = 'SNAPSHOT_INICIAL'"
            ))

            creadas = []
            for asign in asignaciones:
                if asign.get('maquina') in maquinas_auto:
                    raise ValueError(
                        f"'{asign['maquina']}' ya fue detectada automáticamente (EN_PROCESO en db_inyeccion) — "
                        f"no se puede sobrescribir a mano. Libérala primero si el dato real cambió."
                    )
                portamolde = asign.get('codigo_portamolde')
                if not portamolde:
                    raise ValueError(
                        f"Falta codigo_portamolde para el molde '{asign['codigo_molde']}' "
                        f"— hay que indicar cuál de sus portamoldes alternativos está montado ahora."
                    )
                alternativas = SimuladorService._portamoldes_de_molde(asign['codigo_molde'])
                if portamolde not in alternativas:
                    raise ValueError(
                        f"'{portamolde}' no es un portamolde válido para el molde '{asign['codigo_molde']}' "
                        f"(alternativas registradas: {alternativas})."
                    )
                fila = SimuladorAsignacion(
                    maquina=asign['maquina'],
                    codigo_portamolde=portamolde,
                    codigo_molde=asign['codigo_molde'],
                    codigo_referencia=asign['codigo_referencia'],
                    codigo_macho=asign.get('codigo_macho'),
                    cavidades=asign.get('cavidades', 1),
                    origen='SNAPSHOT_INICIAL',
                    estado='ACTIVA',
                    responsable=responsable,
                )
                db.session.add(fila)
                creadas.append(fila)

            db.session.commit()
            return {'filas_creadas': len(creadas)}
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error en cargar_snapshot_inicial: {e}")
            raise

    @staticmethod
    def liberar(id_asignacion):
        fila = SimuladorAsignacion.query.get(id_asignacion)
        if not fila or fila.estado != 'ACTIVA':
            raise ValueError('Asignación no encontrada o ya liberada.')
        fila.estado = 'LIBERADA'
        fila.liberado_en = datetime.utcnow()
        db.session.commit()

    @staticmethod
    def obtener_estado_actual():
        filas = SimuladorAsignacion.query.filter_by(estado='ACTIVA').order_by(SimuladorAsignacion.maquina).all()
        return [{
            'id': f.id, 'maquina': f.maquina, 'codigo_portamolde': f.codigo_portamolde,
            'codigo_molde': f.codigo_molde, 'codigo_referencia': f.codigo_referencia,
            'codigo_macho': f.codigo_macho, 'cavidades': f.cavidades, 'origen': f.origen,
        } for f in filas]

    # ------------------------------------------------------------------
    # Auto-deteccion (lee db_inyeccion EN_PROCESO, nunca escribe ahi)
    # ------------------------------------------------------------------

    @staticmethod
    def _normalizar_nombre_maquina(nombre):
        """'MAQUINA No. 1' -> 'Maquina 1' (mismo formato que MAQUINAS_PORTAMOLDES/rel_maquina_portamolde)."""
        match = re.search(r'(\d+)', nombre or '')
        return f'Maquina {match.group(1)}' if match else None

    @staticmethod
    def _portamoldes_de_maquina(maquina):
        rows = db.session.execute(text(
            "SELECT codigo_portamolde FROM rel_maquina_portamolde WHERE maquina = :m"
        ), {'m': maquina}).fetchall()
        return {r[0] for r in rows}

    @staticmethod
    def detectar_estado_actual():
        """Lee (SOLO SELECT) db_inyeccion para inferir que esta corriendo
        ahora mismo en cada maquina, sin que nadie tenga que digitarlo.
        Para cada fila EN_PROCESO cruza el id_codigo (sin prefijo 'FR-')
        contra rel_producto_molde, y el/los molde(s) resultantes contra
        rel_molde_portamoldes filtrado por lo que ESA maquina especifica
        acepta (rel_maquina_portamolde) - si de ahi sale exactamente una
        combinacion molde+portamolde, queda resuelta. Si sale 0 o mas de 1
        (ambiguo), esa maquina va a 'sin_resolver' para completar a mano -
        nunca se elige una al azar."""
        rows = db.session.execute(text("""
            SELECT id_codigo, maquina FROM db_inyeccion
            WHERE estado = 'EN_PROCESO' AND id_codigo IS NOT NULL AND maquina IS NOT NULL
        """)).fetchall()

        resueltas, sin_resolver = [], []
        for id_codigo_raw, maquina_raw in rows:
            maquina = SimuladorService._normalizar_nombre_maquina(maquina_raw)
            codigo = normalizar_codigo_sin_prefijo(id_codigo_raw)

            if not maquina:
                sin_resolver.append({'maquina_original': maquina_raw, 'codigo_referencia': codigo, 'motivo': 'maquina_no_reconocida'})
                continue

            moldes = db.session.execute(text(
                "SELECT DISTINCT codigo_molde, cavidades FROM rel_producto_molde WHERE codigo_referencia = :c AND activo = TRUE"
            ), {'c': codigo}).fetchall()
            if not moldes:
                sin_resolver.append({'maquina': maquina, 'codigo_referencia': codigo, 'motivo': 'sin_molde_mapeado_en_rel_producto_molde'})
                continue

            portamoldes_maquina = SimuladorService._portamoldes_de_maquina(maquina)
            opciones = []
            for codigo_molde, cavidades in moldes:
                portamoldes_molde = set(SimuladorService._portamoldes_de_molde(codigo_molde))
                for portamolde in (portamoldes_molde & portamoldes_maquina):
                    opciones.append({'codigo_molde': codigo_molde, 'codigo_portamolde': portamolde, 'cavidades': cavidades})

            if len(opciones) == 1:
                op = opciones[0]
                resueltas.append({
                    'maquina': maquina, 'codigo_referencia': codigo,
                    'codigo_molde': op['codigo_molde'], 'codigo_portamolde': op['codigo_portamolde'],
                    'cavidades': op['cavidades'],
                })
            else:
                sin_resolver.append({
                    'maquina': maquina, 'codigo_referencia': codigo,
                    'motivo': 'sin_opciones_compatibles_con_la_maquina' if not opciones else 'ambiguo_multiples_moldes_o_portamoldes',
                    'opciones': opciones,
                })

        return resueltas, sin_resolver

    @staticmethod
    def auto_detectar_y_cargar(responsable):
        """Corre detectar_estado_actual() y guarda las resueltas como
        origen='AUTO_DETECTADO' (reemplaza solo ese origen, no toca
        SNAPSHOT_INICIAL manual ni SUGERIDO_ACEPTADO). Devuelve tambien
        sin_resolver para que la vista pida completar solo esas maquinas."""
        resueltas, sin_resolver = SimuladorService.detectar_estado_actual()
        try:
            db.session.execute(text(
                "DELETE FROM simulador_asignaciones WHERE origen = 'AUTO_DETECTADO'"
            ))
            for r in resueltas:
                db.session.add(SimuladorAsignacion(
                    maquina=r['maquina'],
                    codigo_portamolde=r['codigo_portamolde'],
                    codigo_molde=r['codigo_molde'],
                    codigo_referencia=r['codigo_referencia'],
                    cavidades=r['cavidades'],
                    origen='AUTO_DETECTADO',
                    estado='ACTIVA',
                    responsable=responsable,
                ))
            db.session.commit()
            return {'resueltas': resueltas, 'sin_resolver': sin_resolver}
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error en auto_detectar_y_cargar: {e}")
            raise

    # ------------------------------------------------------------------
    # Helpers de factibilidad (leen catálogo, nunca escriben)
    # ------------------------------------------------------------------

    @staticmethod
    def _portamoldes_de_molde(codigo_molde):
        rows = db.session.execute(text(
            "SELECT DISTINCT codigo_portamolde FROM rel_molde_portamoldes WHERE codigo_molde = :m"
        ), {'m': codigo_molde}).fetchall()
        return [r[0] for r in rows]

    @staticmethod
    def _maquinas_que_aceptan(portamolde):
        rows = db.session.execute(text(
            "SELECT maquina FROM rel_maquina_portamolde WHERE codigo_portamolde = :p"
        ), {'p': portamolde}).fetchall()
        return [r[0] for r in rows]

    @staticmethod
    def _recursos_ocupados():
        rows = db.session.execute(text(
            "SELECT maquina, codigo_portamolde, codigo_macho FROM simulador_asignaciones WHERE estado = 'ACTIVA'"
        )).fetchall()
        maquinas_ocupadas = {r[0] for r in rows}
        portamoldes_ocupados = {r[1] for r in rows}
        machos_en_uso = {}
        for r in rows:
            if r[2]:
                machos_en_uso[r[2]] = machos_en_uso.get(r[2], 0) + 1
        return maquinas_ocupadas, portamoldes_ocupados, machos_en_uso

    @staticmethod
    def _macho_compatible(diametro_interno):
        if diametro_interno is None:
            return None
        rows = db.session.execute(text("""
            SELECT codigo_macho, diametro_interno_mm, cantidad_fisica_disponible
            FROM db_machos
            WHERE activo = TRUE AND ABS(diametro_interno_mm - :d) <= :tol
            ORDER BY ABS(diametro_interno_mm - :d) ASC
            LIMIT 1
        """), {'d': float(diametro_interno), 'tol': TOLERANCIA_MACHO_MM}).fetchone()
        return dict(rows._mapping) if rows else None

    @staticmethod
    def _tiempo_ciclo_historico(codigo_referencia):
        row = db.session.execute(text("""
            SELECT AVG(segundos_por_unidad)::NUMERIC(10,1) as promedio, COUNT(*) as n
            FROM db_inyeccion
            WHERE segundos_por_unidad > 0
              AND (id_codigo = :c OR id_codigo = :c_fr)
        """), {'c': codigo_referencia, 'c_fr': f'FR-{codigo_referencia}'}).fetchone()
        if row and row[1] > 0:
            return {'segundos_por_unidad_promedio': float(row[0]), 'corridas_historicas': row[1]}
        return None

    # ------------------------------------------------------------------
    # Etapa 1+2+3: candidatos factibles con score
    # ------------------------------------------------------------------

    @staticmethod
    def obtener_candidatos(limite=50):
        """Referencias con brecha (comprometido > p_terminado) que además
        tienen al menos un molde con máquina libre y portamolde libre ahora
        mismo en el sandbox. Devuelve una opción por (referencia, molde,
        máquina) factible, con el desglose del score visible — no se elige
        una sola 'mejor' de forma oculta."""
        brechas = db.session.execute(text("""
            SELECT id_codigo, descripcion,
                   COALESCE(comprometido, 0) - COALESCE(p_terminado, 0) AS faltante,
                   pared, diametro_interno
            FROM db_productos
            WHERE COALESCE(comprometido, 0) - COALESCE(p_terminado, 0) > 0
            ORDER BY faltante DESC
            LIMIT :lim
        """), {'lim': limite}).fetchall()

        maquinas_ocupadas, portamoldes_ocupados, machos_en_uso = SimuladorService._recursos_ocupados()

        candidatos = []
        for b in brechas:
            codigo_ref, descripcion, faltante, pared, diametro_interno = b
            moldes = db.session.execute(text(
                "SELECT codigo_molde, cavidades, tipo_vinculo FROM rel_producto_molde WHERE codigo_referencia = :c AND activo = TRUE"
            ), {'c': codigo_ref}).fetchall()

            macho = SimuladorService._macho_compatible(diametro_interno)
            macho_disponible = True
            if macho:
                en_uso = machos_en_uso.get(macho['codigo_macho'], 0)
                macho_disponible = en_uso < macho['cantidad_fisica_disponible']

            for codigo_molde, cavidades, tipo_vinculo in moldes:
                alternativas = SimuladorService._portamoldes_de_molde(codigo_molde)
                if not alternativas:
                    continue

                historial = SimuladorService._tiempo_ciclo_historico(codigo_ref)

                # Alternativas intercambiables (ver docstring del módulo): se
                # prueba cada portamolde libre y, para cada uno, cada máquina
                # libre que lo acepte — no se exige que TODAS estén libres.
                for portamolde in alternativas:
                    if portamolde in portamoldes_ocupados:
                        continue
                    maquinas = [m for m in SimuladorService._maquinas_que_aceptan(portamolde) if m not in maquinas_ocupadas]
                    for maquina in maquinas:
                        candidatos.append({
                            'codigo_referencia': codigo_ref,
                            'descripcion': descripcion,
                            'faltante': float(faltante),
                            'codigo_molde': codigo_molde,
                            'tipo_vinculo': tipo_vinculo,
                            'cavidades': cavidades,
                            'portamoldes_alternativos': alternativas,
                            'portamolde_sugerido': portamolde,
                            'maquina_sugerida': maquina,
                            'pared': float(pared) if pared is not None else None,
                            'macho_requerido': macho['codigo_macho'] if macho else None,
                            'macho_disponible': macho_disponible if macho else None,
                            'tiempo_ciclo_seg_promedio': historial['segundos_por_unidad_promedio'] if historial else None,
                            'corridas_historicas': historial['corridas_historicas'] if historial else 0,
                        })

        return candidatos

    @staticmethod
    def aceptar_sugerencia(candidato, responsable):
        """Mueve un candidato de obtener_candidatos() a 'ACTIVA' en el
        sandbox — bloquea sus portamoldes/máquina/macho para las próximas
        sugerencias, sin tocar nada del MES real."""
        if candidato.get('macho_requerido') and candidato.get('macho_disponible') is False:
            raise ValueError('El macho requerido ya no está disponible.')

        try:
            db.session.add(SimuladorAsignacion(
                maquina=candidato['maquina_sugerida'],
                codigo_portamolde=candidato['portamolde_sugerido'],
                codigo_molde=candidato['codigo_molde'],
                codigo_referencia=candidato['codigo_referencia'],
                codigo_macho=candidato.get('macho_requerido'),
                cavidades=candidato.get('cavidades', 1),
                origen='SUGERIDO_ACEPTADO',
                estado='ACTIVA',
                responsable=responsable,
            ))
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error en aceptar_sugerencia: {e}")
            raise
