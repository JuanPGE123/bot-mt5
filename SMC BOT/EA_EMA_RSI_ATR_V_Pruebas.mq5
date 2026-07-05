//+------------------------------------------------------------------+
//|                                          EA_EMA_RSI_ATR.mq5        |
//|  EA senior MQL5 - Cruce EMA + filtro RSI + recuperacion por grid   |
//|  Version 2.0 - SIN STOP LOSS FIJO / GRID DE RECUPERACION           |
//+------------------------------------------------------------------+
#property copyright "EA_EMA_RSI_ATR"
#property version   "2.00"
#property strict

#include <Trade\Trade.mqh>
#include <Trade\SymbolInfo.mqh>
#include <Trade\PositionInfo.mqh>

//====================== ENUMS ========================================
enum ENUM_EVAL_MODE { EVAL_CLOSE_BAR=0, EVAL_INTRATICK=1 };
enum ENUM_SL_TYPE    { SL_PIPS=0, SL_ATR=1 };
enum ENUM_TP_TYPE    { TP_PIPS=0, TP_ATR=1, TP_RR=2 };

//====================== INPUTS =======================================
input string  Inp_Section0        = "===== GENERAL =====";
input long    InpMagicNumber      = 20251106;    // Magic Number
input bool    InpEnableLogs       = true;        // Activar logs Journal
input bool    InpExportCSV        = true;        // Exportar CSV operaciones
input bool    InpDrawObjects      = true;        // Dibujar flechas/objetos

input string  Inp_Section1        = "===== TIMEFRAME/SIMBOLO =====";
input ENUM_TIMEFRAMES InpTF       = PERIOD_M15;  // Timeframe operativo

input string  Inp_Section2        = "===== SESION/DIAS =====";
input int     InpHourStart        = 0;           // Hora inicio sesion (0-23)
input int     InpHourEnd          = 23;          // Hora fin sesion (0-23)
input bool    InpTradeMon         = true;
input bool    InpTradeTue         = true;
input bool    InpTradeWed         = true;
input bool    InpTradeThu         = true;
input bool    InpTradeFri         = true;
input bool    InpTradeSat         = false;
input bool    InpTradeSun         = false;

input string  Inp_Section3        = "===== SEÑALES =====";
input ENUM_EVAL_MODE InpEvalMode  = EVAL_CLOSE_BAR; // Modo evaluacion
input int     InpEMA_Fast         = 20;   // EMA rapida  [rango opt 10-50 step 5]
input int     InpEMA_Slow         = 50;   // EMA lenta   [rango opt 50-200 step 10]
input int     InpRSI_Period       = 14;   // Periodo RSI
input double  InpRSI_Buy          = 50.0; // Umbral RSI compra (cruce EMA es el gatillo principal)
input double  InpRSI_Sell         = 50.0; // Umbral RSI venta  (cruce EMA es el gatillo principal)
input bool    InpOneTradePerBar   = true; // Una operacion nueva de tendencia por vela

input string  Inp_Section4        = "===== FILTROS (NO BLOQUEANTES) =====";
input bool    InpUseTrendFilter   = true;  // EMA200 como potenciador de direccion (no bloquea)
input int     InpEMA_Trend        = 200;   // Periodo EMA tendencia
input double  InpAgainstTrendLotFactor = 0.5; // Factor de lote si entra contra tendencia
input bool    InpUseVolFilter     = true;  // Filtro ATR (informativo, ya no bloquea)
input int     InpATR_Period       = 14;    // Periodo ATR
input double  InpATR_MinPoints    = 30;    // ATR minimo en puntos (solo log)

input string  Inp_Section4a       = "===== FILTRO ADX (BLOQUEANTE) =====";
input bool    InpUseADXFilter     = true;  // Filtro ADX (bloqueante)
input int     InpADX_Period       = 14;    // Periodo ADX
input double  InpADX_MinLevel     = 14.0;  // ADX minimo obligatorio

input string  Inp_Section4b       = "===== SMC (BLOQUEANTE) =====";
input bool    InpUseSMCFilter     = true;  // Requerir confluencia con OB o FVG
input int     InpSMC_Lookback     = 20;    // Velas hacia atras para buscar FVG/OB
input double  InpSMC_ZoneBufferPts= 5.0;   // Tolerancia en puntos p/ considerar "dentro" de zona

input string  Inp_Section5        = "===== SALIDAS (SIN STOP LOSS FISICO) =====";
input ENUM_TP_TYPE InpTPType      = TP_ATR;  // Tipo TP inicial (posicion unica, antes de grid)
input double  InpTP_Pips          = 600;     // TP en puntos (si TP_PIPS)
input double  InpSL_ATRMult       = 1.2;     // ATR hipotetico SOLO para dimensionar lote (no se envia como SL real)
input double  InpTP_ATRMult       = 2.6;     // Multiplicador ATR TP [opt 1.5-3.5 step 0.1]
input double  InpTP_RR            = 2.2;     // Ratio riesgo/beneficio (si TP_RR, usa SL hipotetico)

input bool    InpUseTrailing      = false;   // Desactivado: dependia de SL fijo
input double  InpTrailStartPts    = 300;     // (sin uso, se deja por compatibilidad de inputs)
input double  InpTrailStepPts     = 100;     // (sin uso, se deja por compatibilidad de inputs)

