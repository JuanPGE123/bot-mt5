# Scalping Analytics — Backtesting Platform

Plataforma web local de backtesting y análisis de scalping. Todo el procesamiento
de datos financieros y noticias se realiza con Python (`yfinance` + scraping con
BeautifulSoup) — **no se usa ninguna API REST comercial de trading o noticias.**

## Estructura del proyecto

```
BACKTESTING/
├── app.py                     # Punto de entrada Flask
├── config.py                  # Configuración global (credenciales, rutas, pares)
├── models.py                  # Acceso a SQLite (Diario de Trading)
├── requirements.txt
├── routes/
│   ├── auth.py                 # Login hardcodeado + decorador login_required
│   ├── data.py                 # Extracción histórica (yfinance) + export CSV
│   ├── backtest.py             # Orquesta motor de estrategia + análisis de imágenes
│   ├── news.py                 # Panel de noticias (scraping)
│   └── journal.py              # Diario de trading (CRUD + estadísticas)
├── services/
│   ├── data_fetcher.py         # Descarga OHLCV con yfinance
│   ├── strategy_engine.py      # S/R, Fibonacci, ATR, volatilidad, win-rate, TP/SL
│   ├── image_analyzer.py       # OpenCV (líneas horizontales) + Pytesseract (OCR)
│   └── news_scraper.py         # yfinance.Ticker.news + scraping BeautifulSoup
├── templates/                  # Vistas Jinja2 (login, dashboard, módulos)
├── static/
│   ├── css/style.css           # Tema oscuro profesional de trading
│   └── js/                     # Lógica de cada vista (fetch AJAX)
├── uploads/
│   ├── csv/                    # CSVs históricos exportados/subidos
│   └── images/                 # Capturas de mercado subidas para análisis
└── data/app.db                 # SQLite del Diario de Trading (se crea al iniciar)
```

## Requisitos previos

1. **Python 3.10+**
2. **Tesseract OCR** instalado en el sistema (requerido por `pytesseract`):
   - Windows: descargar instalador desde el proyecto oficial `UB-Mannheim/tesseract`
     e instalar. Luego, si no queda en el PATH, agregar en `services/image_analyzer.py`:
     ```python
     pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
     ```

## Instalación

```powershell
cd "BACKTESTING"
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Ejecución local

```powershell
python app.py
```

La app queda disponible en **http://127.0.0.1:5000**

## Credenciales de acceso

- Usuario: `juanpablogiraldoe`
- Contraseña: `juanpge`

## Flujo de uso

1. **Login** con las credenciales indicadas.
2. **Extracción de Datos**: elegir par (EURUSD, BTCUSD, XAUUSD, etc.) y temporalidad,
   consultar histórico (yfinance) y descargar el CSV generado.
3. **Backtesting Scalping**: subir el CSV descargado + hasta 2 imágenes del gráfico
   actual. El motor calcula soportes/resistencias, Fibonacci del último impulso
   (foco en 50%/61.8%), ATR, volatilidad por sesión, win-rate histórico de los
   niveles Fibo y sugerencia de TP/SL. El panel lateral trae noticias del par.
4. **Diario de Trading**: registrar operaciones y ver PnL, win-rate y rachas
   actualizados automáticamente.

## Notas importantes

- Todo el histórico y las noticias provienen de fuentes públicas consultadas vía
  librerías Python (`yfinance`) o scraping (`BeautifulSoup`), nunca de APIs REST
  de pago/comerciales.
- El scraping de noticias es "best-effort": si una fuente cambia su HTML o no
  responde, la app se degrada mostrando lo disponible en vez de fallar.
- La detección de zonas en imágenes (OpenCV/Hough) es heurística y sirve como
  apoyo visual; el análisis cuantitativo (fuente de verdad) es el CSV histórico.
