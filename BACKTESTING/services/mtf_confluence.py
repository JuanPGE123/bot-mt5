"""
Módulo de Análisis de Backtesting Avanzado — Confluencia Multi-Temporal.

Cruza tres escalas de tiempo exactas (Macro, Intermedio, Micro) para producir
"Setups de Alta Probabilidad": puntos de precio donde coinciden niveles de
Fibonacci (retroceso + extensión) de varias temporalidades con zonas reales
de Soporte/Resistencia (no líneas exactas, sino bandas de precio).

Jerarquía de negocio (ver requerimiento): la dirección y estructura de la
temporalidad Macro manda sobre Intermedio y Micro. Intermedio/Micro solo
afinan el punto de entrada dentro de esa dirección ya validada.

Este módulo reutiliza strategy_engine.py como fuente de verdad por
temporalidad individual (SR, impulso, ATR) y añade encima la capa de
cruce/confluencia entre las 3.
"""
from __future__ import annotations

import pandas as pd

from services.strategy_engine import (
    _normalize_columns,
    calculate_atr,
    detect_last_impulse,
    fibonacci_levels,
    find_support_resistance,
    validate_timeframe_or_raise,
)

TIMEFRAMES_MTF = ("macro", "intermedio", "micro")

# Peso jerárquico por temporalidad: Macro decide dirección, Intermedio y
# Micro afinan la entrada. A mayor peso, más relevante es su participación
# en un cluster de confluencia.
PESO_TEMPORALIDAD = {"macro": 3, "intermedio": 2, "micro": 1}

# Extensiones de Fibonacci (objetivos de TP más allá del 100% del impulso).
FIB_EXTENSION_RATIOS = (1.272, 1.618, 2.0)


# ---------------------------------------------------------------------------
# 1) Fibonacci — extensiones (además de los retrocesos ya existentes)
# ---------------------------------------------------------------------------
def fibonacci_extension_levels(high: float, low: float, direction: str):
    """Proyecta niveles más allá del 100% del impulso (objetivos de TP)."""
    rango = high - low
    niveles = []
    for ratio in FIB_EXTENSION_RATIOS:
        if direction == "alcista":
            precio = high + rango * (ratio - 1.0)
        else:
            precio = low - rango * (ratio - 1.0)
        niveles.append({"ratio": ratio, "precio": round(precio, 5), "tipo": "extension"})
    return niveles


# ---------------------------------------------------------------------------
# 2) Análisis por temporalidad individual (Macro / Intermedio / Micro)
# ---------------------------------------------------------------------------
def analyze_timeframe(df: pd.DataFrame, etiqueta: str) -> dict:
    """Ejecuta el análisis cuantitativo base de una temporalidad y lo etiqueta
    con su rol jerárquico (`etiqueta` in TIMEFRAMES_MTF)."""
    df = _normalize_columns(df)
    validate_timeframe_or_raise(df)  # misma regla de negocio: rechaza velas < 1H
    sr = find_support_resistance(df)
    impulso = detect_last_impulse(df)
    retrocesos = fibonacci_levels(impulso["high"], impulso["low"], impulso["direccion"])
    extensiones = fibonacci_extension_levels(impulso["high"], impulso["low"], impulso["direccion"])
    atr = calculate_atr(df)
    precio_actual = round(float(df["Close"].iloc[-1]), 5)

    return {
        "temporalidad": etiqueta,
        "peso": PESO_TEMPORALIDAD[etiqueta],
        "direccion": impulso["direccion"],
        "precio_actual": precio_actual,
        "atr": atr,
        "impulso": impulso,
        "soportes_resistencias": sr,
        "fibonacci_retroceso": retrocesos,
        "fibonacci_extension": extensiones,
    }


