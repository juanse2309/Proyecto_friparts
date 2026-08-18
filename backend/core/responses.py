"""Contrato único de respuesta JSON para la API.

Forma fija, sea cual sea el endpoint:
    éxito -> {"success": true,  "data": <payload>, "error": null}
    error -> {"success": false, "data": null,       "error": "<mensaje>"}

`message` y `code` son opcionales y se agregan solo si se pasan. Cualquier
otro kwarg (**extra) se agrega también a nivel raíz, para casos como los
metadatos de OwnershipMismatchException (responsable_db/responsable_in) que
el frontend necesita leer sin ir a buscar dentro de `data`.
"""
from flask import jsonify


def api_success(data=None, message=None, status_code=200, **extra):
    body = {"success": True, "data": data, "error": None}
    if message is not None:
        body["message"] = message
    if extra:
        body.update(extra)
    return jsonify(body), status_code


def api_error(message, status_code=400, code=None, **extra):
    body = {"success": False, "data": None, "error": message}
    if code is not None:
        body["code"] = code
    if extra:
        body.update(extra)
    return jsonify(body), status_code
