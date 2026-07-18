"""
Capa de acceso a datos (SQLite puro, sin ORM) para el Diario de Trading y
Psicología Operativa.

Soporta dos bases de datos independientes mediante el parámetro `db_path`:
- DB_PATH: datos reales del usuario.
- DEMO_DB_PATH: datos ficticios del perfil DemoUser (ver seed_demo_data),
  usado únicamente para mostrar la aplicación a terceros sin exponer
  información real (Punto 4 del requerimiento).
"""
import random
import sqlite3
from datetime import datetime, timedelta

from config import DB_PATH

# Columnas de psicología operativa añadidas sobre la tabla original de trades.
# name -> definición SQL usada al hacer ALTER TABLE en bases de datos ya existentes.
PSICOLOGIA_COLUMNS = {
    "emocion_antes": "TEXT",
    "emocion_durante": "TEXT",
    "emocion_despues": "TEXT",
    "nivel_estres": "INTEGER",       # escala 1 (muy bajo) a 5 (muy alto)
    "cumplio_plan": "INTEGER",       # 1 = sí, 0 = no
    "recomendaciones": "TEXT",       # notas/recomendaciones a tener en cuenta a futuro
}


def get_connection(db_path: str | None = None):
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str | None = None):
    conn = get_connection(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            par TEXT NOT NULL,
            direccion TEXT NOT NULL,           -- LONG / SHORT
            entrada REAL NOT NULL,
            stop_loss REAL NOT NULL,
            take_profit REAL NOT NULL,
            precio_salida REAL,
            pnl REAL,
            resultado TEXT,                    -- WIN / LOSS / BE
            notas TEXT,
            creado_en TEXT NOT NULL
        )
        """
    )
    # Migración incremental: añade columnas de psicología operativa si el
    # archivo .db ya existía de una versión previa sin este módulo.
    columnas_existentes = {row["name"] for row in conn.execute("PRAGMA table_info(trades)")}
    for columna, tipo_sql in PSICOLOGIA_COLUMNS.items():
        if columna not in columnas_existentes:
            conn.execute(f"ALTER TABLE trades ADD COLUMN {columna} {tipo_sql}")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS entradas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            par TEXT NOT NULL,
            direccion TEXT NOT NULL,           -- COMPRA / VENTA
            tipo_orden TEXT NOT NULL,           -- Mercado / Buy Limit / Sell Limit / Buy Stop / Sell Stop
            precio_entrada REAL NOT NULL,
            stop_loss REAL NOT NULL,
            take_profit REAL NOT NULL,
            riesgo_beneficio REAL,
            temporalidad TEXT,
            motivo TEXT,
            origen TEXT NOT NULL DEFAULT 'manual',  -- manual / backtest
            creado_en TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def add_trade(data: dict, db_path: str | None = None):
    conn = get_connection(db_path)
    cur = conn.execute(
        """
        INSERT INTO trades (fecha, par, direccion, entrada, stop_loss, take_profit,
                             precio_salida, pnl, resultado, notas, creado_en,
                             emocion_antes, emocion_durante, emocion_despues,
                             nivel_estres, cumplio_plan, recomendaciones)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["fecha"],
            data["par"],
            data["direccion"],
            data["entrada"],
            data["stop_loss"],
            data["take_profit"],
            data.get("precio_salida"),
            data.get("pnl"),
            data.get("resultado"),
            data.get("notas", ""),
            data.get("creado_en") or datetime.utcnow().isoformat(),
            data.get("emocion_antes", ""),
            data.get("emocion_durante", ""),
            data.get("emocion_despues", ""),
            data.get("nivel_estres"),
            data.get("cumplio_plan"),
            data.get("recomendaciones", ""),
        ),
    )
    conn.commit()
    trade_id = cur.lastrowid
    conn.close()
    return trade_id


