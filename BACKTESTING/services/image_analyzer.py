"""
Módulo de Visión por Computadora para análisis de capturas de gráficos.
Usa OpenCV para detectar líneas horizontales (candidatas a soporte/resistencia)
y Pytesseract (OCR) para extraer valores numéricos visibles en la imagen
(precios, niveles, etiquetas de eje).

Nota: la detección es heurística (best-effort) ya que no existe estandarización
entre plataformas de trading; sirve como apoyo visual complementario al motor
cuantitativo de strategy_engine.py, que es la fuente de verdad del backtest.

Análisis Multi-Temporal: el sistema acepta 3 capturas simultáneas
(Macro, Intermedia, Micro) y combina sus zonas detectadas para sugerir
una lectura de confluencia entre temporalidades (ver evaluate_multi_timeframe).
"""
import re

import cv2
import numpy as np
import pytesseract
from PIL import Image

# Orden y significado de las 3 temporalidades visuales soportadas.
TIMEFRAMES_VISUALES = ("macro", "intermedia", "micro")


def _load_image(filepath: str):
    img = cv2.imread(filepath)
    if img is None:
        raise ValueError(f"No se pudo leer la imagen: {filepath}")
    return img


def extract_price_labels(filepath: str):
    """
    Aplica OCR sobre la imagen completa para extraer texto y filtra
    tokens que parezcan precios (números decimales).
    """
    img = Image.open(filepath)
    texto_crudo = pytesseract.image_to_string(img)

    # Patrón de precio: números con 2 a 6 decimales (cubre forex, cripto, índices)
    patron_precio = re.compile(r"\b\d{1,6}[.,]\d{2,6}\b")
    posibles_precios = patron_precio.findall(texto_crudo)

    precios_normalizados = sorted(
        {float(p.replace(",", ".")) for p in posibles_precios if p},
        reverse=True,
    )

    return {
        "texto_detectado": texto_crudo.strip(),
        "posibles_precios": precios_normalizados[:20],
    }


def detect_horizontal_zones(filepath: str, canny_low=50, canny_high=150,
                             hough_threshold=80, min_line_length=100, max_line_gap=10):
    """
    Detecta líneas horizontales dominantes en el gráfico (candidatas a zonas
    de soporte/resistencia dibujadas o visibles por agrupamiento de velas)
    usando Canny + Transformada de Hough.
    Retorna las posiciones Y (en píxeles, de arriba hacia abajo) de las líneas
    horizontales más relevantes, normalizadas como porcentaje de la altura total.
    """
    img = _load_image(filepath)
    alto, ancho = img.shape[:2]

    gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    bordes = cv2.Canny(gris, canny_low, canny_high)

    lineas = cv2.HoughLinesP(
        bordes,
        rho=1,
        theta=np.pi / 180,
        threshold=hough_threshold,
        minLineLength=min_line_length,
        maxLineGap=max_line_gap,
    )

    zonas_y = []
    if lineas is not None:
        # BUG ORIGINAL: "TypeError: cannot unpack non-iterable numpy.int32 object".
        # cv2.HoughLinesP normalmente devuelve un array con forma (N, 1, 4), por lo
        # que `linea[0]` es un vector [x1, y1, x2, y2] desempaquetable. Pero según
        # la versión de OpenCV/el build usado (o cuando N es muy pequeño) puede
        # devolver forma (N, 4) directamente: en ese caso `linea` YA es el vector
        # de 4 enteros y `linea[0]` es un único numpy.int32 (escalar, no iterable),
        # lo que provoca el error al intentar hacer `x1, y1, x2, y2 = linea[0]`.
        # Solución: normalizar siempre a forma (N, 4) con .reshape(-1, 4) antes de
        # iterar, sin importar la forma original devuelta por OpenCV.
        try:
            lineas = np.asarray(lineas).reshape(-1, 4)
        except ValueError as e:
            raise ValueError(
                f"Formato inesperado de líneas detectadas por Hough: {e}"
            ) from e

        for x1, y1, x2, y2 in lineas:
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            # Consideramos "horizontal" si la pendiente es casi plana
            if abs(y2 - y1) <= 3 and abs(x2 - x1) >= min_line_length:
                zonas_y.append((y1 + y2) / 2)

    # Agrupar posiciones Y cercanas (dentro de 1% de la altura) en una sola zona
    zonas_y.sort()
    agrupadas = []
    for y in zonas_y:
        if agrupadas and abs(y - agrupadas[-1][-1]) <= alto * 0.01:
            agrupadas[-1].append(y)
        else:
            agrupadas.append([y])

    zonas_relevantes = [
        {
            "posicion_y_pct": round(float(np.mean(grupo)) / alto * 100, 2),
            "num_lineas_agrupadas": len(grupo),
        }
        for grupo in agrupadas
    ]
    zonas_relevantes.sort(key=lambda z: -z["num_lineas_agrupadas"])

    return {
        "dimensiones": {"ancho": int(ancho), "alto": int(alto)},
        "zonas_horizontales_detectadas": zonas_relevantes[:10],
    }


