"""
Blueprint: Módulo de Extracción de Datos Históricos.
"""
import os

from flask import Blueprint, render_template, request, jsonify, send_file

from config import PAIR_TICKER_MAP, TIMEFRAME_MAP, UPLOAD_CSV_DIR, DEFAULT_MESES_HISTORICO
from routes.auth import login_required
from services.data_fetcher import fetch_historical_data, export_to_csv, DataFetchError

data_bp = Blueprint("data", __name__, url_prefix="/data")


@data_bp.route("/", methods=["GET"])
@login_required
def index():
    return render_template(
        "data_extraction.html",
        pares=sorted(PAIR_TICKER_MAP.keys()),
        temporalidades=list(TIMEFRAME_MAP.keys()),
        meses_default=DEFAULT_MESES_HISTORICO,
    )


@data_bp.route("/fetch", methods=["POST"])
@login_required
def fetch():
    payload = request.get_json(silent=True) or {}
    pair = payload.get("pair")
    timeframe = payload.get("timeframe")
    try:
        meses = int(payload.get("meses") or DEFAULT_MESES_HISTORICO)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "La ventana de meses debe ser un número entero."}), 400

    try:
        df = fetch_historical_data(pair, timeframe, meses=meses)
        filepath = export_to_csv(df, pair, timeframe)
    except DataFetchError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": f"Error inesperado: {e}"}), 500

    preview = df.tail(15).to_dict(orient="records")
    return jsonify(
        {
            "ok": True,
            "filas_totales": len(df),
            "nulos_limpiados": df.attrs.get("nulos_limpiados", 0),
            "ventana_meses": meses,
            "archivo": filepath,
            "vista_previa": preview,
            "columnas": list(df.columns),
        }
    )


@data_bp.route("/download")
@login_required
def download():
    filename = request.args.get("path")
    if not filename:
        return "Ruta de archivo no especificada", 400

    # Solo se permite servir archivos dentro de uploads/csv (evita path traversal)
    filename = os.path.basename(filename)
    filepath = os.path.join(UPLOAD_CSV_DIR, filename)
    if not os.path.isfile(filepath):
        return "Archivo no encontrado", 404
    return send_file(filepath, as_attachment=True)
