"""
Motor de Backtesting y Análisis de Scalping.

Estrategia estricta basada en:
  a) Zonas de Soporte y Resistencia (pivotes locales).
  b) Retrocesos de Fibonacci del último impulso, con foco en 50% y 61.8%.
  c) Análisis del precio máximo/mínimo de velas de 1 día.

Además calcula estadísticas de utilidad para scalping: ATR, volatilidad
por sesión y win-rate histórico de reacción en niveles Fibonacci.
"""
import numpy as np
import pandas as pd

FIB_RATIOS = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]

# Umbral mínimo de temporalidad aceptado por el backtester (en minutos).
# Requerimiento del negocio: cualquier CSV con velas de menos de 1 hora
# (scalping ultra-intradía tipo 1m/5m/15m/30m) no es válido para este
# backtesting, ya que el motor está calibrado para operar sobre estructura
# de 1H en adelante (evita ruido/whipsaw de temporalidades muy bajas).
MIN_MINUTOS_VELA_VALIDA = 60

# Clasificación relativa de temporalidad usada para decidir si se ejecuta el
# análisis de zonas de reversión + Fibonacci + patrones de velas + trampas de
# liquidez (solo aplica a "intermedia" y "micro"; "macro" se deja solo como
# contexto de tendencia general, sin sugerir entradas puntuales).
def clasificar_temporalidad(minutos_por_vela: float) -> str:
    if minutos_por_vela < MIN_MINUTOS_VELA_VALIDA:
        return "invalida"
    if minutos_por_vela < 240:  # 1H (posible 1h-3h)
        return "micro"
    if minutos_por_vela < 1440:  # 4H-hasta 1D
        return "intermedia"
    return "macro"  # 1D, 1W...


def infer_minutos_por_vela(df: pd.DataFrame) -> float:
    """Infiere el tamaño de vela (en minutos) a partir de la mediana de
    diferencias entre timestamps consecutivos. Robusto ante huecos de fin de
    semana/festivos en forex, ya que usa la mediana (no el promedio)."""
    if "Datetime" not in df.columns or len(df) < 3:
        raise ValueError(
            "El CSV no tiene columna de fecha/hora (Datetime) válida; "
            "no es posible determinar su temporalidad."
        )
    diffs = df["Datetime"].diff().dropna().dt.total_seconds() / 60.0
    diffs = diffs[diffs > 0]
    if diffs.empty:
        raise ValueError("No fue posible inferir la temporalidad del CSV (timestamps inválidos o duplicados).")
    return float(diffs.median())


