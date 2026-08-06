# -*- coding: utf-8 -*-
"""Rutas del simulador what-if de programación — sin lógica de negocio,
delega todo a SimuladorService (ver docstring de ese módulo para las reglas
confirmadas y por qué vive aislado del MES real)."""
from flask import Blueprint, request, jsonify, session
import logging

from backend.services.simulador_service import SimuladorService

simulador_bp = Blueprint('simulador_bp', __name__)
logger = logging.getLogger(__name__)


@simulador_bp.route('/api/simulador/snapshot', methods=['POST'])
def cargar_snapshot():
    """Carga manual del Jefe de Planta: qué está montado ahora mismo.
    Body: {"asignaciones": [{"maquina", "codigo_molde", "codigo_portamolde", "codigo_referencia", "codigo_macho"?, "cavidades"?}, ...]}
    codigo_portamolde es obligatorio: cuál de los portamoldes alternativos del molde está montado."""
    data = request.json or {}
    try:
        resultado = SimuladorService.cargar_snapshot_inicial(
            asignaciones=data.get('asignaciones', []),
            responsable=session.get('user', 'SISTEMA'),
        )
        return jsonify({'success': True, **resultado}), 200
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error en cargar_snapshot: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@simulador_bp.route('/api/simulador/auto-detectar', methods=['POST'])
def auto_detectar():
    """Lee db_inyeccion (EN_PROCESO) y auto-carga lo que pueda resolver sin
    ambigüedad. No requiere ningún dato del usuario."""
    try:
        resultado = SimuladorService.auto_detectar_y_cargar(responsable=session.get('user', 'SISTEMA'))
        return jsonify({'success': True, **resultado}), 200
    except Exception as e:
        logger.error(f"Error en auto_detectar: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@simulador_bp.route('/api/simulador/estado', methods=['GET'])
def estado_actual():
    try:
        return jsonify(SimuladorService.obtener_estado_actual()), 200
    except Exception as e:
        logger.error(f"Error en estado_actual: {e}")
        return jsonify([]), 200


@simulador_bp.route('/api/simulador/candidatos', methods=['GET'])
def candidatos():
    limite = request.args.get('limite', 50, type=int)
    try:
        return jsonify(SimuladorService.obtener_candidatos(limite=limite)), 200
    except Exception as e:
        logger.error(f"Error en candidatos: {e}")
        return jsonify([]), 200


@simulador_bp.route('/api/simulador/aceptar', methods=['POST'])
def aceptar():
    data = request.json or {}
    try:
        SimuladorService.aceptar_sugerencia(
            candidato=data.get('candidato', {}),
            responsable=session.get('user', 'SISTEMA'),
        )
        return jsonify({'success': True}), 200
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error en aceptar: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@simulador_bp.route('/api/simulador/liberar/<int:id_asignacion>', methods=['POST'])
def liberar(id_asignacion):
    try:
        SimuladorService.liberar(id_asignacion)
        return jsonify({'success': True}), 200
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Error en liberar: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