input bool    InpUseBreakEven     = false;   // Desactivado: dependia de SL fijo
input double  InpBE_ATRMult       = 0.6;     // (sin uso, se deja por compatibilidad de inputs)
input double  InpBE_LockPts       = 15;      // (sin uso, se deja por compatibilidad de inputs)

input bool    InpUsePartialClose  = false;   // Desactivado: el RR dependia de la distancia al SL
input double  InpPartialPct       = 50.0;    // (sin uso mientras no haya SL fisico)
input double  InpPartialAtRR      = 1.0;     // (sin uso mientras no haya SL fisico)

input bool    InpUseTimeExit      = false;   // Salida por tiempo maximo
input int     InpMaxBarsInTrade   = 100;     // Barras maximas en trade

input string  Inp_Section6        = "===== RIESGO/EXPOSICION =====";
input double  InpFixedLot         = 0.01;    // Lote fijo base (fallback si el calculo por riesgo falla)
input double  InpRiskPercent      = 1.0;     // Riesgo por operacion (% balance, sobre SL hipotetico)
input int     InpMaxPosSymbol     = 6;       // Max posiciones por simbolo (incluye cesta de recuperacion)
input int     InpMaxPosTotal      = 10;      // Max posiciones totales
input double  InpMinDistancePts   = 0;       // Distancia minima entre ordenes (pts)

input string  Inp_Section6b       = "===== GRID / RECUPERACION (MARTINGALA SUAVE) =====";
input double  InpGridDistanceATRMultiplier = 1.5; // Distancia en contra (x ATR) para abrir posicion de recuperacion
input double  InpMartingaleMultiplier      = 1.5; // Multiplicador de lote de cada posicion de recuperacion
input int     InpMaxRecoveryTrades         = 3;   // Maximo de operaciones de recuperacion por cesta
input double  InpBasketTP_ATRMult          = 0.2; // TP conjunto: X*ATR sobre el precio medio ponderado

input string  Inp_Section7        = "===== EJECUCION =====";
input int     InpSlippagePts      = 2;       // Slippage maximo (puntos)
input int     InpMaxSpreadPts     = 200;     // Spread maximo (puntos)
input int     InpMaxRetries       = 3;       // Reintentos en error de trading
input int     InpRetryDelayMs     = 500;     // Delay entre reintentos (ms)
input int     InpGridThrottleMs   = 200;     // Intervalo minimo (ms) entre chequeos de grid recovery

input string  Inp_Section8        = "===== REGLAS ESPECIALES =====";
input int     InpMaxConsecLosses  = 4;       // Pausa tras N perdidas seguidas
input int     InpBarsWaitAfterClose = 1;     // Esperar N velas tras cierre para reentrar

//====================== GLOBALES =====================================
CTrade         trade;
CSymbolInfo    symbolInfo;
CPositionInfo  positionInfo;

int handleEMA_Fast, handleEMA_Slow, handleEMA_Trend, handleRSI, handleATR, handleADX;
datetime lastBarTime      = 0;
datetime lastSignalBar    = 0;
datetime lastCloseBarTime = 0;
int      consecutiveLosses = 0;
int      csvHandle = INVALID_HANDLE;
string   csvFileName;
int      g_recoveryCount = 0;   // operaciones de recuperacion abiertas en la cesta actual

//+------------------------------------------------------------------+
//| Estructura para tracking break-even/parciales por ticket           |
//+------------------------------------------------------------------+
struct PosState
  {
   ulong  ticket;
   bool   beDone;
   bool   partialDone;
   datetime openTime;
  };
PosState g_states[];

//+------------------------------------------------------------------+
//| OnInit                                                             |
//+------------------------------------------------------------------+
int OnInit()
  {
   symbolInfo.Name(_Symbol);
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetDeviationInPoints(InpSlippagePts);
   trade.SetTypeFillingBySymbol(_Symbol);

   handleEMA_Fast  = iMA(_Symbol, InpTF, InpEMA_Fast, 0, MODE_EMA, PRICE_CLOSE);
   handleEMA_Slow  = iMA(_Symbol, InpTF, InpEMA_Slow, 0, MODE_EMA, PRICE_CLOSE);
   handleEMA_Trend = iMA(_Symbol, InpTF, InpEMA_Trend, 0, MODE_EMA, PRICE_CLOSE);
   handleRSI       = iRSI(_Symbol, InpTF, InpRSI_Period, PRICE_CLOSE);
   handleATR       = iATR(_Symbol, InpTF, InpATR_Period);
   handleADX       = iADX(_Symbol, InpTF, InpADX_Period);

   if(handleEMA_Fast==INVALID_HANDLE || handleEMA_Slow==INVALID_HANDLE ||
      handleEMA_Trend==INVALID_HANDLE || handleRSI==INVALID_HANDLE || handleATR==INVALID_HANDLE ||
      handleADX==INVALID_HANDLE)
     {
      Print("Error creando indicadores: ", GetLastError());
      return(INIT_FAILED);
     }

   if(InpExportCSV)
     {
      csvFileName = "EA_EMA_RSI_ATR_" + _Symbol + "_" + IntegerToString((int)InpMagicNumber) + ".csv";
      csvHandle = FileOpen(csvFileName, FILE_WRITE|FILE_CSV|FILE_ANSI, ';');
      if(csvHandle != INVALID_HANDLE)
        {
         FileWrite(csvHandle, "Ticket","Simbolo","Tipo","Volumen","PrecioApertura","PrecioCierre","SL","TP","Profit","AperturaTime","CierreTime");
        }
      else
         Log("No se pudo crear CSV: " + IntegerToString(GetLastError()));
     }

   ArrayResize(g_states, 0);
   g_recoveryCount = 0;
   Log("EA inicializado correctamente. Modo SIN STOP LOSS + Grid de recuperacion.");
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| OnDeinit                                                           |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   if(csvHandle != INVALID_HANDLE)
      FileClose(csvHandle);

   IndicatorRelease(handleEMA_Fast);
   IndicatorRelease(handleEMA_Slow);
   IndicatorRelease(handleEMA_Trend);
   IndicatorRelease(handleRSI);
   IndicatorRelease(handleATR);
   IndicatorRelease(handleADX);

   if(InpDrawObjects)
      ObjectsDeleteAll(0, "EA_EMA_RSI_ATR_");

   Log("EA finalizado. Razon: " + IntegerToString(reason));
  }

