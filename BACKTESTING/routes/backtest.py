"""
Blueprint: Módulo de Backtesting y Análisis de Scalping.
Recibe el CSV histórico + hasta 2 imágenes del estado del mercado,
ejecuta el motor de estrategia (S/R, Fibonacci, ATR, etc.) y el análisis
de visión por computadora sobre las imágenes.
"""
import os
import uuid

import pandas as pd
from flask import Blueprint, render_template, request, jsonify, session
from werkzeug.utils import secure_filename

from config import UPLOAD_CSV_DIR, UPLOAD_IMG_DIR, ALLOWED_CSV_EXT, ALLOWED_IMG_EXT, DEMO_FIXTURES_DIR, PAIR_TICKER_MAP
from routes.auth import login_required
from services.strategy_engine import run_full_analysis
from services.image_analyzer import analyze_chart_image, evaluate_multi_timeframe, TIMEFRAMES_VISUALES
from services.mtf_confluence import run_mtf_analysis, TIMEFRAMES_MTF

backtest_bp = Blueprint("backtest", __name__, url_prefix="/backtest")

# Campos de formulario esperados para el análisis multi-temporal (Macro/Intermedia/Micro)
IMAGE_FIELDS = {tf: f"image_{tf}" for tf in TIMEFRAMES_VISUALES}

# Fixtures del perfil DemoUser (Punto 4): CSV + 3 imágenes de ejemplo,
# generadas una única vez y versionadas en fixtures/demo/.
DEMO_CSV = os.path.join(DEMO_FIXTURES_DIR, "demo_EURUSD_1h.csv")
DEMO_IMAGES = {
    "macro": os.path.join(DEMO_FIXTURES_DIR, "demo_macro.png"),
    "intermedia": os.path.join(DEMO_FIXTURES_DIR, "demo_intermedia.png"),
    "micro": os.path.join(DEMO_FIXTURES_DIR, "demo_micro.png"),
}


def _allowed(filename, allowed_ext):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_ext


def _analizar(csv_path: str, imagenes_por_tf: dict):
    """Lógica común de análisis (CSV + hasta 3 imágenes), reutilizada por
    /run (uploads reales) y /run-demo (fixtures del perfil DemoUser)."""
    df = pd.read_csv(csv_path)
    analisis = run_full_analysis(df)

    analisis_imagenes = {}
    for tf in TIMEFRAMES_VISUALES:
        path = imagenes_por_tf.get(tf)
        if path:
            try:
                resultado_img = analyze_chart_image(path)
                resultado_img["archivo"] = os.path.basename(path)
                resultado_img["temporalidad"] = tf
                analisis_imagenes[tf] = resultado_img
            except Exception as e:
                analisis_imagenes[tf] = {"archivo": os.path.basename(path), "temporalidad": tf, "error": str(e)}
        else:
            analisis_imagenes[tf] = None

    confluencia = evaluate_multi_timeframe(
        analisis_imagenes, direccion_csv=analisis["ultimo_impulso"]["direccion"]
    )
    return {
        "ok": True,
        "analisis": analisis,
        "analisis_imagenes": analisis_imagenes,
        "confluencia_multitemporal": confluencia,
    }


@backtest_bp.route("/", methods=["GET"])
@login_required
def index():
    return render_template(
        "backtest.html", is_demo=session.get("is_demo", False),
        pares=sorted(PAIR_TICKER_MAP.keys()),
    )


@backtest_bp.route("/run", methods=["POST"])
@login_required
def run():
    if "csv_file" not in request.files:
        return jsonify({"ok": False, "error": "Debes subir el archivo CSV histórico."}), 400

    csv_file = request.files["csv_file"]
    if csv_file.filename == "" or not _allowed(csv_file.filename, ALLOWED_CSV_EXT):
        return jsonify({"ok": False, "error": "Archivo CSV inválido."}), 400

    os.makedirs(UPLOAD_CSV_DIR, exist_ok=True)
    os.makedirs(UPLOAD_IMG_DIR, exist_ok=True)

    csv_name = f"{uuid.uuid4().hex}_{secure_filename(csv_file.filename)}"
    csv_path = os.path.join(UPLOAD_CSV_DIR, csv_name)
    csv_file.save(csv_path)

    # --- Análisis Multi-Temporal: guarda hasta 3 imágenes (Macro/Intermedia/Micro) ---
    imagenes_por_tf = {}
    for tf, campo in IMAGE_FIELDS.items():
        img_file = request.files.get(campo)
        if img_file and img_file.filename and _allowed(img_file.filename, ALLOWED_IMG_EXT):
            img_name = f"{uuid.uuid4().hex}_{secure_filename(img_file.filename)}"
            img_path = os.path.join(UPLOAD_IMG_DIR, img_name)
            img_file.save(img_path)
            imagenes_por_tf[tf] = img_path

    try:
        resultado = _analizar(csv_path, imagenes_por_tf)
    except ValueError as e:
        # Validación estricta de datos (temporalidad < 1H, columnas faltantes, etc.)
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": f"Error procesando el CSV: {e}"}), 400

    return jsonify(resultado)


@backtest_bp.route("/run-mtf", methods=["POST"])
@login_required
def run_mtf():
    """
    Módulo de Análisis de Backtesting Avanzado: recibe 3 CSV históricos, uno
    por cada temporalidad exacta (Macro, Intermedio, Micro), y devuelve el
    dashboard de confluencia (Fibonacci + zonas SR cruzadas) con los Setups
    de Alta Probabilidad ya calculados.
    """
    csv_paths = {}
    try:
        os.makedirs(UPLOAD_CSV_DIR, exist_ok=True)
        for tf in TIMEFRAMES_MTF:
            campo = f"csv_{tf}"
            if campo not in request.files or request.files[campo].filename == "":
                return jsonify({"ok": False, "error": f"Falta el CSV de la temporalidad '{tf}'."}), 400

            csv_file = request.files[campo]
            if not _allowed(csv_file.filename, ALLOWED_CSV_EXT):
                return jsonify({"ok": False, "error": f"Archivo CSV inválido para '{tf}'."}), 400

            csv_name = f"{uuid.uuid4().hex}_{secure_filename(csv_file.filename)}"
            csv_path = os.path.join(UPLOAD_CSV_DIR, csv_name)
            csv_file.save(csv_path)
            csv_paths[tf] = csv_path

        dfs = {tf: pd.read_csv(path) for tf, path in csv_paths.items()}
        resultado = run_mtf_analysis(dfs["macro"], dfs["intermedio"], dfs["micro"])
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": f"Error procesando el análisis multi-temporal: {e}"}), 400

    return jsonify({"ok": True, "mtf": resultado})


@backtest_bp.route("/run-demo", methods=["POST"])
@login_required
def run_demo():
    """
    Backtest pre-cargado del perfil DemoUser/Showcase (Punto 4): reutiliza el
    mismo motor de análisis (`_analizar`) sobre datos y capturas ficticias
    versionadas en fixtures/demo/, sin necesidad de subir archivos.
    """
    if not os.path.isfile(DEMO_CSV):
        return jsonify({"ok": False, "error": "Fixtures de demo no encontradas en el servidor."}), 500
    try:
        resultado = _analizar(DEMO_CSV, DEMO_IMAGES)
    except Exception as e:
        return jsonify({"ok": False, "error": f"Error ejecutando el backtest de ejemplo: {e}"}), 500
    return jsonify(resultado)
