"""
Blueprint: Entradas — oportunidades de compra/venta (o pendientes) generadas
manualmente o a partir del análisis del módulo de Backtesting y Análisis de
Scalping. Objetivo: traducir el análisis en una lista concreta y accionable
de setups de entrada al mercado.
"""
from flask import Blueprint, render_template, request, jsonify, session

from routes.auth import login_required
from config import DEMO_DB_PATH, PAIR_TICKER_MAP
from models import add_entrada, get_all_entradas, delete_entrada, clear_entradas

entradas_bp = Blueprint("entradas", __name__, url_prefix="/entradas")

TIPOS_ORDEN = [
    "Compra a Mercado", "Venta a Mercado",
    "Buy Limit", "Sell Limit", "Buy Stop", "Sell Stop",
]


def _db_path_actual():
    return DEMO_DB_PATH if session.get("is_demo") else None


@entradas_bp.route("/", methods=["GET"])
@login_required
def index():
    db_path = _db_path_actual()
    entradas = get_all_entradas(db_path)
    return render_template(
        "entradas.html",
        entradas=entradas,
        pares=sorted(PAIR_TICKER_MAP.keys()),
        tipos_orden=TIPOS_ORDEN,
    )


@entradas_bp.route("/add", methods=["POST"])
@login_required
def add():
    payload = request.get_json(silent=True) or {}
    campos_requeridos = ["par", "direccion", "tipo_orden", "precio_entrada", "stop_loss", "take_profit"]
    if not all(payload.get(c) not in (None, "") for c in campos_requeridos):
        return jsonify({"ok": False, "error": "Faltan campos obligatorios."}), 400

    try:
        db_path = _db_path_actual()
        entrada_id = add_entrada(
            {
                "par": str(payload["par"]).upper(),
                "direccion": payload["direccion"].upper(),
                "tipo_orden": payload["tipo_orden"],
                "precio_entrada": float(payload["precio_entrada"]),
                "stop_loss": float(payload["stop_loss"]),
                "take_profit": float(payload["take_profit"]),
                "riesgo_beneficio": float(payload["riesgo_beneficio"]) if payload.get("riesgo_beneficio") not in (None, "") else None,
                "temporalidad": payload.get("temporalidad", ""),
                "motivo": payload.get("motivo", ""),
                "origen": payload.get("origen", "manual"),
            },
            db_path=db_path,
        )
    except (ValueError, TypeError) as e:
        return jsonify({"ok": False, "error": f"Datos numéricos inválidos: {e}"}), 400

    return jsonify({"ok": True, "entrada_id": entrada_id})


@entradas_bp.route("/delete/<int:entrada_id>", methods=["POST"])
@login_required
def delete(entrada_id):
    db_path = _db_path_actual()
    delete_entrada(entrada_id, db_path=db_path)
    return jsonify({"ok": True})


@entradas_bp.route("/clear", methods=["POST"])
@login_required
def clear():
    db_path = _db_path_actual()
    clear_entradas(db_path=db_path)
    return jsonify({"ok": True})