//+------------------------------------------------------------------+
//| OnTick                                                             |
//+------------------------------------------------------------------+
void OnTick()
  {
   ulong t0 = GetMicrosecondCount();

   if(!symbolInfo.RefreshRates())
      return;

   ManageOpenPositions();

   bool isNewBar = IsNewBar();
   if(InpEvalMode==EVAL_CLOSE_BAR && !isNewBar)
      return;

   if(!IsTradeAllowedNow())
      return;

   if(!CheckSpread())
      return;

   if(consecutiveLosses >= InpMaxConsecLosses)
     {
      Log("Pausado por " + IntegerToString(consecutiveLosses) + " perdidas consecutivas.");
      return;
     }

   if(InpOneTradePerBar && lastSignalBar == iTime(_Symbol, InpTF, 0))
      return;

   if(!ReentryDelayElapsed())
      return;

   ulong tSignalStart = GetMicrosecondCount();
   double lotFactor = 1.0;
   int signal = GetSignal(lotFactor);
   ulong tSignalEnd = GetMicrosecondCount();
   if(InpEnableLogs)
      Log(StringFormat("PERF GetSignal=%d us", (int)(tSignalEnd - tSignalStart)));

   if(signal == 0)
      return;

   int openDir = GetOpenPositionDirection(_Symbol);

   // ---- Salida por señal inversa (cierre por giro) ----
   if(openDir != 0 && openDir != signal)
     {
      Log("Señal inversa detectada. Cerrando cesta actual antes de reabrir.");
      CloseBasket(_Symbol);
      openDir = 0;
     }

   if(openDir != 0)
      return; // ya hay posicion en la misma direccion, el grid se gestiona en ManageOpenPositions

   if(CountOpenPositions(_Symbol) >= InpMaxPosSymbol)
      return;
   if(CountOpenPositions(NULL) >= InpMaxPosTotal)
      return;

   double lot = CalcInitialLot() * lotFactor;

   ulong tSendStart = GetMicrosecondCount();
   OpenPosition(signal == 1 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL, lot, false);
   ulong tSendEnd = GetMicrosecondCount();

   if(InpEnableLogs)
      Log(StringFormat("PERF OpenPosition=%d us total_tick=%d us", (int)(tSendEnd - tSendStart), (int)(tSendEnd - t0)));
  }

//+------------------------------------------------------------------+
//| Detecta nueva barra                                                 |
//+------------------------------------------------------------------+
bool IsNewBar()
  {
   datetime t = iTime(_Symbol, InpTF, 0);
   if(t != lastBarTime)
     {
      lastBarTime = t;
      return(true);
     }
   return(false);
  }

//+------------------------------------------------------------------+
//| Validaciones de sesion/dias/mercado                                 |
//+------------------------------------------------------------------+
bool IsTradeAllowedNow()
  {
   if(!MQLInfoInteger(MQL_TRADE_ALLOWED))
      return(false);
   if(symbolInfo.TradeMode() == SYMBOL_TRADE_MODE_DISABLED)
     {
      Log("Trading deshabilitado para el simbolo.");
      return(false);
     }

   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);

   switch(dt.day_of_week)
     {
      case 0: if(!InpTradeSun) return(false); break;
      case 1: if(!InpTradeMon) return(false); break;
      case 2: if(!InpTradeTue) return(false); break;
      case 3: if(!InpTradeWed) return(false); break;
      case 4: if(!InpTradeThu) return(false); break;
      case 5: if(!InpTradeFri) return(false); break;
      case 6: if(!InpTradeSat) return(false); break;
     }

   int hour = dt.hour;
   if(InpHourStart <= InpHourEnd)
     {
      if(hour < InpHourStart || hour > InpHourEnd)
         return(false);
     }
   else // sesion cruza medianoche
     {
      if(hour < InpHourStart && hour > InpHourEnd)
         return(false);
     }
   return(true);
  }

//+------------------------------------------------------------------+
//| Chequeo de spread maximo                                            |
//+------------------------------------------------------------------+
bool CheckSpread()
  {
   long spread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(spread > InpMaxSpreadPts)
     {
      Log("Spread excesivo: " + IntegerToString(spread));
      return(false);
     }
   return(true);
  }

//+------------------------------------------------------------------+
//| Espera N velas tras cierre para reentrar                            |
//+------------------------------------------------------------------+
bool ReentryDelayElapsed()
  {
   if(lastCloseBarTime == 0)
      return(true);
   int barsElapsed = iBarShift(_Symbol, InpTF, lastCloseBarTime) - iBarShift(_Symbol, InpTF, TimeCurrent());
   if(barsElapsed < InpBarsWaitAfterClose)
      return(false);
   return(true);
  }

