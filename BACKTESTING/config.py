"""
Configuración global de la aplicación.
Centraliza rutas, credenciales de login y constantes de negocio.
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# En producción (Docker/Fly.io) se monta un volumen persistente en DATA_DIR;
# en local se usa BASE_DIR como antes.
DATA_DIR = os.environ.get("BACKTESTING_DATA_DIR", BASE_DIR)

# --- Seguridad / Sesión ---
SECRET_KEY = os.environ.get("BACKTESTING_SECRET_KEY", "dev-secret-key-cambiar-en-produccion")

# --- Credenciales (override vía env en producción; default = valores del proyecto) ---
AUTH_USERNAME = os.environ.get("BACKTESTING_USERNAME", "juanpablogiraldoe")
AUTH_PASSWORD = os.environ.get("BACKTESTING_PASSWORD", "juanpge")

# --- Usuario Demo / Showcase (Punto 4): perfil de solo demostración con datos
# ficticios, aislado en su propia base de datos (nunca toca los datos reales).
DEMO_USERNAME = os.environ.get("BACKTESTING_DEMO_USERNAME", "DemoUser")
DEMO_PASSWORD = os.environ.get("BACKTESTING_DEMO_PASSWORD", "demo1234")

# --- Rutas de almacenamiento ---
UPLOAD_CSV_DIR = os.path.join(DATA_DIR, "uploads", "csv")
UPLOAD_IMG_DIR = os.path.join(DATA_DIR, "uploads", "images")
DB_PATH = os.path.join(DATA_DIR, "data", "app.db")
DEMO_DB_PATH = os.path.join(DATA_DIR, "data", "demo.db")
DEMO_FIXTURES_DIR = os.path.join(BASE_DIR, "fixtures", "demo")

ALLOWED_CSV_EXT = {"csv"}
ALLOWED_IMG_EXT = {"png", "jpg", "jpeg", "bmp"}

# --- Pares soportados y su ticker equivalente en Yahoo Finance (vía yfinance) ---
# yfinance obtiene datos scrapeando/consumiendo endpoints públicos de Yahoo Finance
# a través de la librería (NO es una API REST comercial de trading).
PAIR_TICKER_MAP = {
    # --- Forex mayores y cruces ---
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "AUDUSD": "AUDUSD=X",
    "USDCAD": "USDCAD=X",
    "USDCHF": "USDCHF=X",
    "NZDUSD": "NZDUSD=X",
    "EURGBP": "EURGBP=X",
    "EURJPY": "EURJPY=X",
    "GBPJPY": "GBPJPY=X",
    "EURAUD": "EURAUD=X",
    "AUDJPY": "AUDJPY=X",
    "EURCHF": "EURCHF=X",
    "USDMXN": "USDMXN=X",
    # --- Cripto ---
    "BTCUSD": "BTC-USD",
    "ETHUSD": "ETH-USD",
    "SOLUSD": "SOL-USD",
    "BNBUSD": "BNB-USD",
    "XRPUSD": "XRP-USD",
    "ADAUSD": "ADA-USD",
    "DOGEUSD": "DOGE-USD",
    # --- Metales y materias primas ---
    "XAUUSD": "GC=F",
    "XAGUSD": "SI=X",
    "WTIUSD": "CL=F",
    # --- Índices ---
    "US30": "^DJI",
    "NAS100": "^NDX",
    "SPX500": "^GSPC",
    "GER40": "^GDAXI",
    "UK100": "^FTSE",
}

# Temporalidades soportadas -> parámetro interval de yfinance
TIMEFRAME_MAP = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "60m",
    "4h": "1h",   # yfinance no tiene 4h nativo, se resamplea desde 1h
    "1d": "1d",
    "1wk": "1wk",
}

# Ventana de tiempo por defecto para la extracción automática de histórico
# (Módulo de Extracción de Datos Históricos): últimos N meses hasta el
# instante exacto de la consulta.
DEFAULT_MESES_HISTORICO = 6
