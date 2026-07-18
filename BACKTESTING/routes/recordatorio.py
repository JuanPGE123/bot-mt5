"""
Blueprint: Recordatorios por WhatsApp (Meta Cloud API).

- GET/POST /webhook  -> integración Meta (verificación + mensajes entrantes).
- GET /health         -> health check de Fly.io.
- GET /recordatorio/  -> panel web de solo lectura, visible únicamente para
  AUTH_USERNAME (oculto al perfil DemoUser).
"""
from datetime import datetime

from flask import Blueprint, request, jsonify, session, render_template, abort

import config
import models_recordatorio as db
from routes.auth import login_required
from services.whatsapp_service import procesar_mensaje, enviar_mensaje

recordatorio_bp = Blueprint("recordatorio", __name__)


def _solo_yo(view_func):
    """Bloquea el panel web al perfil DemoUser: módulo estrictamente personal."""
    from functools import wraps

    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if session.get("is_demo"):
            abort(403)
        return view_func(*args, **kwargs)
    return wrapped


@recordatorio_bp.route("/webhook", methods=["GET"])
def webhook_verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge", "")
    if mode == "subscribe" and token == config.VERIFY_TOKEN:
        return challenge, 200
    return "Forbidden", 403


@recordatorio_bp.route("/webhook", methods=["POST"])
def webhook_receive():
    data = request.get_json(silent=True) or {}
    try:
        entry = data["entry"][0]
        cambio = entry["changes"][0]["value"]
        mensajes = cambio.get("messages", [])
    except (KeyError, IndexError):
        return jsonify({"ok": True}), 200  # eventos que no son mensajes (status, etc.)

    for msg in mensajes:
        numero = msg.get("from", "")
        texto = (msg.get("text") or {}).get("body", "")
        if not texto:
            continue
        respuesta = procesar_mensaje(numero, texto)
        if respuesta:
            enviar_mensaje(respuesta, numero=numero)

    return jsonify({"ok": True}), 200


@recordatorio_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@recordatorio_bp.route("/recordatorio/", methods=["GET"])
@login_required
@_solo_yo
def index():
    items = db.get_todos()
    ahora = datetime.now().isoformat()
    return render_template("recordatorio.html", items=items, ahora=ahora)


@recordatorio_bp.route("/recordatorio/delete/<int:recordatorio_id>", methods=["POST"])
@login_required
@_solo_yo
def delete(recordatorio_id):
    ok = db.delete_recordatorio(recordatorio_id)
    return jsonify({"ok": ok})