//+------------------------------------------------------------------+
//| Cuenta posiciones abiertas (symbol=NULL => todas)                  |
//+------------------------------------------------------------------+
int CountOpenPositions(string symbol)
  {
   int count = 0;
   for(int i = PositionsTotal()-1; i >= 0; i--)
     {
      if(!positionInfo.SelectByIndex(i)) continue;
      if(positionInfo.Magic() != InpMagicNumber) continue;
      if(symbol != NULL && positionInfo.Symbol() != symbol) continue;
      count++;
     }
   return(count);
  }

//+------------------------------------------------------------------+
//| Direccion de la cesta abierta actual: 0 ninguna, 1 buy, -1 sell     |
//+------------------------------------------------------------------+
int GetOpenPositionDirection(string symbol)
  {
   for(int i = PositionsTotal()-1; i >= 0; i--)
     {
      if(!positionInfo.SelectByIndex(i)) continue;
      if(positionInfo.Magic() != InpMagicNumber) continue;
      if(positionInfo.Symbol() != symbol) continue;
      return(positionInfo.PositionType() == POSITION_TYPE_BUY ? 1 : -1);
     }
   return(0);
  }

//+------------------------------------------------------------------+
//| Cierra todas las posiciones de la cesta (symbol+magic)              |
//+------------------------------------------------------------------+
void CloseBasket(string symbol)
  {
   for(int i = PositionsTotal()-1; i >= 0; i--)
     {
      if(!positionInfo.SelectByIndex(i)) continue;
      if(positionInfo.Magic() != InpMagicNumber) continue;
      if(positionInfo.Symbol() != symbol) continue;
      trade.PositionClose(positionInfo.Ticket());
     }
   g_recoveryCount = 0;
  }

//+------------------------------------------------------------------+
//| Detecta confluencia SMC: FVG (brecha vela1/vela3) o OB reciente     |
//| dir: 1=buscar zona alcista (para BUY), -1=zona bajista (para SELL)  |
//| Usa CopyHigh/Low/Open/Close (CopyRates/MqlRates prohibido en EA)    |
//+------------------------------------------------------------------+
bool IsSMCConfluence(int dir)
  {
   int n = InpSMC_Lookback;
   double high[], low[], open[], close[];
   ArraySetAsSeries(high, true);
   ArraySetAsSeries(low, true);
   ArraySetAsSeries(open, true);
   ArraySetAsSeries(close, true);

   if(CopyHigh(_Symbol, InpTF, 1, n, high) < n)  return(false);
   if(CopyLow(_Symbol, InpTF, 1, n, low)   < n)  return(false);
   if(CopyOpen(_Symbol, InpTF, 1, n, open) < n)  return(false);
   if(CopyClose(_Symbol, InpTF, 1, n, close) < n) return(false);

   double point   = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double buffer  = InpSMC_ZoneBufferPts * point;
   double currentPrice = (dir == 1) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                                     : SymbolInfoDouble(_Symbol, SYMBOL_BID);

   // --- FVG: candle[i] (vela3, mas antigua), candle[i-1] (vela2, impulso), candle[i-2] (vela1, mas nueva) ---
   // Indices: high[0]=ultima vela cerrada ... high[n-1]=mas antigua (serie invertida)
   for(int i = 2; i < n; i++)
     {
      if(dir == 1)
        {
         // FVG alcista: low de vela1 (mas nueva) > high de vela3 (mas antigua)
         double gapLow  = high[i];      // techo del gap (vela3)
         double gapHigh = low[i-2];     // piso del gap (vela1)
         if(gapHigh > gapLow)
           {
            if(currentPrice <= gapHigh + buffer && currentPrice >= gapLow - buffer)
               return(true); // precio mitigando FVG alcista
           }
        }
      else // dir == -1
        {
         // FVG bajista: high de vela1 (mas nueva) < low de vela3 (mas antigua)
         double gapHigh = low[i];       // piso del gap (vela3)
         double gapLow  = high[i-2];    // techo del gap (vela1)
         if(gapHigh > gapLow)
           {
            if(currentPrice >= gapLow - buffer && currentPrice <= gapHigh + buffer)
               return(true); // precio mitigando FVG bajista
           }
        }
     }

   // --- Order Block: ultima vela contraria antes de impulso fuerte ---
   for(int i = 1; i < n - 1; i++)
     {
      bool isBearish = close[i] < open[i];
      bool isBullish = close[i] > open[i];

      if(dir == 1 && isBearish)
        {
         // impulso alcista posterior: vela i-1 debe romper el high de la vela bajista (OB)
         if(close[i-1] > high[i])
           {
            double obLow  = low[i];
            double obHigh = high[i];
            if(currentPrice >= obLow - buffer && currentPrice <= obHigh + buffer)
               return(true); // precio reaccionando en OB alcista
           }
        }
      if(dir == -1 && isBullish)
        {
         // impulso bajista posterior: vela i-1 debe romper el low de la vela alcista (OB)
         if(close[i-1] < low[i])
           {
            double obLow  = low[i];
            double obHigh = high[i];
            if(currentPrice >= obLow - buffer && currentPrice <= obHigh + buffer)
               return(true); // precio reaccionando en OB bajista
           }
        }
     }

   return(false); // sin confluencia SMC
  }

