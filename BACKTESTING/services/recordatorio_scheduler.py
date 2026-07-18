"""
Scheduler del módulo de Recordatorios (APScheduler).

Gunicorn corre varios workers en el mismo proceso master; solo UNO debe
disparar el job (si no, se enviarían mensajes duplicados). Se usa un lock
de archivo (fcntl, POSIX) en el volumen /data: el primer worker que lo
adquiere arranca el scheduler, los demás lo omiten. En Windows (desarrollo
local, un solo proceso) no hay fcntl y se arranca sin lock.
"""
import logging
import os
from datetime import datetime

import config
import models_recordatorio as db
from services.whatsapp_service import enviar_mensaje

logger = logging.getLogger(__name__)

try:
    import fcntl
except ImportError:
    fcntl = None

_lock_file = None  # referencia global: si se cierra, se libera el flock


def _adquirir_lock_unico_worker() -> bool:
    if fcntl is None:
        return True  # sin multi-worker (dev local)

    global _lock_file
    lock_path = os.path.join(os.path.dirname(config.RECORDATORIOS_DB_PATH), "scheduler.lock")
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    _lock_file = open(lock_path, "w")
    try:
        fcntl.flock(_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        _lock_file.close()
        _lock_file = None
        return False


def _revisar_y_enviar():
    ahora_iso = datetime.now(_tz()).isoformat()
    vencidos = db.get_recordatorios_vencidos(ahora_iso)
    for r in vencidos:
        try:
            resp = enviar_mensaje(f"Recordatorio: {r['tarea']}")
            if resp.status_code < 300:
                db.marcar_enviado(r["id"])
            else:
                logger.warning("Fallo al enviar recordatorio #%s: %s", r["id"], resp.text)
        except Exception:
            logger.exception("Error enviando recordatorio #%s", r["id"])


def _tz():
    from zoneinfo import ZoneInfo
    return ZoneInfo(config.RECORDATORIOS_TZ)


def iniciar_scheduler():
    """Arranca el job cada 60s. Debe llamarse una sola vez por proceso (create_app)."""
    if not config.WHATSAPP_TOKEN or not config.WHATSAPP_PHONE_ID or not config.MI_NUMERO:
        logger.info("Recordatorios: faltan credenciales WhatsApp, scheduler no se inicia.")
        return

    if not _adquirir_lock_unico_worker():
        logger.info("Recordatorios: otro worker ya tiene el scheduler activo.")
        return

    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = BackgroundScheduler(timezone=config.RECORDATORIOS_TZ)
    scheduler.add_job(_revisar_y_enviar, "interval", seconds=60, id="recordatorios_check", replace_existing=True)
    scheduler.start()
    logger.info("Recordatorios: scheduler iniciado.")
