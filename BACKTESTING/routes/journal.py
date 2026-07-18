"""
Blueprint: Diario de Trading + Psicología Operativa (registro de operaciones,
métricas automatizadas y alertas de riesgo emocional).

Objetivo principal del módulo de psicología: "No quemar la cuenta" — detectar
a tiempo patrones de operativa impulsiva (rachas de pérdidas + estrés alto +
incumplimiento del plan) y alertar al usuario antes de que escalen.
"""
from flask import Blueprint, render_template, request, jsonify, session

from routes.auth import login_required
from config import DEMO_DB_PATH, PAIR_TICKER_MAP
from models import add_trade, get_all_trades, delete_trade, clear_trades, compute_journal_stats, evaluate_psychological_risk

journal_bp = Blueprint("journal", __name__, url_prefix="/journal")


def _db_path_actual():
    """El perfil DemoUser opera sobre una base de datos aislada (fixtures
    ficticias), nunca sobre los datos reales del usuario."""
    return DEMO_DB_PATH if session.get("is_demo") else None


@journal_bp.route("/", methods=["GET"])
@login_required
def index():
    db_path = _db_path_actual()
    trades = get_all_trades(db_path)
    stats = compute_journal_stats(trades)
    riesgo = evaluate_psychological_risk(trades)
    return render_template(
        "journal.html", trades=trades, stats=stats, riesgo=riesgo,
        pares=sorted(PAIR_TICKER_MAP.keys()),
    )


@journal_bp.route("/add", methods=["POST"])
@login_required
def add():
    payload = request.get_json(silent=True) or {}
    campos_requeridos = ["fecha", "par", "direccion", "entrada", "stop_loss", "take_profit"]
    if not all(payload.get(c) not in (None, "") for c in campos_requeridos):
        return jsonify({"ok": False, "error": "Faltan campos obligatorios."}), 400

    try:
        entrada = float(payload["entrada"])
        precio_salida = payload.get("precio_salida")
        precio_salida = float(precio_salida) if precio_salida not in (None, "") else None

        pnl = None
        resultado = payload.get("resultado") or None
        if precio_salida is not None:
            direccion = payload["direccion"].upper()
            diff = (precio_salida - entrada) if direccion == "LONG" else (entrada - precio_salida)
            pnl = round(diff, 5)
            if resultado is None:
                resultado = "WIN" if pnl > 0 else ("LOSS" if pnl < 0 else "BE")

        nivel_estres = payload.get("nivel_estres")
        nivel_estres = int(nivel_estres) if nivel_estres not in (None, "") else None
        if nivel_estres is not None and not (1 <= nivel_estres <= 5):
            return jsonify({"ok": False, "error": "El nivel de estrés debe estar entre 1 y 5."}), 400

        cumplio_plan_raw = payload.get("cumplio_plan")
        cumplio_plan = None
        if cumplio_plan_raw not in (None, ""):
            cumplio_plan = 1 if str(cumplio_plan_raw) in ("1", "true", "True", "on") else 0

        db_path = _db_path_actual()
        trade_id = add_trade(
            {
                "fecha": payload["fecha"],
                "par": payload["par"],
                "direccion": payload["direccion"].upper(),
                "entrada": entrada,
                "stop_loss": float(payload["stop_loss"]),
                "take_profit": float(payload["take_profit"]),
                "precio_salida": precio_salida,
                "pnl": pnl,
                "resultado": resultado,
                "notas": payload.get("notas", ""),
                "emocion_antes": payload.get("emocion_antes", ""),
                "emocion_durante": payload.get("emocion_durante", ""),
                "emocion_despues": payload.get("emocion_despues", ""),
                "nivel_estres": nivel_estres,
                "cumplio_plan": cumplio_plan,
                "recomendaciones": payload.get("recomendaciones", ""),
            },
            db_path=db_path,
        )
    except (ValueError, TypeError) as e:
        return jsonify({"ok": False, "error": f"Datos numéricos inválidos: {e}"}), 400

    db_path = _db_path_actual()
    trades = get_all_trades(db_path)
    stats = compute_journal_stats(trades)
    riesgo = evaluate_psychological_risk(trades)
    trade_creado = next((t for t in trades if t["id"] == trade_id), None)
    return jsonify({"ok": True, "trade_id": trade_id, "trade": trade_creado, "stats": stats, "riesgo": riesgo})


@journal_bp.route("/delete/<int:trade_id>", methods=["POST"])
@login_required
def delete(trade_id):
    db_path = _db_path_actual()
    delete_trade(trade_id, db_path=db_path)
    trades = get_all_trades(db_path)
    stats = compute_journal_stats(trades)
    riesgo = evaluate_psychological_risk(trades)
    return jsonify({"ok": True, "stats": stats, "riesgo": riesgo})


@journal_bp.route("/clear", methods=["POST"])
@login_required
def clear():
    db_path = _db_path_actual()
    clear_trades(db_path=db_path)
    trades = get_all_trades(db_path)
    stats = compute_journal_stats(trades)
    riesgo = evaluate_psychological_risk(trades)
    return jsonify({"ok": True, "stats": stats, "riesgo": riesgo})


@journal_bp.route("/stats")
@login_required
def stats():
    db_path = _db_path_actual()
    trades = get_all_trades(db_path)
    return jsonify(compute_journal_stats(trades))


@journal_bp.route("/riesgo-psicologico")
@login_required
def riesgo_psicologico():
    db_path = _db_path_actual()
    trades = get_all_trades(db_path)
    return jsonify(evaluate_psychological_risk(trades))