//+------------------------------------------------------------------+
//| Logica de señal: cruce EMA + RSI, EMA200 como potenciador           |
//| return 1 = BUY, -1 = SELL, 0 = sin señal                            |
//| lotFactor: 1.0 normal, InpAgainstTrendLotFactor si va contra EMA200 |
//+------------------------------------------------------------------+
int GetSignal(double &lotFactor)
  {
   lotFactor = 1.0;
   // Arreglos dinamicos: requerido para que MQL5 los trate como serie temporal real.
   double emaFast[], emaSlow[], emaTrend[], rsi[], atr[];
   // ArraySetAsSeries fuerza indice[0]=vela actual en formacion, [1]=ultima cerrada, [2]=anterior a esa.
   ArraySetAsSeries(emaFast, true);
   ArraySetAsSeries(emaSlow, true);
   ArraySetAsSeries(emaTrend, true);
   ArraySetAsSeries(rsi, true);
   ArraySetAsSeries(atr, true);

   // CopyBuffer llena el arreglo desde el handle del indicador; con la serie ya fijada,
   // [0]=vela en formacion, [1]=ultima cerrada, [2]=cerrada previa (usadas para el cruce).
   if(CopyBuffer(handleEMA_Fast, 0, 0, 3, emaFast) < 3) return(0);
   if(CopyBuffer(handleEMA_Slow, 0, 0, 3, emaSlow) < 3) return(0);
   if(CopyBuffer(handleRSI, 0, 0, 2, rsi) < 2) return(0);
   if(CopyBuffer(handleATR, 0, 0, 2, atr) < 2) return(0);

   // Usamos vela cerrada (indice 1) para evitar repintado
   bool crossUp   = (emaFast[2] <= emaSlow[2]) && (emaFast[1] > emaSlow[1]);
   bool crossDown = (emaFast[2] >= emaSlow[2]) && (emaFast[1] < emaSlow[1]);

   if(!crossUp && !crossDown)
      return(0);

   if(InpUseVolFilter)
     {
      double atrPoints = atr[1] / SymbolInfoDouble(_Symbol, SYMBOL_POINT);
      if(atrPoints < InpATR_MinPoints)
         Log("DEBUG ATR bajo (" + DoubleToString(atrPoints,1) + " pts), no bloquea entrada.");
     }

   if(InpUseADXFilter)
     {
      double adxMain[];
      ArraySetAsSeries(adxMain, true); // [1]=ultima vela cerrada del ADX
      if(CopyBuffer(handleADX, 0, 0, 2, adxMain) < 2)
         return(0); // sin dato ADX, no arriesga entrada
      if(adxMain[1] < InpADX_MinLevel)
        {
         Log("DEBUG ADX bajo (" + DoubleToString(adxMain[1],1) + "), BLOQUEA entrada.");
         return(0); // bloqueo real, ya no informativo
        }
     }

   Log(StringFormat("DEBUG cruce=%s rsi=%.2f emaFast1=%.5f emaSlow1=%.5f atrPts=%.1f",
       crossUp ? "UP":"DOWN", rsi[1], emaFast[1], emaSlow[1],
       atr[1]/SymbolInfoDouble(_Symbol, SYMBOL_POINT)));

   double trendPrice = 0;
   bool trendReady = false;
   if(InpUseTrendFilter && CopyBuffer(handleEMA_Trend, 0, 0, 2, emaTrend) == 2)
     {
      // Lectura de precio exacto via CopyClose (prohibido CopyRates/MqlRates); mismo orden de serie que arriba.
      double closePrice[];
      ArraySetAsSeries(closePrice, true);
      if(CopyClose(_Symbol, InpTF, 0, 2, closePrice) == 2)
        {
         trendPrice = closePrice[1]; // ultima vela cerrada, coherente con emaTrend[1]
         trendReady = true;
        }
     }

   if(crossUp && rsi[1] >= InpRSI_Buy)
     {
      if(InpUseSMCFilter && !IsSMCConfluence(1))
        {
         Log("DEBUG BUY descartado: sin confluencia SMC (FVG/OB) cercana.");
         return(0);
        }
      if(trendReady && trendPrice < emaTrend[1])
        {
         Log(StringFormat("DEBUG BUY contra tendencia (close=%.5f < ema200=%.5f), reduce lote.", trendPrice, emaTrend[1]));
         lotFactor = InpAgainstTrendLotFactor;
        }
      return(1);
     }
   if(crossDown && rsi[1] <= InpRSI_Sell)
     {
      if(InpUseSMCFilter && !IsSMCConfluence(-1))
        {
         Log("DEBUG SELL descartado: sin confluencia SMC (FVG/OB) cercana.");
         return(0);
        }
      if(trendReady && trendPrice > emaTrend[1])
        {
         Log(StringFormat("DEBUG SELL contra tendencia (close=%.5f > ema200=%.5f), reduce lote.", trendPrice, emaTrend[1]));
         lotFactor = InpAgainstTrendLotFactor;
        }
      return(-1);
     }
   return(0);
  }