# ---------------------------------------------------------------------------
# 3) Zonas (no líneas): todo nivel de precio se trata como una banda con
#    ancho proporcional al ATR de su propia temporalidad. Esto es lo que
#    permite filtrar falsos rompimientos/manipulaciones: una mecha que perfora
#    la línea exacta pero se mantiene dentro de la banda NO rompe la zona.
# ---------------------------------------------------------------------------
def _puntos_de_precio(tf_result: dict) -> list[dict]:
    """Convierte todo lo relevante de una temporalidad (SR + Fibo retroceso
    clave + Fibo extensión) en una lista uniforme de puntos de precio con su
    banda de tolerancia (zona), listos para cruzar contra otras temporalidades."""
    atr = tf_result["atr"] or 0.0001
    ancho_zona = atr * 0.5  # media ATR de la propia temporalidad = ancho de zona
    puntos = []

    for r in tf_result["soportes_resistencias"]["resistencias"]:
        puntos.append({"precio": r["nivel"], "tipo": "resistencia", "origen": "SR", "toques": r["toques"]})
    for s in tf_result["soportes_resistencias"]["soportes"]:
        puntos.append({"precio": s["nivel"], "tipo": "soporte", "origen": "SR", "toques": s["toques"]})
    for f in tf_result["fibonacci_retroceso"]:
        if f["zona_clave"]:
            puntos.append({"precio": f["precio"], "tipo": "fibo_retroceso", "origen": f"Fibo {f['ratio']*100:.1f}%", "toques": None})
    for f in tf_result["fibonacci_extension"]:
        puntos.append({"precio": f["precio"], "tipo": "fibo_extension", "origen": f"Ext {f['ratio']}", "toques": None})

    for p in puntos:
        p["temporalidad"] = tf_result["temporalidad"]
        p["peso"] = tf_result["peso"]
        p["zona_min"] = round(p["precio"] - ancho_zona, 5)
        p["zona_max"] = round(p["precio"] + ancho_zona, 5)
    return puntos


def _se_solapan(a: dict, b: dict) -> bool:
    """Dos zonas de precio se consideran en confluencia si sus bandas se
    solapan (intersección de intervalos), sin importar cuál sea más ancha."""
    return a["zona_min"] <= b["zona_max"] and b["zona_min"] <= a["zona_max"]


# ---------------------------------------------------------------------------
# 4) Clustering de confluencia: agrupa puntos de precio (de cualquier
#    temporalidad/origen) cuyas zonas se solapan entre sí.
# ---------------------------------------------------------------------------
def find_confluence_clusters(puntos: list[dict]) -> list[dict]:
    puntos_ordenados = sorted(puntos, key=lambda p: p["precio"])
    clusters: list[list[dict]] = []

    for p in puntos_ordenados:
        colocado = False
        for cluster in clusters:
            if any(_se_solapan(p, q) for q in cluster):
                cluster.append(p)
                colocado = True
                break
        if not colocado:
            clusters.append([p])

    salida = []
    for cluster in clusters:
        temporalidades_presentes = sorted({p["temporalidad"] for p in cluster}, key=TIMEFRAMES_MTF.index)
        score = sum(PESO_TEMPORALIDAD[tf] for tf in temporalidades_presentes)
        precio_centro = round(sum(p["precio"] for p in cluster) / len(cluster), 5)

        if len(temporalidades_presentes) >= 3:
            nivel = "Alta (Macro + Intermedio + Micro)"
        elif len(temporalidades_presentes) == 2:
            nivel = "Media (2 temporalidades)"
        else:
            nivel = "Baja (1 sola temporalidad)"

        salida.append(
            {
                "precio_centro": precio_centro,
                "zona_min": round(min(p["zona_min"] for p in cluster), 5),
                "zona_max": round(max(p["zona_max"] for p in cluster), 5),
                "temporalidades": temporalidades_presentes,
                "num_temporalidades": len(temporalidades_presentes),
                "score_confluencia": score,
                "nivel_confluencia": nivel,
                "componentes": [
                    {"temporalidad": p["temporalidad"], "tipo": p["tipo"], "origen": p["origen"], "precio": p["precio"]}
                    for p in cluster
                ],
            }
        )

    salida.sort(key=lambda c: (-c["score_confluencia"], -c["num_temporalidades"]))
    return salida


