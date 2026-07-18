"""
Módulo de Recordatorios por WhatsApp (Meta Cloud API).
Personal — solo responde/envía a config.MI_NUMERO.

Interpreta comandos en español con regex + dateparser (sin IA externa):
  - "recuérdame TAREA mañana a las 5pm"
  - "agrega TAREA para el 20 de julio"
  - "pendientes" / "qué tengo"
  - "hoy"
  - "elimina N"
Si falta la fecha se asume hoy; si falta la hora se pregunta y se espera
la respuesta en el siguiente mensaje (estado_conversacion).
"""
import re
from datetime import datetime

import requests
from dateparser.search import search_dates
from zoneinfo import ZoneInfo

import config
import models_recordatorio as db

TZ = ZoneInfo(config.RECORDATORIOS_TZ)

_RE_HORA_EXPLICITA = re.compile(r"\d{1,2}(:\d{2})?\s*(am|pm)|\ba las\b|\bhrs?\b", re.IGNORECASE)
_RE_ELIMINA = re.compile(r"^elimina\s+(\d+)$", re.IGNORECASE)
_RE_CREAR = re.compile(r"^(recu[eé]rdame|agrega)\s+(.+)$", re.IGNORECASE)
_RE_HORA_LIBRE = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)?", re.IGNORECASE)


def enviar_mensaje(texto: str, numero: str | None = None) -> requests.Response:
    numero = numero or config.MI_NUMERO
    url = f"https://graph.facebook.com/v18.0/{config.WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {config.WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "text",
        "text": {"body": texto},
    }
    return requests.post(url, headers=headers, json=payload, timeout=15)


def _extraer_hora(texto: str):
    """Extrae (hora, minuto) 24h de una respuesta libre tipo '5pm', '17:30', 'a las 5'."""
    tl = texto.lower().strip()
    m = _RE_HORA_LIBRE.search(tl)
    if not m:
        return None
    hora = int(m.group(1))
    minuto = int(m.group(2) or 0)
    ampm = (m.group(3) or "").replace(".", "")
    if ampm == "pm" and hora < 12:
        hora += 12
    elif ampm == "am" and hora == 12:
        hora = 0
    elif not ampm and ("tarde" in tl or "noche" in tl) and hora < 12:
        hora += 12
    if not (0 <= hora <= 23 and 0 <= minuto <= 59):
        return None
    return hora, minuto


def _interpretar(texto: str) -> dict:
    t = texto.strip()
    tl = t.lower()

    if tl in ("pendientes", "qué tengo", "que tengo"):
        return {"accion": "listar"}
    if tl == "hoy":
        return {"accion": "listar_hoy"}

    m = _RE_ELIMINA.match(tl)
    if m:
        return {"accion": "eliminar", "id": int(m.group(1))}

    m = _RE_CREAR.match(t)
    if not m:
        return {"accion": "desconocido"}

    resto = re.sub(r"^que\s+", "", m.group(2).strip(), flags=re.IGNORECASE)

    resultados = search_dates(
        resto,
        languages=["es"],
        settings={
            "TIMEZONE": config.RECORDATORIOS_TZ,
            "RETURN_AS_TIMEZONE_AWARE": True,
            "PREFER_DATES_FROM": "future",
        },
    )
    if not resultados:
        return {"accion": "falta_hora", "tarea": resto.strip(" ,."), "fecha": datetime.now(TZ)}

    frase, fecha = resultados[-1]
    tarea = resto.replace(frase, "").strip()
    tarea = re.sub(r"\b(para el|para|el)\s*$", "", tarea, flags=re.IGNORECASE).strip(" ,.")
    if not tarea:
        tarea = "Recordatorio"

    if not _RE_HORA_EXPLICITA.search(frase):
        return {"accion": "falta_hora", "tarea": tarea, "fecha": fecha}
    return {"accion": "crear", "tarea": tarea, "fecha_hora": fecha}


def _formatear_item(item: dict) -> str:
    fh = datetime.fromisoformat(item["fecha_hora"])
    return f"#{item['id']} {item['tarea']} — {fh.strftime('%d/%m %H:%M')}"


def procesar_mensaje(numero: str, texto: str) -> str | None:
    """Procesa un mensaje entrante y devuelve el texto de respuesta (o None si se ignora)."""
    if numero != config.MI_NUMERO:
        return None  # módulo personal: ignora cualquier otro número

    pendiente = db.get_estado_pendiente(numero)
    if pendiente:
        hora = _extraer_hora(texto)
        if not hora:
            return "No entendí la hora. Ejemplo: 5pm o 17:30. ¿A qué hora?"
        fecha_base = datetime.fromisoformat(pendiente["fecha_hora"])
        fecha_final = fecha_base.replace(hour=hora[0], minute=hora[1], second=0, microsecond=0)
        rid = db.add_recordatorio(pendiente["tarea"], fecha_final.isoformat())
        db.clear_estado_pendiente(numero)
        return f"Listo #{rid}: {pendiente['tarea']} — {fecha_final.strftime('%d/%m/%Y %H:%M')}"

    cmd = _interpretar(texto)
    accion = cmd["accion"]

    if accion in ("listar", "listar_hoy"):
        solo_hoy = accion == "listar_hoy"
        hoy_iso = datetime.now(TZ).strftime("%Y-%m-%d") if solo_hoy else None
        items = db.get_pendientes(solo_hoy=solo_hoy, fecha_hoy_iso=hoy_iso)
        if not items:
            return "No tienes pendientes."
        return "\n".join(_formatear_item(it) for it in items)

    if accion == "eliminar":
        ok = db.delete_recordatorio(cmd["id"])
        return f"Eliminado #{cmd['id']}." if ok else f"No existe el recordatorio #{cmd['id']}."

    if accion == "falta_hora":
        db.set_estado_pendiente(numero, cmd["tarea"], cmd["fecha"].isoformat())
        return "¿A qué hora?"

    if accion == "crear":
        rid = db.add_recordatorio(cmd["tarea"], cmd["fecha_hora"].isoformat())
        return f"Listo #{rid}: {cmd['tarea']} — {cmd['fecha_hora'].strftime('%d/%m/%Y %H:%M')}"

    return (
        "No entendí. Prueba:\n"
        "'recuérdame TAREA mañana a las 5pm'\n"
        "'agrega TAREA para el 20 de julio'\n"
        "'pendientes' / 'hoy' / 'elimina N'"
    )