//+------------------------------------------------------------------+
//| Calcula TP inicial en precio (posicion unica, sin SL fisico)        |
//+------------------------------------------------------------------+
double CalcInitialTP(ENUM_ORDER_TYPE type, double entryPrice)
  {
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double atr[];
   ArraySetAsSeries(atr, true); // serie temporal: [0]=ultima vela cerrada solicitada (shift 1 real)
   CopyBuffer(handleATR, 0, 1, 1, atr);
   double atrVal = atr[0];

   double hypotheticalSLDist = atrVal * InpSL_ATRMult; // solo para RR, no se envia
   double tpDist;

   if(InpTPType == TP_ATR)
      tpDist = atrVal * InpTP_ATRMult;
   else if(InpTPType == TP_RR)
      tpDist = hypotheticalSLDist * InpTP_RR;
   else
      tpDist = InpTP_Pips * point;

   double tp = (type == ORDER_TYPE_BUY) ? entryPrice + tpDist : entryPrice - tpDist;
   return(NormalizeDouble(tp, (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS)));
  }

//+------------------------------------------------------------------+
//| Valida distancia minima del TP frente al StopLevel del broker       |
//+------------------------------------------------------------------+
bool ValidateStopLevel(ENUM_ORDER_TYPE type, double entryPrice, double tp)
  {
   if(tp <= 0) return(true);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   long stopLevelPts = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double minDist = stopLevelPts * point;

   if(minDist <= 0) return(true);

   if(type == ORDER_TYPE_BUY)
      return((tp - entryPrice) >= minDist);
   else
      return((entryPrice - tp) >= minDist);
  }

//+------------------------------------------------------------------+
//| Lote inicial: riesgo % sobre SL hipotetico (ATR), con fallback fijo |
//+------------------------------------------------------------------+
double CalcInitialLot()
  {
   double atr[];
   ArraySetAsSeries(atr, true); // serie temporal para el ATR usado en dimensionamiento de lote
   if(CopyBuffer(handleATR, 0, 1, 1, atr) < 1)
      return(InpFixedLot);

   double hypotheticalSLDist = atr[0] * InpSL_ATRMult;
   if(hypotheticalSLDist <= 0)
      return(InpFixedLot);

   double balance   = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskMoney = balance * (InpRiskPercent / 100.0);

   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);

   if(tickSize <= 0 || tickValue <= 0)
      return(InpFixedLot);

   double lossPerLot = (hypotheticalSLDist / tickSize) * tickValue;
   if(lossPerLot <= 0)
      return(InpFixedLot);

   double lot = riskMoney / lossPerLot;

   double lotMin  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double lotMax  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

   if(lotStep <= 0)
      return(InpFixedLot);

   lot = MathFloor(lot / lotStep) * lotStep;
   lot = MathMax(lotMin, MathMin(lotMax, lot));

   if(lot < lotMin)
      return(InpFixedLot);

   return(NormalizeDouble(lot, 2));
  }

//+------------------------------------------------------------------+
//| Normaliza lote a los limites/step del broker                        |
//+------------------------------------------------------------------+
double NormalizeLot(double lot)
  {
   double lotMin  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double lotMax  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(lotStep <= 0) lotStep = 0.01;

   lot = MathFloor(lot / lotStep) * lotStep;
   lot = MathMax(lotMin, MathMin(lotMax, lot));
   return(NormalizeDouble(lot, 2));
  }

//+------------------------------------------------------------------+
//| Abre posicion con reintentos prudentes. SL=0 siempre.                |
//| isRecovery=true => operacion de la cesta de recuperacion (sin TP    |
//| individual, el TP conjunto lo fija ManageRecoveryGrid)               |
//+------------------------------------------------------------------+
void OpenPosition(ENUM_ORDER_TYPE type, double lot, bool isRecovery)
  {
   lot = NormalizeLot(lot);

   symbolInfo.RefreshRates();
   double price = (type == ORDER_TYPE_BUY) ? symbolInfo.Ask() : symbolInfo.Bid();

   double tp = isRecovery ? 0.0 : CalcInitialTP(type, price);

   if(!isRecovery && !ValidateStopLevel(type, price, tp))
     {
      Log("TP dentro de StopLevel minimo del broker. Cancelado.");
      return;
     }

   if(!CheckMoneyForTrade(type, lot, price))
     {
      Log("Margen insuficiente para abrir posicion.");
      return;
     }

   bool success = false;
   for(int attempt = 1; attempt <= InpMaxRetries && !success; attempt++)
     {
      symbolInfo.RefreshRates();
      price = (type == ORDER_TYPE_BUY) ? symbolInfo.Ask() : symbolInfo.Bid();
      if(!isRecovery)
        {
         tp = CalcInitialTP(type, price);
         if(!ValidateStopLevel(type, price, tp))
           {
            Log("StopLevel invalido tras refresh en intento " + IntegerToString(attempt) + ". Reintentando.");
            Sleep(InpRetryDelayMs);
            continue;
           }
        }

      if(type == ORDER_TYPE_BUY)
         success = trade.Buy(lot, _Symbol, price, 0, tp, "EA_EMA_RSI_ATR");
      else
         success = trade.Sell(lot, _Symbol, price, 0, tp, "EA_EMA_RSI_ATR");

      if(!success)
        {
         int err = GetLastError();
         Log("Intento " + IntegerToString(attempt) + " fallido. Error: " + IntegerToString(err));
         ResetLastError();
         Sleep(InpRetryDelayMs);
        }
     }

   if(success)
     {
      if(!isRecovery)
         lastSignalBar = iTime(_Symbol, InpTF, 0);
      else
         g_recoveryCount++;

      ulong ticket = trade.ResultOrder();
      RegisterPositionState(ticket);
      if(InpDrawObjects)
         DrawEntryArrow(type, price);
      Log((isRecovery ? "Posicion RECOVERY abierta: " : "Posicion abierta: ") + EnumToString(type) +
          " lote=" + DoubleToString(lot,2) + " SL=0 TP=" + DoubleToString(tp,_Digits));
     }
   else
      Log("No se pudo abrir posicion tras " + IntegerToString(InpMaxRetries) + " intentos.");
  }

