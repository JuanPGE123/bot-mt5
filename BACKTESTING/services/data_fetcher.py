"""
Módulo de extracción de datos históricos de mercado.
Usa la librería yfinance (Python) para descargar velas históricas hasta el
instante exacto de la consulta. No se emplea ninguna API REST comercial:
yfinance obtiene los datos consultando internamente páginas públicas de
Yahoo Finance.
"""
import os
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf
from dateutil.relativedelta import relativedelta

from config import PAIR_TICKER_MAP, TIMEFRAME_MAP, UPLOAD_CSV_DIR, DEFAULT_MESES_HISTORICO


class DataFetchError(Exception):
    pass


# yfinance limita cuánto histórico intradía se puede pedir hacia atrás,
# independientemente de la ventana de meses solicitada por el usuario.
_INTRADAY_MAX_DIAS = {
    "1m": 7,
    "5m": 60,
    "15m": 60,
    "30m": 60,
    "60m": 730,
    "1h": 730,
}


def _rango_fechas(interval: str, meses: int):
    """
    Calcula (start, end) para la descarga: por defecto los últimos `meses`
    meses hasta el instante exacto de la consulta (ahora), recortado al
    máximo permitido por yfinance para temporalidades intradía.
    """
    fin = datetime.now()
    inicio_solicitado = fin - relativedelta(months=meses)
    max_dias = _INTRADAY_MAX_DIAS.get(interval)
    if max_dias is not None:
        limite_intradia = fin - timedelta(days=max_dias)
        inicio_solicitado = max(inicio_solicitado, limite_intradia)
    return inicio_solicitado, fin


def _limpiar_nulos(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """
    Maneja valores nulos en el OHLCV descargado: primero forward-fill (huecos
    puntuales de mercado cerrado/feed intermitente), luego descarta cualquier
    fila que aún tenga nulos en columnas OHLC obligatorias. Retorna el
    DataFrame limpio y el número de filas descartadas (para reportar).
    """
    cols_ohlc = [c for c in ("Open", "High", "Low", "Close") if c in df.columns]
    filas_antes = len(df)
    if cols_ohlc:
        df[cols_ohlc] = df[cols_ohlc].ffill()
        df = df.dropna(subset=cols_ohlc)
    return df, filas_antes - len(df)


def fetch_historical_data(pair: str, timeframe: str, meses: int = DEFAULT_MESES_HISTORICO) -> pd.DataFrame:
    """
    Descarga histórico OHLCV para `pair` en la temporalidad `timeframe`.
    Por defecto trae los últimos `meses` (6 por defecto) hasta el momento
    exacto de la consulta, de forma automática y con limpieza de nulos.
    """
    if pair not in PAIR_TICKER_MAP:
        raise DataFetchError(f"Par no soportado: {pair}")
    if timeframe not in TIMEFRAME_MAP:
        raise DataFetchError(f"Temporalidad no soportada: {timeframe}")
    if meses <= 0:
        raise DataFetchError("La ventana de meses a consultar debe ser mayor a 0.")

    ticker = PAIR_TICKER_MAP[pair]
    interval = TIMEFRAME_MAP[timeframe]
    inicio, fin = _rango_fechas(interval, meses)

    df = yf.download(
        ticker,
        start=inicio,
        end=fin,
        interval=interval,
        progress=False,
        auto_adjust=False,
    )

    if df is None or df.empty:
        raise DataFetchError(
            f"No se obtuvo data para {pair} ({ticker}) en {timeframe} "
            f"(ventana solicitada: últimos {meses} mes(es)). "
            "Puede que Yahoo Finance no tenga histórico para ese instrumento/temporalidad."
        )

    # yfinance puede devolver columnas MultiIndex cuando se pasa un solo ticker en listas
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]

    df = df.reset_index()
    df.rename(columns={df.columns[0]: "Datetime"}, inplace=True)

    # Resampleo manual a 4h ya que yfinance no ofrece ese intervalo nativamente
    if timeframe == "4h":
        df = df.set_index("Datetime")
        df = df.resample("4h").agg(
            {
                "Open": "first",
                "High": "max",
                "Low": "min",
                "Close": "last",
                "Adj Close": "last",
                "Volume": "sum",
            }
        ).dropna().reset_index()

    df, nulos_limpiados = _limpiar_nulos(df)
    if df.empty:
        raise DataFetchError(
            f"Tras limpiar valores nulos no quedaron velas válidas para {pair} en {timeframe}."
        )

    df["consultado_en"] = datetime.now().isoformat(timespec="seconds")
    df.attrs["nulos_limpiados"] = nulos_limpiados
    df.attrs["ventana_meses"] = meses
    return df


def export_to_csv(df: pd.DataFrame, pair: str, timeframe: str) -> str:
    """Guarda el DataFrame en uploads/csv y retorna la ruta absoluta del archivo."""
    os.makedirs(UPLOAD_CSV_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{pair}_{timeframe}_{stamp}.csv"
    filepath = os.path.join(UPLOAD_CSV_DIR, filename)
    df.to_csv(filepath, index=False)
    return filepath