# ---------------------------------------------------------------------------
# 5) Setups de Alta Probabilidad: filtra clusters accionables (>=2
#    temporalidades) y les da forma de operación (entrada/SL/TP), priorizando
#    siempre la dirección de la Macro.
# ---------------------------------------------------------------------------
def build_high_probability_setups(clusters: list[dict], macro: dict, intermedio: dict, micro: dict) -> list[dict]:
    direccion_macro = macro["direccion"]
    precio_actual = micro.get("precio_actual") or intermedio.get("precio_actual") or macro["precio_actual"]
    atr_micro = micro.get("atr") or intermedio.get("atr") or macro["atr"]

    setups = []
    for cluster in clusters:
        if cluster["num_temporalidades"] < 2:
            continue  # requerimiento: solo confluencia real (>=2 temporalidades) es "alta probabilidad"

        tipos = {c["tipo"] for c in cluster["componentes"]}
        es_soporte = "soporte" in tipos
        es_resistencia = "resistencia" in tipos

        # La zona por debajo del precio actual y con Macro alcista => compra;
        # por encima del precio actual y con Macro bajista => venta. La
        # estructura Macro decide qué lado de la zona es operable.
        if direccion_macro == "alcista" and cluster["precio_centro"] <= precio_actual:
            direccion_setup = "COMPRA"
        elif direccion_macro == "bajista" and cluster["precio_centro"] >= precio_actual:
            direccion_setup = "VENTA"
        else:
            continue  # zona en contra de la estructura Macro: se descarta, no es un setup válido

        alternativas = sorted({c["origen"] for c in cluster["componentes"]})

        if direccion_setup == "COMPRA":
            sl = round(cluster["zona_min"] - atr_micro, 5)
            tp = round(cluster["zona_max"] + abs(cluster["zona_max"] - cluster["zona_min"]) * 3 + atr_micro * 3, 5)
        else:
            sl = round(cluster["zona_max"] + atr_micro, 5)
            tp = round(cluster["zona_min"] - abs(cluster["zona_max"] - cluster["zona_min"]) * 3 - atr_micro * 3, 5)

        riesgo = abs(cluster["precio_centro"] - sl)
        beneficio = abs(tp - cluster["precio_centro"])
        rr = round(beneficio / riesgo, 2) if riesgo else 0.0

        setups.append(
            {
                "direccion": direccion_setup,
                "precio_entrada_sugerido": cluster["precio_centro"],
                "zona_entrada": {"min": cluster["zona_min"], "max": cluster["zona_max"]},
                "stop_loss": sl,
                "take_profit": tp,
                "riesgo_beneficio": rr,
                "nivel_confluencia": cluster["nivel_confluencia"],
                "score_confluencia": cluster["score_confluencia"],
                "temporalidades_confluentes": cluster["temporalidades"],
                "alternativas_de_entrada": alternativas,
                "es_zona_sr": es_soporte or es_resistencia,
                "componentes": cluster["componentes"],
            }
        )

    setups.sort(key=lambda s: (-s["score_confluencia"], -s["riesgo_beneficio"]))
    return setups


# ---------------------------------------------------------------------------
# 6) Orquestador: recibe los 3 DataFrames OHLCV (uno por temporalidad) y
#    entrega el dashboard completo ya estructurado (resumen + detalle + setups).
# ---------------------------------------------------------------------------
def run_mtf_analysis(df_macro: pd.DataFrame, df_intermedio: pd.DataFrame, df_micro: pd.DataFrame) -> dict:
    macro = analyze_timeframe(df_macro, "macro")
    intermedio = analyze_timeframe(df_intermedio, "intermedio")
    micro = analyze_timeframe(df_micro, "micro")

    todos_los_puntos = (
        _puntos_de_precio(macro) + _puntos_de_precio(intermedio) + _puntos_de_precio(micro)
    )
    clusters = find_confluence_clusters(todos_los_puntos)
    setups = build_high_probability_setups(clusters, macro, intermedio, micro)

    return {
        # --- Sección 1: Resumen General (jerárquico, dirección manda la Macro) ---
        "resumen_general": {
            "direccion_macro": macro["direccion"],
            "precio_actual": micro["precio_actual"],
            "estructura": {
                "macro": macro["direccion"],
                "intermedio": intermedio["direccion"],
                "micro": micro["direccion"],
            },
            "alineacion_total": macro["direccion"] == intermedio["direccion"] == micro["direccion"],
            "total_setups_alta_probabilidad": len(setups),
            "mejor_setup": setups[0] if setups else None,
        },
        # --- Sección 2: Detalle por temporalidad (Fibonacci + SR + ATR) ---
        "detalle_por_temporalidad": {
            "macro": macro,
            "intermedio": intermedio,
            "micro": micro,
        },
        # --- Sección 3: Confluencia cruda (todos los clusters, no solo setups) ---
        "confluencias": clusters,
        # --- Sección 4: Setups de Alta Probabilidad, listos para operar ---
        "setups_alta_probabilidad": setups,
    }
