"""
Capa de acceso a datos (SQLite puro) del módulo de Recordatorios por WhatsApp.

Base de datos propia y aislada (RECORDATORIOS_DB_PATH) — no comparte tablas
con el resto de la app. Módulo personal: solo lo usa/ve AUTH_USERNAME, nunca
el perfil DemoUser.
"""
import sqlite3
from datetime import datetime

from config import RECORDATORIOS_DB_PATH


def get_connection():
    conn = sqlite3.connect(RECORDATORIOS_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS recordatorios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tarea TEXT NOT NULL,
            fecha_hora TEXT NOT NULL,      -- ISO8601 con offset, America/Bogota
            enviado INTEGER NOT NULL DEFAULT 0,
            creado_en TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS estado_conversacion (
            numero TEXT PRIMARY KEY,       -- número de WhatsApp esperando respuesta (la hora)
            tarea TEXT NOT NULL,
            fecha_hora TEXT NOT NULL,      -- fecha ya resuelta (solo falta la hora)
            actualizado_en TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def add_recordatorio(tarea: str, fecha_hora_iso: str) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO recordatorios (tarea, fecha_hora, enviado, creado_en) VALUES (?, ?, 0, ?)",
        (tarea, fecha_hora_iso, datetime.utcnow().isoformat()),
    )
    conn.commit()
    rid = cur.lastrowid
    conn.close()
    return rid


def get_pendientes(solo_hoy: bool = False, fecha_hoy_iso: str | None = None):
    conn = get_connection()
    if solo_hoy and fecha_hoy_iso:
        rows = conn.execute(
            "SELECT * FROM recordatorios WHERE enviado = 0 AND substr(fecha_hora, 1, 10) = ? ORDER BY fecha_hora ASC",
            (fecha_hoy_iso,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM recordatorios WHERE enviado = 0 ORDER BY fecha_hora ASC"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_todos(db_path: str | None = None):
    conn = get_connection()
    rows = conn.execute("SELECT * FROM recordatorios ORDER BY fecha_hora ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_recordatorio(recordatorio_id: int) -> bool:
    conn = get_connection()
    cur = conn.execute("DELETE FROM recordatorios WHERE id = ?", (recordatorio_id,))
    conn.commit()
    existia = cur.rowcount > 0
    conn.close()
    return existia


def marcar_enviado(recordatorio_id: int):
    conn = get_connection()
    conn.execute("UPDATE recordatorios SET enviado = 1 WHERE id = ?", (recordatorio_id,))
    conn.commit()
    conn.close()


def get_recordatorios_vencidos(ahora_iso: str):
    """Recordatorios pendientes cuya fecha_hora ya pasó (para disparar el envío)."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM recordatorios WHERE enviado = 0 AND fecha_hora <= ? ORDER BY fecha_hora ASC",
        (ahora_iso,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Estado de conversación — flujo "¿A qué hora?" cuando el usuario no da hora.
# ---------------------------------------------------------------------------
def set_estado_pendiente(numero: str, tarea: str, fecha_hora_iso: str):
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO estado_conversacion (numero, tarea, fecha_hora, actualizado_en)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(numero) DO UPDATE SET tarea=excluded.tarea, fecha_hora=excluded.fecha_hora,
                                           actualizado_en=excluded.actualizado_en
        """,
        (numero, tarea, fecha_hora_iso, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def get_estado_pendiente(numero: str):
    conn = get_connection()
    row = conn.execute("SELECT * FROM estado_conversacion WHERE numero = ?", (numero,)).fetchone()
    conn.close()
    return dict(row) if row else None


def clear_estado_pendiente(numero: str):
    conn = get_connection()
    conn.execute("DELETE FROM estado_conversacion WHERE numero = ?", (numero,))
    conn.commit()
    conn.close()