//+------------------------------------------------------------------+
//| Verifica margen disponible antes de operar                          |
//+------------------------------------------------------------------+
bool CheckMoneyForTrade(ENUM_ORDER_TYPE type, double lot, double price)
  {
   double marginRequired;
   if(!OrderCalcMargin(type, _Symbol, lot, price, marginRequired))
      return(false);
   double freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   return(freeMargin >= marginRequired);
  }

//+------------------------------------------------------------------+
//| Registro de estado por ticket (BE/parcial)                          |
//+------------------------------------------------------------------+
void RegisterPositionState(ulong ticket)
  {
   int size = ArraySize(g_states);
   ArrayResize(g_states, size + 1);
   g_states[size].ticket      = ticket;
   g_states[size].beDone      = false;
   g_states[size].partialDone = false;
   g_states[size].openTime    = TimeCurrent();
  }

int FindStateIndex(ulong ticket)
  {
   for(int i = 0; i < ArraySize(g_states); i++)
      if(g_states[i].ticket == ticket)
         return(i);
   return(-1);
  }

//+------------------------------------------------------------------+
//| Elimina estado de ticket cerrado (swap-with-last, evita fuga)      |
//+------------------------------------------------------------------+
void RemoveStateByTicket(ulong ticket)
  {
   int idx = FindStateIndex(ticket);
   if(idx < 0)
      return;
   int last = ArraySize(g_states) - 1;
   g_states[idx] = g_states[last];
   ArrayResize(g_states, last);
  }

//+------------------------------------------------------------------+
//| Gestion de posiciones abiertas: grid recovery, TP conjunto, time-exit|
//+------------------------------------------------------------------+
void ManageOpenPositions()
  {
   for(int i = PositionsTotal()-1; i >= 0; i--)
     {
      if(!positionInfo.SelectByIndex(i)) continue;
      if(positionInfo.Magic() != InpMagicNumber) continue;
      if(positionInfo.Symbol() != _Symbol) continue;

      ulong ticket = positionInfo.Ticket();
      int idx = FindStateIndex(ticket);
      if(idx < 0)
        {
         RegisterPositionState(ticket);
         idx = FindStateIndex(ticket);
        }

      // ---- Time exit ----
      if(InpUseTimeExit)
        {
         int barsOpen = iBarShift(_Symbol, InpTF, g_states[idx].openTime) - iBarShift(_Symbol, InpTF, TimeCurrent());
         if(barsOpen >= InpMaxBarsInTrade)
           {
            trade.PositionClose(ticket);
            Log("Cierre por tiempo maximo ticket " + IntegerToString((int)ticket));
           }
        }
     }

   // Throttle: evita CopyBuffer+PositionModify en cada tick con alta frecuencia
   static uint lastGridCheckMs = 0;
   uint nowMs = GetTickCount();
   if(nowMs - lastGridCheckMs >= InpGridThrottleMs)
     {
      ManageRecoveryGrid();
      lastGridCheckMs = nowMs;
     }

   CheckClosedPositionsForHistory();
  }

//+------------------------------------------------------------------+
//| Grid de recuperacion: abre lote martingala si el precio va en      |
//| contra por InpGridDistanceATRMultiplier*ATR y fija TP conjunto      |
//| sobre el precio medio ponderado de toda la cesta.                   |
//+------------------------------------------------------------------+
void ManageRecoveryGrid()
  {
   int count = 0;
   double totalVolume = 0, weightedPrice = 0, lastLot = 0;
   datetime lastOpenTime = 0;
   ENUM_POSITION_TYPE posType = POSITION_TYPE_BUY;
   ulong tickets[];

   for(int i = PositionsTotal()-1; i >= 0; i--)
     {
      if(!positionInfo.SelectByIndex(i)) continue;
      if(positionInfo.Magic() != InpMagicNumber) continue;
      if(positionInfo.Symbol() != _Symbol) continue;

      double vol   = positionInfo.Volume();
      double entry = positionInfo.PriceOpen();
      totalVolume  += vol;
      weightedPrice += entry * vol;
      posType = positionInfo.PositionType();

      if(positionInfo.Time() >= lastOpenTime)
        {
         lastOpenTime = positionInfo.Time();
         lastLot = vol;
        }

      int sz = ArraySize(tickets);
      ArrayResize(tickets, sz + 1);
      tickets[sz] = positionInfo.Ticket();
      count++;
     }

   if(count == 0)
     {
      g_recoveryCount = 0;
      return;
     }

   double avgPrice = weightedPrice / totalVolume;
   double curPrice = (posType == POSITION_TYPE_BUY) ? symbolInfo.Bid() : symbolInfo.Ask();

   double atr[];
   ArraySetAsSeries(atr, true); // serie temporal para el ATR usado en el grid de recuperacion
   if(CopyBuffer(handleATR, 0, 1, 1, atr) < 1)
      return;
   double atrVal = atr[0];
   if(atrVal <= 0)
      return;

   // ---- Abrir posicion de recuperacion si la cesta va en contra ----
   double adverseDist = (posType == POSITION_TYPE_BUY) ? (avgPrice - curPrice) : (curPrice - avgPrice);
   if(adverseDist >= atrVal * InpGridDistanceATRMultiplier && g_recoveryCount < InpMaxRecoveryTrades)
     {
      double newLot = NormalizeLot(lastLot * InpMartingaleMultiplier);
      Log(StringFormat("Grid recovery #%d: adverso=%.5f (>=%.5f). Lote nuevo=%.2f",
          g_recoveryCount+1, adverseDist, atrVal*InpGridDistanceATRMultiplier, newLot));
      OpenPosition(posType == POSITION_TYPE_BUY ? ORDER_TYPE_BUY : ORDER_TYPE_SELL, newLot, true);
      return; // recalculo de cesta se hace en el siguiente tick, ya con la nueva posicion incluida
     }

   // ---- TP conjunto sobre precio medio ponderado ----
   double tpDist = atrVal * InpBasketTP_ATRMult;
   double basketTP = (posType == POSITION_TYPE_BUY) ? (avgPrice + tpDist) : (avgPrice - tpDist);
   basketTP = NormalizeDouble(basketTP, (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS));

   for(int t = 0; t < ArraySize(tickets); t++)
     {
      if(!positionInfo.SelectByTicket(tickets[t])) continue;
      if(MathAbs(positionInfo.TakeProfit() - basketTP) > SymbolInfoDouble(_Symbol, SYMBOL_POINT))
         trade.PositionModify(tickets[t], 0, basketTP);
     }
  }

