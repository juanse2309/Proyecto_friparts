"""Gestor de tareas en background para operaciones largas (ej. generacion de
Excel) que no deben bloquear el hilo HTTP.

In-memory, sin Celery/Redis: gunicorn corre con workers=1 (ver
gunicorn.conf.py) -- un solo proceso Python, asi que un dict en memoria no
sufre la inconsistencia entre workers que tendria con mas de un proceso.
Mismo supuesto que ya usan PRODUCTOS_V2_CACHE/NamespaceTTLCache. Si el
proyecto alguna vez pasa a mas de un worker, este modulo deja de ser valido
y hay que migrar a Redis/DB -- no antes.

Patron de ejecucion identico al ya usado en wo_routes.py para la
sincronizacion de cartera/clientes: threading.Thread(daemon=True) +
app.app_context() explicito, porque Flask-SQLAlchemy resuelve db.session vía
contexto thread-local y un hilo nuevo no lo hereda solo.
"""
import os
import time
import uuid
import logging
import threading
from dataclasses import dataclass, field
from typing import Callable, Optional

logger = logging.getLogger(__name__)

PENDING = 'PENDING'
RUNNING = 'RUNNING'
COMPLETED = 'COMPLETED'
FAILED = 'FAILED'

# Una tarea terminada (COMPLETED/FAILED) que nadie descarga en este lapso se
# purga junto con su archivo temporal, para no acumular basura en disco.
_TASK_TTL_SECONDS = 30 * 60


@dataclass
class Task:
    id: str
    status: str = PENDING
    file_path: Optional[str] = None
    filename: Optional[str] = None
    mimetype: Optional[str] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None


_tasks: dict[str, Task] = {}
_lock = threading.Lock()


def create_task() -> str:
    """Registra una tarea PENDING y devuelve su id. Llamar desde el hilo HTTP."""
    task_id = uuid.uuid4().hex
    with _lock:
        _purgar_vencidas()
        _tasks[task_id] = Task(id=task_id)
    return task_id


def get_task(task_id: str) -> Optional[Task]:
    with _lock:
        return _tasks.get(task_id)


def run_in_background(task_id: str, app, target: Callable, *args, **kwargs) -> None:
    """
    Ejecuta target(task_id, *args, **kwargs) en un hilo daemon dentro del
    app_context de `app`. `target` es responsable de dejar la tarea en
    COMPLETED (via set_completed) o FAILED (via set_failed) al terminar;
    cualquier excepcion no capturada por `target` tambien se traduce a FAILED
    aqui como red de seguridad.
    """
    def _wrapper():
        with app.app_context():
            _marcar_en_progreso(task_id)
            try:
                target(task_id, *args, **kwargs)
            except Exception as e:
                logger.error(f"[TaskRunner] Tarea {task_id} fallo sin capturar: {e}")
                set_failed(task_id, str(e))

    threading.Thread(target=_wrapper, daemon=True).start()


def set_completed(task_id: str, file_path: str, filename: str, mimetype: str) -> None:
    with _lock:
        t = _tasks.get(task_id)
        if t:
            t.status = COMPLETED
            t.file_path = file_path
            t.filename = filename
            t.mimetype = mimetype
            t.finished_at = time.time()


def set_failed(task_id: str, error: str) -> None:
    with _lock:
        t = _tasks.get(task_id)
        if t:
            t.status = FAILED
            t.error = error
            t.finished_at = time.time()


def _marcar_en_progreso(task_id: str) -> None:
    with _lock:
        t = _tasks.get(task_id)
        if t:
            t.status = RUNNING


def _purgar_vencidas() -> None:
    """Requiere _lock ya tomado. Borra tareas terminadas hace mas de _TASK_TTL_SECONDS y su archivo."""
    ahora = time.time()
    vencidas = [
        tid for tid, t in _tasks.items()
        if t.finished_at and (ahora - t.finished_at) > _TASK_TTL_SECONDS
    ]
    for tid in vencidas:
        t = _tasks.pop(tid, None)
        if t and t.file_path:
            try:
                os.remove(t.file_path)
            except OSError:
                pass
