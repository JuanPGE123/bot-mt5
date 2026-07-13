"""
Panel de noticias fundamentales.

No se consume ninguna API REST de noticias comercial. Las fuentes son:
  1. `yfinance` (Ticker.news) — biblioteca Python que obtiene titulares
     públicos asociados al instrumento consultado.
  2. Un scraper de respaldo con BeautifulSoup sobre una página pública de
     titulares financieros generales, filtrando por palabras clave del par.

Ambas fuentes son "best-effort": si fallan (cambios de HTML, timeouts, etc.)
se degradan de forma silenciosa y devuelven lista vacía en vez de romper la app.
"""
from datetime import datetime

import requests
import yfinance as yf
from bs4 import BeautifulSoup

from config import PAIR_TICKER_MAP

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

# Palabras clave por divisa/activo para filtrar noticias generales por relevancia
KEYWORDS_POR_PAR = {
    "EURUSD": ["euro", "eur", "ecb", "bce", "eurozone"],
    "GBPUSD": ["pound", "gbp", "bank of england", "boe", "uk "],
    "USDJPY": ["yen", "jpy", "boj", "bank of japan"],
    "AUDUSD": ["aussie", "aud", "rba"],
    "USDCAD": ["loonie", "cad", "boc"],
    "USDCHF": ["franc", "chf", "snb"],
    "NZDUSD": ["kiwi", "nzd", "rbnz"],
    "BTCUSD": ["bitcoin", "btc", "crypto"],
    "ETHUSD": ["ethereum", "eth", "crypto"],
    "XAUUSD": ["gold", "xau", "bullion"],
    "XAGUSD": ["silver", "xag"],
    "US30": ["dow jones", "us30"],
    "NAS100": ["nasdaq", "tech stocks"],
    "SPX500": ["s&p 500", "spx"],
}


def _news_from_yfinance(pair: str, limit: int = 10):
    ticker_symbol = PAIR_TICKER_MAP.get(pair)
    if not ticker_symbol:
        return []
    try:
        ticker = yf.Ticker(ticker_symbol)
        raw_news = ticker.news or []
    except Exception:
        return []

    noticias = []
    for item in raw_news[:limit]:
        content = item.get("content", item)  # compatibilidad entre versiones de yfinance
        titulo = content.get("title") or item.get("title")
        link = (content.get("canonicalUrl", {}) or {}).get("url") or item.get("link")
        fecha = content.get("pubDate") or item.get("providerPublishTime")
        if not titulo:
            continue
        noticias.append(
            {
                "titulo": titulo,
                "link": link,
                "fecha": str(fecha) if fecha else "",
                "fuente": "Yahoo Finance (yfinance)",
            }
        )
    return noticias


def _news_from_scraping(pair: str, limit: int = 10):
    """
    Scraping de respaldo sobre una página pública de titulares financieros.
    Filtra por palabras clave asociadas al par para dar contexto fundamental.
    """
    keywords = KEYWORDS_POR_PAR.get(pair, [])
    try:
        resp = requests.get(
            "https://www.marketwatch.com/markets", headers=HEADERS, timeout=6
        )
        resp.raise_for_status()
    except Exception:
        return []

    try:
        soup = BeautifulSoup(resp.text, "lxml")
        titulares = []
        for a in soup.select("a"):
            texto = a.get_text(strip=True)
            href = a.get("href")
            if not texto or len(texto) < 15 or not href:
                continue
            if keywords and not any(k.lower() in texto.lower() for k in keywords):
                continue
            titulares.append(
                {
                    "titulo": texto,
                    "link": href if href.startswith("http") else f"https://www.marketwatch.com{href}",
                    "fecha": "",
                    "fuente": "MarketWatch (scraping)",
                }
            )
            if len(titulares) >= limit:
                break
        return titulares
    except Exception:
        return []


def get_news_for_pair(pair: str, limit: int = 10) -> dict:
    """Combina ambas fuentes y retorna noticias relevantes para el par consultado."""
    noticias = _news_from_yfinance(pair, limit=limit)
    if len(noticias) < limit:
        noticias += _news_from_scraping(pair, limit=limit - len(noticias))

    return {
        "par": pair,
        "consultado_en": datetime.now().isoformat(timespec="seconds"),
        "total": len(noticias),
        "noticias": noticias,
    }