def validate_timeframe_or_raise(df: pd.DataFrame) -> dict:
    """
    Validación estricta de datos (requerimiento del negocio):
    rechaza cualquier CSV cuya temporalidad de vela sea menor a 1 Hora
    (por ejemplo 1m, 5m, 15m, 30m), ya que no tiene validez para este
    backtesting de scalping estructural. Lanza ValueError con un mensaje
    claro y accionable para el usuario si la validación falla.
    """
    minutos = infer_minutos_por_vela(df)
    etiqueta = clasificar_temporalidad(minutos)
    if etiqueta == "invalida":
        raise ValueError(
            f"CSV rechazado: la temporalidad detectada es de ~{minutos:.0f} minuto(s) por vela, "
            f"menor a 1 Hora (60 min). Este backtesting solo acepta datos de 1H en adelante "
            f"(1H, 4H, 1D, 1W). Vuelve a exportar el histórico en una temporalidad de 1 Hora o superior."
        )
    return {"minutos_por_vela": round(minutos, 2), "clasificacion": etiqueta}


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza nombres de columnas típicos de un CSV OHLCV a formato estándar."""
    rename_map = {}
    for col in df.columns:
        key = str(col).strip().lower()
        if key in ("date", "datetime", "time", "fecha"):
            rename_map[col] = "Datetime"
        elif key in ("open", "apertura"):
            rename_map[col] = "Open"
        elif key in ("high", "maximo", "máximo"):
            rename_map[col] = "High"
        elif key in ("low", "minimo", "mínimo"):
            rename_map[col] = "Low"
        elif key in ("close", "cierre"):
            rename_map[col] = "Close"
        elif key == "adj close" and "close" not in [str(c).strip().lower() for c in df.columns]:
            rename_map[col] = "Close"
        elif key in ("volume", "volumen"):
            rename_map[col] = "Volume"
    df = df.rename(columns=rename_map)
    required = {"Open", "High", "Low", "Close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"El CSV no contiene las columnas requeridas: {missing}")
    if "Datetime" in df.columns:
        # utc=True evita el error "Mixed timezones detected" cuando el CSV
        # mezcla timestamps con distinto offset (o algunos con tz y otros
        # sin ella, típico al exportar de distintas plataformas/brokers).
        # Luego se descarta la tz y se deja naive en UTC para que el resto
        # del motor (resample 1D, hora UTC de sesión, etc.) opere consistente.
        df["Datetime"] = pd.to_datetime(df["Datetime"], errors="coerce", utc=True).dt.tz_localize(None)
        df = df.dropna(subset=["Datetime"]).sort_values("Datetime").reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# a) Soportes y Resistencias
# ---------------------------------------------------------------------------
def find_support_resistance(df: pd.DataFrame, window: int = 5, tolerance_pct: float = 0.05):
    """
    Detecta zonas de soporte/resistencia agrupando pivotes locales
    (máximos y mínimos que son extremos dentro de una ventana `window`).
    `tolerance_pct` agrupa niveles cercanos entre sí como una misma zona.
    """
    highs = df["High"].values
    lows = df["Low"].values
    n = len(df)

    pivot_highs, pivot_lows = [], []
    for i in range(window, n - window):
        if highs[i] == max(highs[i - window: i + window + 1]):
            pivot_highs.append(highs[i])
        if lows[i] == min(lows[i - window: i + window + 1]):
            pivot_lows.append(lows[i])

    def cluster(levels):
        if not levels:
            return []
        levels = sorted(levels)
        clusters = [[levels[0]]]
        for lvl in levels[1:]:
            last = clusters[-1][-1]
            if abs(lvl - last) / last * 100 <= tolerance_pct * 100:
                clusters[-1].append(lvl)
            else:
                clusters.append([lvl])
        # cada cluster se representa por su promedio, con "fuerza" = nro. de toques
        return [
            {"nivel": round(float(np.mean(c)), 5), "toques": len(c)}
            for c in clusters
        ]

    resistencias = sorted(cluster(pivot_highs), key=lambda x: -x["toques"])[:8]
    soportes = sorted(cluster(pivot_lows), key=lambda x: -x["toques"])[:8]
    return {"soportes": soportes, "resistencias": resistencias}


# ---------------------------------------------------------------------------
# b) Fibonacci del último impulso
# ---------------------------------------------------------------------------
def detect_last_impulse(df: pd.DataFrame, lookback: int = 100):
    """
    Identifica el último impulso (tramo alcista o bajista) usando el
    máximo y mínimo absoluto dentro de la ventana de `lookback` velas,
    determinando la dirección según cuál extremo ocurrió más recientemente.
    """
    sub = df.tail(lookback).reset_index(drop=True)
    idx_high = sub["High"].idxmax()
    idx_low = sub["Low"].idxmin()

    high_val = float(sub.loc[idx_high, "High"])
    low_val = float(sub.loc[idx_low, "Low"])

    # Si el mínimo ocurrió después del máximo -> impulso bajista (High -> Low)
    # Si el máximo ocurrió después del mínimo -> impulso alcista (Low -> High)
    direccion = "bajista" if idx_low > idx_high else "alcista"

    # Punto A = origen del impulso, Punto B = fin del impulso. Son los dos
    # puntos exactos desde donde se debe trazar la herramienta Fibonacci en
    # la plataforma de trading (arrastrar de A a B) para proyectar los
    # niveles de retroceso y buscar entradas en la zona 50%/61.8%.
    if direccion == "alcista":
        punto_a = {"tipo": "low", "precio": low_val, "idx": int(idx_low)}
        punto_b = {"tipo": "high", "precio": high_val, "idx": int(idx_high)}
    else:
        punto_a = {"tipo": "high", "precio": high_val, "idx": int(idx_high)}
        punto_b = {"tipo": "low", "precio": low_val, "idx": int(idx_low)}

    if "Datetime" in sub.columns:
        punto_a["fecha"] = str(sub.loc[punto_a["idx"], "Datetime"])
        punto_b["fecha"] = str(sub.loc[punto_b["idx"], "Datetime"])

    return {
        "direccion": direccion,
        "high": high_val,
        "low": low_val,
        "idx_high": int(idx_high),
        "idx_low": int(idx_low),
        "punto_A": punto_a,
        "punto_B": punto_b,
    }


def fibonacci_levels(high: float, low: float, direction: str):
    """
    Calcula niveles de retroceso de Fibonacci del impulso.
    - direction == 'alcista': retrocesos se miden desde High hacia Low.
    - direction == 'bajista': retrocesos se miden desde Low hacia High.
    Devuelve todos los niveles estándar, resaltando 50% y 61.8% (zona clave).
    """
    rango = high - low
    niveles = []
    for ratio in FIB_RATIOS:
        if direction == "alcista":
            precio = high - rango * ratio
        else:
            precio = low + rango * ratio
        niveles.append(
            {
                "ratio": ratio,
                "precio": round(precio, 5),
                "zona_clave": ratio in (0.5, 0.618),
            }
        )
    return niveles


# ---------------------------------------------------------------------------
# c) Análisis de velas diarias (máximos/mínimos de 1D)
# ---------------------------------------------------------------------------
def daily_high_low_analysis(df: pd.DataFrame):
    """Resamplea la data a velas de 1 día y extrae estadísticas de máximos/mínimos."""
    if "Datetime" not in df.columns:
        return {"error": "El dataset no tiene columna de fecha/hora para resamplear a 1D."}

    daily = (
        df.set_index("Datetime")
        .resample("1D")
        .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"})
        .dropna()
    )
    if daily.empty:
        return {"error": "No hay suficientes datos para calcular velas diarias."}

    daily["rango"] = daily["High"] - daily["Low"]

    return {
        "max_precio_historico": round(float(daily["High"].max()), 5),
        "min_precio_historico": round(float(daily["Low"].min()), 5),
        "rango_diario_promedio": round(float(daily["rango"].mean()), 5),
        "rango_diario_max": round(float(daily["rango"].max()), 5),
        "ultima_vela_1d": {
            "fecha": str(daily.index[-1].date()),
            "open": round(float(daily["Open"].iloc[-1]), 5),
            "high": round(float(daily["High"].iloc[-1]), 5),
            "low": round(float(daily["Low"].iloc[-1]), 5),
            "close": round(float(daily["Close"].iloc[-1]), 5),
        },
    }


# ---------------------------------------------------------------------------
# Estadísticas para scalping
# ---------------------------------------------------------------------------
def calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
    """Average True Range clásico, útil para dimensionar SL/TP en scalping."""
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return round(float(atr.iloc[-1]), 5) if not atr.empty and not np.isnan(atr.iloc[-1]) else 0.0


def session_volatility(df: pd.DataFrame):
    """
    Calcula la volatilidad (desviación estándar de retornos) agrupada por hora
    del día, para identificar la sesión más volátil (Asia/Londres/NY) y
    priorizar horarios de scalping.
    """
    if "Datetime" not in df.columns:
        return {"error": "El dataset no tiene columna de fecha/hora."}

    tmp = df.copy()
    tmp["retorno"] = tmp["Close"].pct_change()
    tmp["hora"] = tmp["Datetime"].dt.hour
    vol_por_hora = tmp.groupby("hora")["retorno"].std().dropna()

    if vol_por_hora.empty:
        return {"error": "No hay suficiente granularidad temporal para calcular volatilidad por sesión."}

    hora_mas_volatil = int(vol_por_hora.idxmax())

    def clasificar_sesion(h):
        if 0 <= h < 8:
            return "Asia"
        if 8 <= h < 13:
            return "Londres"
        if 13 <= h < 17:
            return "Solape Londres-NY"
        if 17 <= h < 22:
            return "Nueva York"
        return "Cierre/Post-mercado"

    return {
        "hora_mas_volatil_utc": hora_mas_volatil,
        "sesion_mas_volatil": clasificar_sesion(hora_mas_volatil),
        "volatilidad_por_hora": {
            str(h): round(float(v), 6) for h, v in vol_por_hora.items()
        },
    }


def fib_level_winrate(df: pd.DataFrame, tolerance_pct: float = 0.1, lookahead: int = 10,
                       reaction_pct: float = 0.3):
    """
    Backtest simplificado de win-rate para los niveles Fibonacci 50% y 61.8%:
    para cada impulso detectado en ventanas móviles, evalúa si el precio,
    al tocar la zona 50%/61.8%, reacciona en la dirección esperada al menos
    `reaction_pct`% dentro de las siguientes `lookahead` velas.
    """
    resultados = {"50.0": {"toques": 0, "aciertos": 0}, "61.8": {"toques": 0, "aciertos": 0}}
    n = len(df)
    step = max(20, lookahead)

    for start in range(0, n - step, step):
        window = df.iloc[start:start + step]
        if len(window) < 5:
            continue
        impulso = detect_last_impulse(window, lookback=len(window))
        niveles = fibonacci_levels(impulso["high"], impulso["low"], impulso["direccion"])

        for nivel in niveles:
            if nivel["ratio"] not in (0.5, 0.618):
                continue
            key = "50.0" if nivel["ratio"] == 0.5 else "61.8"
            precio_nivel = nivel["precio"]
            tol = precio_nivel * (tolerance_pct / 100)

            # Buscar velas posteriores al impulso que toquen el nivel
            resto = df.iloc[start + step:start + step + 50]
            for i in range(len(resto) - lookahead):
                vela = resto.iloc[i]
                if vela["Low"] - tol <= precio_nivel <= vela["High"] + tol:
                    resultados[key]["toques"] += 1
                    futuro = resto.iloc[i + 1: i + 1 + lookahead]
                    if futuro.empty:
                        continue
                    if impulso["direccion"] == "alcista":
                        objetivo = precio_nivel * (1 + reaction_pct / 100)
                        acierto = (futuro["High"] >= objetivo).any()
                    else:
                        objetivo = precio_nivel * (1 - reaction_pct / 100)
                        acierto = (futuro["Low"] <= objetivo).any()
                    if acierto:
                        resultados[key]["aciertos"] += 1
                    break  # solo el primer toque por ventana

    salida = {}
    for key, val in resultados.items():
        toques = val["toques"]
        salida[key] = {
            "toques": toques,
            "aciertos": val["aciertos"],
            "win_rate": round((val["aciertos"] / toques) * 100, 2) if toques else 0.0,
        }
    return salida


# ---------------------------------------------------------------------------
# Sugerencia de TP / SL
# ---------------------------------------------------------------------------
def suggest_tp_sl(df: pd.DataFrame, direction: str, sr: dict, fib_levels: list, atr: float):
    """
    Sugiere TP/SL combinando:
      - Nivel Fibonacci clave (50%/61.8%) más cercano como referencia de entrada.
      - Soporte/Resistencia más próximo como objetivo de TP.
      - ATR como colchón mínimo de seguridad para el SL.
    """
    precio_actual = float(df["Close"].iloc[-1])

    zona_entrada = min(
        [n for n in fib_levels if n["zona_clave"]],
        key=lambda n: abs(n["precio"] - precio_actual),
    )

    if direction == "alcista":
        candidatos_tp = [r["nivel"] for r in sr["resistencias"] if r["nivel"] > precio_actual]
        candidatos_sl = [s["nivel"] for s in sr["soportes"] if s["nivel"] < precio_actual]
        tp = min(candidatos_tp) if candidatos_tp else round(precio_actual + atr * 3, 5)
        sl_base = max(candidatos_sl) if candidatos_sl else round(precio_actual - atr * 1.5, 5)
        sl = min(sl_base, round(precio_actual - atr, 5))
    else:
        candidatos_tp = [s["nivel"] for s in sr["soportes"] if s["nivel"] < precio_actual]
        candidatos_sl = [r["nivel"] for r in sr["resistencias"] if r["nivel"] > precio_actual]
        tp = max(candidatos_tp) if candidatos_tp else round(precio_actual - atr * 3, 5)
        sl_base = min(candidatos_sl) if candidatos_sl else round(precio_actual + atr * 1.5, 5)
        sl = max(sl_base, round(precio_actual + atr, 5))

    riesgo = abs(precio_actual - sl)
    beneficio = abs(tp - precio_actual)
    rr = round(beneficio / riesgo, 2) if riesgo else 0.0

    return {
        "precio_actual": round(precio_actual, 5),
        "zona_entrada_fibo": zona_entrada,
        "take_profit": round(tp, 5),
        "stop_loss": round(sl, 5),
        "riesgo_beneficio": rr,
    }


# ---------------------------------------------------------------------------
# Sugerencia de tipo de orden (mercado / limit / stop)
# ---------------------------------------------------------------------------
def suggest_order_type(direction: str, precio_actual: float, zona_entrada: dict, atr: float, trampas: list = None) -> dict:
    """
    Traduce el análisis (zona Fibo clave + ATR + trampas de liquidez) en un
    tipo de orden ejecutable, tal como lo decidiría un trader manual:
      - Mercado: el precio ya está dentro de la zona clave (o hubo una
        trampa de liquidez reciente que confirma la reversión ya).
      - Limit (Buy/Sell Limit): el precio se alejó de la zona en sentido
        contrario a la tendencia -> se espera el retroceso hacia la zona.
      - Stop (Buy/Sell Stop): el precio ya superó la zona en el sentido de
        la tendencia sin retroceder -> se espera ruptura confirmada.
    """
    trampas = trampas or []
    precio_zona = zona_entrada["precio"]
    tolerancia = atr * 0.3
    distancia = precio_actual - precio_zona
    en_zona = abs(distancia) <= tolerancia
    trampa_reciente = any(t["idx"] <= 3 for t in trampas)

    if en_zona or trampa_reciente:
        tipo_orden = "Compra a Mercado" if direction == "alcista" else "Venta a Mercado"
        precio_entrada = round(precio_actual, 5)
        motivo = (
            "Precio ya está dentro de la zona Fibo clave"
            if en_zona
            else "Trampa de liquidez reciente confirma reversión: entrar ya, sin esperar retroceso"
        )
    elif (direction == "alcista" and distancia > 0) or (direction == "bajista" and distancia < 0):
        tipo_orden = "Buy Limit" if direction == "alcista" else "Sell Limit"
        precio_entrada = round(precio_zona, 5)
        motivo = f"Precio se alejó de la zona clave; colocar {tipo_orden} para esperar el retroceso"
    else:
        tipo_orden = "Buy Stop" if direction == "alcista" else "Sell Stop"
        precio_entrada = (
            round(precio_actual + atr * 0.5, 5) if direction == "alcista" else round(precio_actual - atr * 0.5, 5)
        )
        motivo = f"Precio superó la zona clave sin retroceso; colocar {tipo_orden} para confirmar ruptura"

    return {
        "tipo_orden": tipo_orden,
        "precio_entrada_sugerido": precio_entrada,
        "en_zona_actualmente": en_zona,
        "motivo": motivo,
    }


# ---------------------------------------------------------------------------
# Patrones de velas (reversión / continuidad) — "frescos" = solo velas recientes
# ---------------------------------------------------------------------------
def detect_candle_patterns(df: pd.DataFrame, n_recientes: int = 30):
    """
    Recorre las últimas `n_recientes` velas e identifica los principales
    patrones de reversión y de continuidad. Se limita a velas recientes para
    mantener las señales "frescas" (un patrón de hace 500 velas ya no es
    accionable). Cada patrón detectado incluye índice/fecha para poder
    ubicarlo en el gráfico.
    """
    sub = df.tail(n_recientes).reset_index(drop=True)
    n = len(sub)
    patrones = []

    def cuerpo(v):
        return abs(v["Close"] - v["Open"])

    def rango(v):
        return v["High"] - v["Low"] if v["High"] != v["Low"] else 1e-9

    def mecha_superior(v):
        return v["High"] - max(v["Open"], v["Close"])

    def mecha_inferior(v):
        return min(v["Open"], v["Close"]) - v["Low"]

    def alcista(v):
        return v["Close"] > v["Open"]

    def registrar(idx, nombre, tipo, direccion):
        item = {"idx": int(idx), "patron": nombre, "tipo": tipo, "direccion": direccion}
        if "Datetime" in sub.columns:
            item["fecha"] = str(sub.loc[idx, "Datetime"])
        patrones.append(item)

    for i in range(n):
        v = sub.iloc[i]
        c = cuerpo(v)
        r = rango(v)

        # Doji: cuerpo ínfimo relativo al rango -> indecisión (posible reversión en zona clave)
        if c <= r * 0.1:
            registrar(i, "Doji", "reversion_potencial", "indefinida")

        # Martillo (hammer) / Estrella fugaz (shooting star) según posición de la mecha larga
        if mecha_inferior(v) >= c * 2 and mecha_superior(v) <= c * 0.5:
            registrar(i, "Martillo (Hammer)", "reversion", "alcista")
        if mecha_superior(v) >= c * 2 and mecha_inferior(v) <= c * 0.5:
            registrar(i, "Estrella Fugaz (Shooting Star)", "reversion", "bajista")

        if i == 0:
            continue
        prev = sub.iloc[i - 1]

        # Envolvente alcista/bajista (engulfing)
        if alcista(v) and not alcista(prev) and v["Close"] >= prev["Open"] and v["Open"] <= prev["Close"]:
            registrar(i, "Envolvente Alcista (Bullish Engulfing)", "reversion", "alcista")
        if (not alcista(v)) and alcista(prev) and v["Open"] >= prev["Close"] and v["Close"] <= prev["Open"]:
            registrar(i, "Envolvente Bajista (Bearish Engulfing)", "reversion", "bajista")

        # Inside bar (vela interior): continuidad/consolidación dentro del rango previo
        if v["High"] <= prev["High"] and v["Low"] >= prev["Low"]:
            registrar(i, "Vela Interior (Inside Bar)", "continuidad", "indefinida")

        if i < 2:
            continue
        prev2 = sub.iloc[i - 2]

        # Estrella de la mañana (morning star): bajista, indecisión pequeña, alcista fuerte
        if (
            not alcista(prev2) and cuerpo(prev2) > r * 0.5
            and cuerpo(prev) <= r * 0.3
            and alcista(v) and v["Close"] >= (prev2["Open"] + prev2["Close"]) / 2
        ):
            registrar(i, "Estrella de la Mañana (Morning Star)", "reversion", "alcista")

        # Estrella de la tarde (evening star): alcista, indecisión pequeña, bajista fuerte
        if (
            alcista(prev2) and cuerpo(prev2) > r * 0.5
            and cuerpo(prev) <= r * 0.3
            and (not alcista(v)) and v["Close"] <= (prev2["Open"] + prev2["Close"]) / 2
        ):
            registrar(i, "Estrella de la Tarde (Evening Star)", "reversion", "bajista")

        # Tres Soldados Blancos / Tres Cuervos Negros (continuidad de tendencia fuerte)
        tres = [prev2, prev, v]
        if all(alcista(x) for x in tres) and all(
            tres[k]["Close"] > tres[k - 1]["Close"] for k in (1, 2)
        ):
            registrar(i, "Tres Soldados Blancos", "continuidad", "alcista")
        if all(not alcista(x) for x in tres) and all(
            tres[k]["Close"] < tres[k - 1]["Close"] for k in (1, 2)
        ):
            registrar(i, "Tres Cuervos Negros", "continuidad", "bajista")

    # Los más recientes primero (más relevantes para decisión inmediata)
    patrones.sort(key=lambda p: -p["idx"])
    return patrones[:15]


# ---------------------------------------------------------------------------
# Trampas de mercado: fakeouts / tomas de liquidez sobre zonas S/R
# ---------------------------------------------------------------------------
def detect_liquidity_traps(df: pd.DataFrame, sr: dict, n_recientes: int = 30, tolerancia_pct: float = 0.08):
    """
    Detecta posibles "engaños" del mercado: velas cuya mecha perfora una zona
    de soporte/resistencia conocida (toma de liquidez / stop hunt) pero cuyo
    cierre vuelve a quedar dentro del rango previo (el precio no logra
    sostenerse fuera de la zona). Es la firma típica de un fakeout.
    """
    sub = df.tail(n_recientes).reset_index(drop=True)
    niveles = [("resistencia", r["nivel"]) for r in sr.get("resistencias", [])] + [
        ("soporte", s["nivel"]) for s in sr.get("soportes", [])
    ]
    trampas = []

    for i in range(len(sub)):
        v = sub.iloc[i]
        for tipo_nivel, nivel in niveles:
            tol = nivel * (tolerancia_pct / 100)
            if tipo_nivel == "resistencia":
                # Mecha superior perfora la resistencia pero el cierre queda por debajo
                perfora = v["High"] > nivel + tol
                falla_sostener = v["Close"] < nivel
                direccion_trampa = "bajista"
                etiqueta = "Toma de liquidez sobre resistencia (fakeout alcista fallido)"
            else:
                # Mecha inferior perfora el soporte pero el cierre queda por encima
                perfora = v["Low"] < nivel - tol
                falla_sostener = v["Close"] > nivel
                direccion_trampa = "alcista"
                etiqueta = "Toma de liquidez bajo soporte (fakeout bajista fallido)"

            if perfora and falla_sostener:
                item = {
                    "idx": int(i),
                    "nivel_afectado": round(float(nivel), 5),
                    "tipo_zona": tipo_nivel,
                    "senal": etiqueta,
                    "direccion_esperada_tras_trampa": direccion_trampa,
                }
                if "Datetime" in sub.columns:
                    item["fecha"] = str(sub.loc[i, "Datetime"])
                trampas.append(item)

    trampas.sort(key=lambda t: -t["idx"])
    return trampas[:10]


# ---------------------------------------------------------------------------
# Zona de Reversión + puntos A/B para Fibonacci (solo intermedia/micro)
# ---------------------------------------------------------------------------
def detect_reversal_setup(df: pd.DataFrame, sr: dict, impulso: dict, patrones: list, trampas: list) -> dict:
    """
    Combina el impulso detectado (con sus puntos A/B ya calculados) con
    patrones de velas y trampas de liquidez recientes para confirmar (o no)
    que el punto B del impulso coincide con una zona real de reversión.
    Devuelve los puntos A/B exactos para trazar Fibonacci en la plataforma,
    junto con la confianza de la señal.
    """
    idx_b = impulso["punto_B"]["idx"]
    ventana_confirmacion = 3  # velas de tolerancia alrededor del extremo B

    patrones_confluentes = [p for p in patrones if abs(p["idx"] - idx_b) <= ventana_confirmacion]
    trampas_confluentes = [t for t in trampas if abs(t["idx"] - idx_b) <= ventana_confirmacion]

    direccion_esperada = "alcista" if impulso["direccion"] == "bajista" else "bajista"
    confirmaciones_alineadas = [
        p for p in patrones_confluentes
        if p["direccion"] in (direccion_esperada, "indefinida")
    ] + [t for t in trampas_confluentes if t["direccion_esperada_tras_trampa"] == direccion_esperada]

    zona_confirmada = len(confirmaciones_alineadas) > 0
    confianza = "alta" if len(confirmaciones_alineadas) >= 2 else ("media" if zona_confirmada else "baja")

    return {
        "punto_A": impulso["punto_A"],
        "punto_B": impulso["punto_B"],
        "direccion_reversion_esperada": direccion_esperada,
        "zona_reversion_confirmada": zona_confirmada,
        "confianza": confianza,
        "patrones_en_zona": patrones_confluentes,
        "trampas_en_zona": trampas_confluentes,
        "instruccion": (
            f"Trazar Fibonacci desde Punto A ({impulso['punto_A']['tipo']} @ "
            f"{impulso['punto_A']['precio']}) hasta Punto B ({impulso['punto_B']['tipo']} @ "
            f"{impulso['punto_B']['precio']}); buscar entradas {direccion_esperada}s en zona 50%-61.8%."
        ),
    }


def run_full_analysis(df: pd.DataFrame) -> dict:
    """Orquesta el análisis completo de backtesting sobre un DataFrame OHLCV.

    Validación Estricta de Datos: antes de cualquier cálculo se verifica que
    la temporalidad del CSV sea de 1 Hora en adelante (ver
    `validate_timeframe_or_raise`). Si no cumple, se lanza ValueError y el
    caller (routes/backtest.py) debe responder con un error 400 claro al
    usuario — el dataset NO tiene validez para este backtesting.
    """
    df = _normalize_columns(df)
    temporalidad = validate_timeframe_or_raise(df)

    sr = find_support_resistance(df)
    impulso = detect_last_impulse(df)
    fibo = fibonacci_levels(impulso["high"], impulso["low"], impulso["direccion"])
    daily = daily_high_low_analysis(df)
    atr = calculate_atr(df)
    volatilidad = session_volatility(df)
    winrate_fibo = fib_level_winrate(df)
    tp_sl = suggest_tp_sl(df, impulso["direccion"], sr, fibo, atr)
    orden = suggest_order_type(impulso["direccion"], tp_sl["precio_actual"], tp_sl["zona_entrada_fibo"], atr)

    resultado = {
        "temporalidad_detectada": temporalidad,
        "soportes_resistencias": sr,
        "ultimo_impulso": impulso,
        "fibonacci": fibo,
        "analisis_diario": daily,
        "atr_scalping": atr,
        "volatilidad_sesion": volatilidad,
        "win_rate_fibo": winrate_fibo,
        "sugerencia_tp_sl": tp_sl,
        "sugerencia_orden": orden,
    }

    # Zonas de reversión, patrones de velas y trampas de liquidez solo aplican
    # a temporalidades "intermedia" y "micro" (4H/1H): en "macro" (1D/1W) estas
    # señales tácticas no son relevantes, ese timeframe solo da contexto de
    # tendencia general (soportes/resistencias y Fibonacci siguen calculándose).
    if temporalidad["clasificacion"] in ("intermedia", "micro"):
        patrones = detect_candle_patterns(df)
        trampas = detect_liquidity_traps(df, sr)
        resultado["patrones_de_velas"] = patrones
        resultado["trampas_de_mercado"] = trampas
        resultado["zona_reversion_fibonacci"] = detect_reversal_setup(df, sr, impulso, patrones, trampas)
        resultado["sugerencia_orden"] = suggest_order_type(
            impulso["direccion"], tp_sl["precio_actual"], tp_sl["zona_entrada_fibo"], atr, trampas
        )
    else:
        resultado["patrones_de_velas"] = []
        resultado["trampas_de_mercado"] = []
        resultado["zona_reversion_fibonacci"] = {
            "nota": "Temporalidad macro (1D/1W): se usa solo como contexto de tendencia; "
                    "no se sugieren zonas de entrada Fibonacci puntuales."
        }

    return resultado