//+------------------------------------------------------------------+
//| Revisa historial reciente para CSV, flechas de salida y racha       |
//+------------------------------------------------------------------+
void CheckClosedPositionsForHistory()
  {
   static datetime lastCheck = 0;
   datetime from = (lastCheck == 0) ? TimeCurrent() - 3600 : lastCheck;
   if(!HistorySelect(from, TimeCurrent() + 60))
      return;

   int total = HistoryDealsTotal();
   for(int i = 0; i < total; i++)
     {
      ulong dealTicket = HistoryDealGetTicket(i);
      if(dealTicket == 0) continue;
      if((long)HistoryDealGetInteger(dealTicket, DEAL_MAGIC) != InpMagicNumber) continue;
      if(HistoryDealGetInteger(dealTicket, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;

      datetime dealTime = (datetime)HistoryDealGetInteger(dealTicket, DEAL_TIME);
      if(dealTime <= lastCheck) continue;

      double profit = HistoryDealGetDouble(dealTicket, DEAL_PROFIT);
      double price  = HistoryDealGetDouble(dealTicket, DEAL_PRICE);
      double volume = HistoryDealGetDouble(dealTicket, DEAL_VOLUME);
      ulong  posId  = HistoryDealGetInteger(dealTicket, DEAL_POSITION_ID);

      if(profit < 0)
         consecutiveLosses++;
      else if(profit > 0)
         consecutiveLosses = 0;

      RemoveStateByTicket(posId);
      lastCloseBarTime = iTime(_Symbol, InpTF, 0);

      if(InpDrawObjects)
         DrawExitMarker(price, profit);

      if(InpExportCSV && csvHandle != INVALID_HANDLE)
        {
         FileWrite(csvHandle, posId, _Symbol,
                   EnumToString((ENUM_DEAL_TYPE)HistoryDealGetInteger(dealTicket, DEAL_TYPE)),
                   volume, "", DoubleToString(price,_Digits), "", "",
                   DoubleToString(profit,2), "", TimeToString(dealTime, TIME_DATE|TIME_SECONDS));
         FileFlush(csvHandle);
        }

      Log("Operacion cerrada. Profit=" + DoubleToString(profit,2) +
          " Racha perdidas=" + IntegerToString(consecutiveLosses));
     }
   lastCheck = TimeCurrent();

   if(CountOpenPositions(_Symbol) == 0)
      g_recoveryCount = 0;
  }

//+------------------------------------------------------------------+
//| Dibuja flecha de entrada                                            |
//+------------------------------------------------------------------+
void DrawEntryArrow(ENUM_ORDER_TYPE type, double price)
  {
   string name = "EA_EMA_RSI_ATR_ENTRY_" + IntegerToString((int)TimeCurrent()) + "_" + IntegerToString(MathRand());
   int code = (type == ORDER_TYPE_BUY) ? 233 : 234;
   color clr = (type == ORDER_TYPE_BUY) ? clrLime : clrRed;

   ObjectCreate(0, name, OBJ_ARROW, 0, TimeCurrent(), price);
   ObjectSetInteger(0, name, OBJPROP_ARROWCODE, code);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 2);
  }

//+------------------------------------------------------------------+
//| Dibuja marcador de salida                                           |
//+------------------------------------------------------------------+
void DrawExitMarker(double price, double profit)
  {
   string name = "EA_EMA_RSI_ATR_EXIT_" + IntegerToString((int)TimeCurrent()) + "_" + IntegerToString(MathRand());
   color clr = (profit >= 0) ? clrDodgerBlue : clrOrange;

   ObjectCreate(0, name, OBJ_ARROW, 0, TimeCurrent(), price);
   ObjectSetInteger(0, name, OBJPROP_ARROWCODE, 251);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 2);
  }

//+------------------------------------------------------------------+
//| Log condicional al Journal                                          |
//+------------------------------------------------------------------+
void Log(string msg)
  {
   if(InpEnableLogs)
      Print("[EA_EMA_RSI_ATR] ", msg);
  }
//+------------------------------------------------------------------+