def get_all_trades(db_path: str | None = None):
    conn = get_connection(db_path)
    rows = conn.execute("SELECT * FROM trades ORDER BY fecha DESC, id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_trade(trade_id: int, db_path: str | None = None):
    conn = get_connection(db_path)
    conn.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
    conn.commit()
    conn.close()


def clear_trades(db_path: str | None = None):
    conn = get_connection(db_path)
    conn.execute("DELETE FROM trades")
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Entradas — oportunidades de compra/venta sugeridas (manual o desde Backtesting)
# ---------------------------------------------------------------------------
def add_entrada(data: dict, db_path: str | None = None):
    conn = get_connection(db_path)
    cur = conn.execute(
        """
        INSERT INTO entradas (par, direccion, tipo_orden, precio_entrada, stop_loss,
                               take_profit, riesgo_beneficio, temporalidad, motivo, origen, creado_en)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["par"],
            data["direccion"],
            data["tipo_orden"],
            data["precio_entrada"],
            data["stop_loss"],
            data["take_profit"],
            data.get("riesgo_beneficio"),
            data.get("temporalidad", ""),
            data.get("motivo", ""),
            data.get("origen", "manual"),
            data.get("creado_en") or datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()
    entrada_id = cur.lastrowid
    conn.close()
    return entrada_id


def get_all_entradas(db_path: str | None = None):
    conn = get_connection(db_path)
    rows = conn.execute("SELECT * FROM entradas ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_entrada(entrada_id: int, db_path: str | None = None):
    conn = get_connection(db_path)
    conn.execute("DELETE FROM entradas WHERE id = ?", (entrada_id,))
    conn.commit()
    conn.close()


def clear_entradas(db_path: str | None = None):
    conn = get_connection(db_path)
    conn.execute("DELETE FROM entradas")
    conn.commit()
    conn.close()


def compute_journal_stats(trades: list):
    """Calcula PnL total, win-rate y racha actual/máxima a partir del historial de trades."""
    if not trades:
        return {
            "total_trades": 0,
            "pnl_total": 0.0,
            "win_rate": 0.0,
            "wins": 0,
            "losses": 0,
            "racha_actual": 0,
            "racha_tipo": "N/A",
            "mejor_racha_wins": 0,
            "peor_racha_losses": 0,
        }

    # Orden cronológico ascendente para calcular rachas correctamente
    ordenados = sorted(trades, key=lambda t: (t["fecha"], t["id"]))

    wins = sum(1 for t in ordenados if t["resultado"] == "WIN")
    losses = sum(1 for t in ordenados if t["resultado"] == "LOSS")
    total = len(ordenados)
    pnl_total = sum(t["pnl"] or 0 for t in ordenados)

    racha_actual = 0
    racha_tipo = None
    mejor_racha_wins = 0
    peor_racha_losses = 0
    contador = 0
    tipo_prev = None

    for t in ordenados:
        r = t["resultado"]
        if r not in ("WIN", "LOSS"):
            contador = 0
            tipo_prev = None
            continue
        if r == tipo_prev:
            contador += 1
        else:
            contador = 1
            tipo_prev = r
        if r == "WIN":
            mejor_racha_wins = max(mejor_racha_wins, contador)
        else:
            peor_racha_losses = max(peor_racha_losses, contador)

    racha_actual = contador
    racha_tipo = tipo_prev or "N/A"

    return {
        "total_trades": total,
        "pnl_total": round(pnl_total, 2),
        "win_rate": round((wins / total) * 100, 2) if total else 0.0,
        "wins": wins,
        "losses": losses,
        "racha_actual": racha_actual,
        "racha_tipo": racha_tipo,
        "mejor_racha_wins": mejor_racha_wins,
        "peor_racha_losses": peor_racha_losses,
    }


# ---------------------------------------------------------------------------
# Psicología Operativa — Objetivo principal: "No quemar la cuenta"
# ---------------------------------------------------------------------------
def evaluate_psychological_risk(trades: list, n_recientes: int = 5) -> dict:
    """
    Analiza los últimos `n_recientes` trades (orden cronológico) y genera
    alertas psicológicas enfocadas en gestión de riesgo emocional. El
    objetivo central es detectar el patrón típico de "quema de cuenta":
    rachas de pérdidas + estrés alto + incumplimiento del plan de trading.
    """
    if not trades:
        return {
            "nivel_riesgo": "sin_datos",
            "alertas": [],
            "recomendacion_principal": "Registra tus primeras operaciones para activar el monitoreo psicológico.",
        }

    ordenados = sorted(trades, key=lambda t: (t["fecha"], t["id"]))
    recientes = ordenados[-n_recientes:]

    alertas = []

    # 1) Racha de pérdidas consecutivas (riesgo de "revenge trading")
    racha_perdidas = 0
    for t in reversed(ordenados):
        if t["resultado"] == "LOSS":
            racha_perdidas += 1
        else:
            break
    if racha_perdidas >= 3:
        alertas.append(
            f"Racha de {racha_perdidas} pérdidas consecutivas. Alto riesgo de 'revenge trading': "
            "considera pausar la operativa por hoy."
        )

    # 2) Estrés alto sostenido
    estres_altos = [t for t in recientes if (t.get("nivel_estres") or 0) >= 4]
    if len(estres_altos) >= 2:
        alertas.append(
            f"{len(estres_altos)} de las últimas {len(recientes)} operaciones registraron estrés alto (4-5). "
            "Estado emocional inestable: reduce tamaño de posición o detén la operativa."
        )

    # 3) Incumplimiento del plan
    incumplidos = [t for t in recientes if t.get("cumplio_plan") == 0]
    if len(incumplidos) >= 2:
        alertas.append(
            f"{len(incumplidos)} de las últimas {len(recientes)} operaciones NO siguieron el plan de trading. "
            "Operativa impulsiva detectada: refuerza la disciplina antes de seguir operando."
        )

    # 4) Combinación crítica: pérdidas + estrés alto + incumplimiento -> riesgo de quemar la cuenta
    combinacion_critica = (
        racha_perdidas >= 2
        and len(estres_altos) >= 1
        and len(incumplidos) >= 1
    )
    if combinacion_critica:
        alertas.append(
            "COMBINACIÓN CRÍTICA: pérdidas recientes + estrés alto + incumplimiento del plan. "
            "Riesgo elevado de quemar la cuenta. Se recomienda detener la operativa por el resto del día."
        )

    if combinacion_critica or racha_perdidas >= 4:
        nivel_riesgo = "alto"
    elif alertas:
        nivel_riesgo = "medio"
    else:
        nivel_riesgo = "bajo"

    recomendacion_principal = {
        "alto": "Detén la operativa hoy. Revisa tu plan de trading y espera a estar en un estado emocional estable.",
        "medio": "Reduce el tamaño de posición y opera solo tus setups de mayor calidad hasta estabilizar tu estado emocional.",
        "bajo": "Estado emocional y disciplina dentro de rango saludable. Mantén el proceso.",
        "sin_datos": "Sin datos suficientes.",
    }[nivel_riesgo]

    return {
        "nivel_riesgo": nivel_riesgo,
        "racha_perdidas_actual": racha_perdidas,
        "alertas": alertas,
        "recomendacion_principal": recomendacion_principal,
    }


# ---------------------------------------------------------------------------
# DemoUser — datos ficticios para mostrar la aplicación sin exponer datos reales
# ---------------------------------------------------------------------------
def seed_demo_data(db_path: str, force: bool = False):
    """
    Puebla la base de datos del DemoUser con operaciones ficticias (ganadoras
    y perdedoras) y entradas de psicología, solo si está vacía (o si
    `force=True`). Es determinístico (semilla fija) para que la demo se vea
    igual en cada despliegue.
    """
    init_db(db_path)
    conn = get_connection(db_path)
    existentes = conn.execute("SELECT COUNT(*) AS n FROM trades").fetchone()["n"]
    conn.close()
    if existentes > 0 and not force:
        _seed_demo_entradas(db_path, force)
        return

    rng = random.Random(42)
    pares_demo = ["EURUSD", "GBPUSD", "XAUUSD", "BTCUSD", "USDJPY"]
    emociones_pos = ["Confianza", "Calma", "Enfocado"]
    emociones_neg = ["Ansiedad", "Duda", "Frustración", "Euforia"]
    hoy = datetime.utcnow().date()

    for i in range(20):
        fecha = hoy - timedelta(days=(20 - i))
        direccion = rng.choice(["LONG", "SHORT"])
        par = rng.choice(pares_demo)
        entrada = round(rng.uniform(1.05, 1.20) if "USD" in par and par != "BTCUSD" else rng.uniform(60000, 70000), 5)
        gano = rng.random() > 0.42  # ~58% win-rate ficticio, realista para scalping disciplinado
        variacion = entrada * rng.uniform(0.002, 0.012)
        if direccion == "LONG":
            precio_salida = entrada + variacion if gano else entrada - variacion
        else:
            precio_salida = entrada - variacion if gano else entrada + variacion
        diff = (precio_salida - entrada) if direccion == "LONG" else (entrada - precio_salida)
        pnl = round(diff, 5)
        resultado = "WIN" if pnl > 0 else "LOSS"

        # Simula una racha mala reciente (día 15-17) para poder mostrar la
        # alerta psicológica "no quemar la cuenta" en la demo.
        estres_alto_forzado = 15 <= i <= 17
        add_trade(
            {
                "fecha": fecha.isoformat(),
                "par": par,
                "direccion": direccion,
                "entrada": entrada,
                "stop_loss": round(entrada - variacion * 1.5 if direccion == "LONG" else entrada + variacion * 1.5, 5),
                "take_profit": round(entrada + variacion * 2 if direccion == "LONG" else entrada - variacion * 2, 5),
                "precio_salida": round(precio_salida, 5),
                "pnl": pnl,
                "resultado": resultado,
                "notas": "Operación de ejemplo (perfil Demo).",
                "emocion_antes": rng.choice(emociones_pos if not estres_alto_forzado else emociones_neg),
                "emocion_durante": rng.choice(emociones_pos if resultado == "WIN" else emociones_neg),
                "emocion_despues": rng.choice(emociones_pos if resultado == "WIN" else emociones_neg),
                "nivel_estres": rng.randint(4, 5) if estres_alto_forzado else rng.randint(1, 3),
                "cumplio_plan": 0 if estres_alto_forzado else 1,
                "recomendaciones": "Ejemplo generado automáticamente para el perfil Demo/Showcase.",
            },
            db_path=db_path,
        )

    _seed_demo_entradas(db_path, force)


def _seed_demo_entradas(db_path: str, force: bool = False):
    conn = get_connection(db_path)
    existentes_entradas = conn.execute("SELECT COUNT(*) AS n FROM entradas").fetchone()["n"]
    conn.close()
    if existentes_entradas > 0 and not force:
        return

    entradas_demo = [
        ("USDCAD", "COMPRA", "Buy Limit", 1.41500, 1.41300, 1.41700, 1.0, "micro", "Retroceso esperado a zona Fibo 61.8%."),
        ("EURUSD", "VENTA", "Venta a Mercado", 1.08650, 1.08820, 1.08310, 2.0, "intermedia", "Trampa de liquidez confirma reversión bajista."),
        ("XAUUSD", "COMPRA", "Buy Stop", 2382.50, 2378.00, 2391.00, 1.9, "micro", "Ruptura confirmada de resistencia clave."),
        ("GBPUSD", "VENTA", "Sell Limit", 1.26900, 1.27100, 1.26500, 2.0, "intermedia", "Precio se alejó de la zona clave, se espera retroceso."),
    ]
    for par, direccion, tipo_orden, entrada, sl, tp, rr, tf, motivo in entradas_demo:
        add_entrada(
            {
                "par": par,
                "direccion": direccion,
                "tipo_orden": tipo_orden,
                "precio_entrada": entrada,
                "stop_loss": sl,
                "take_profit": tp,
                "riesgo_beneficio": rr,
                "temporalidad": tf,
                "motivo": motivo,
                "origen": "backtest",
            },
            db_path=db_path,
        )
