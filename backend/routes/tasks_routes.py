from flask import Blueprint, send_file
from backend.core.responses import api_success, api_error
from backend.core import task_runner
from backend.utils.auth_middleware import require_login

tasks_bp = Blueprint('tasks_bp', __name__)


@tasks_bp.route('/api/tasks/status/<task_id>', methods=['GET'])
@require_login
def obtener_estado_tarea(task_id):
    """Sondeo generico de estado para cualquier tarea creada via task_runner."""
    task = task_runner.get_task(task_id)
    if not task:
        return api_error("Tarea no encontrada (puede haber expirado)", status_code=404)

    data = {"status": task.status}
    if task.status == task_runner.COMPLETED:
        data["download_url"] = f"/api/tasks/download/{task_id}"
    elif task.status == task_runner.FAILED:
        data["error"] = task.error

    return api_success(data=data)


@tasks_bp.route('/api/tasks/download/<task_id>', methods=['GET'])
@require_login
def descargar_resultado_tarea(task_id):
    """Sirve el archivo generado por una tarea ya COMPLETED."""
    task = task_runner.get_task(task_id)
    if not task or task.status != task_runner.COMPLETED:
        return api_error("Archivo no disponible", status_code=404)

    return send_file(
        task.file_path,
        mimetype=task.mimetype,
        as_attachment=True,
        download_name=task.filename
    )