def analyze_chart_image(filepath: str) -> dict:
    """Punto de entrada único: combina OCR + detección de líneas horizontales."""
    ocr = extract_price_labels(filepath)
    zonas = detect_horizontal_zones(filepath)
    return {
        "ocr": ocr,
        "zonas_visuales": zonas,
    }


# ---------------------------------------------------------------------------
# Análisis Multi-Temporal (Macro / Intermedia / Micro)
# ---------------------------------------------------------------------------
def _zona_dominante_pct(analisis_imagen: dict):
    """Extrae la posición Y (%) de la zona horizontal más fuerte de una imagen, o None."""
    zonas = analisis_imagen.get("zonas_visuales", {}).get("zonas_horizontales_detectadas", [])
    return zonas[0]["posicion_y_pct"] if zonas else None


def evaluate_multi_timeframe(resultados_por_temporalidad: dict, direccion_csv: str | None = None) -> dict:
    """
    Combina los análisis de las 3 imágenes (Macro, Intermedia, Micro) para
    sugerir una lectura de confluencia entre temporalidades.

    `resultados_por_temporalidad` es un dict con claves de TIMEFRAMES_VISUALES
    y valor = salida de analyze_chart_image (o None si esa imagen no se subió).
    `direccion_csv` es la dirección del último impulso detectado por el motor
    cuantitativo (strategy_engine.detect_last_impulse), usada como referencia
    para juzgar si las temporalidades visuales están alineadas con la data.

    Es heurístico (best-effort): no reemplaza el análisis cuantitativo del CSV,
    solo aporta contexto visual de contexto de mercado en varias temporalidades.
    """
    disponibles = {
        tf: resultados_por_temporalidad.get(tf)
        for tf in TIMEFRAMES_VISUALES
        if resultados_por_temporalidad.get(tf) and "error" not in resultados_por_temporalidad[tf]
    }

    if not disponibles:
        return {
            "confluencia": "sin_datos",
            "mensaje": "No se subieron imágenes válidas para evaluar confluencia multi-temporal.",
        }

    num_precios = {tf: len(r["ocr"]["posibles_precios"]) for tf, r in disponibles.items()}
    num_zonas = {tf: len(r["zonas_visuales"]["zonas_horizontales_detectadas"]) for tf, r in disponibles.items()}

    # Heurística de alineación: si al menos 2 temporalidades muestran su zona
    # horizontal dominante en la mitad superior (posible resistencia) o inferior
    # (posible soporte) del gráfico de forma consistente, se considera "alineación".
    posiciones = [p for p in (_zona_dominante_pct(r) for r in disponibles.values()) if p is not None]
    if len(posiciones) >= 2:
        en_mitad_superior = sum(1 for p in posiciones if p < 50)
        if en_mitad_superior == len(posiciones):
            sesgo_visual = "bajista (zonas fuertes cerca de máximos -> posible resistencia)"
        elif en_mitad_superior == 0:
            sesgo_visual = "alcista (zonas fuertes cerca de mínimos -> posible soporte)"
        else:
            sesgo_visual = "mixto (temporalidades no coinciden en la ubicación de la zona clave)"
    else:
        sesgo_visual = "insuficiente (se requieren al menos 2 imágenes con zonas detectadas)"

    alineado_con_csv = None
    if direccion_csv and "insuficiente" not in sesgo_visual:
        if direccion_csv == "alcista" and "alcista" in sesgo_visual:
            alineado_con_csv = True
        elif direccion_csv == "bajista" and "bajista" in sesgo_visual:
            alineado_con_csv = True
        elif "mixto" not in sesgo_visual:
            alineado_con_csv = False

    return {
        "temporalidades_recibidas": sorted(disponibles.keys()),
        "temporalidades_faltantes": sorted(set(TIMEFRAMES_VISUALES) - set(disponibles.keys())),
        "num_precios_ocr_por_temporalidad": num_precios,
        "num_zonas_por_temporalidad": num_zonas,
        "sesgo_visual_confluencia": sesgo_visual,
        "impulso_csv_direccion": direccion_csv,
        "alineado_con_impulso_csv": alineado_con_csv,
    }
