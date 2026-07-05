//+------------------------------------------------------------------+
//|                                                  ScalpingPro.mq5 |
//|                     EA de Scalping de Alta Frecuencia            |
//|                        Con Panel Visual y Filtro EMA 20          |
//+------------------------------------------------------------------+
#property copyright "ScalpingPro"
#property link      ""
#property version   "1.02"
#property strict

#include <Trade\Trade.mqh>

//--- Parámetros de entrada
input double   Input_Volumen_Inicial = 0.01;   // Volumen de lote
input int      Max_Ops_Por_Hora      = 2;      // Máximo de operaciones por hora
input double   TP_Objetivo_USD       = 70.0;   // Take Profit objetivo en USD
input int      Magic_Number          = 123456; // Número mágico del EA
input int      Periodo_EMA           = 20;     // Período de la EMA

//--- Constantes del panel
#define PANEL_NOMBRE   "ScalpingProPanel"
#define PANEL_TITLEBAR "ScalpingProTitleBar"
#define BTN_BUY        "BtnBuyScalping"
#define BTN_SELL       "BtnSellScalping"
#define LBL_TITULO     "LblTituloScalping"
#define LBL_SIMBOLO    "LblSimboloScalping"
#define LBL_VOLUMEN    "LblVolumenScalping"
#define LBL_TIMER      "LblTimerVelaScalping"
#define LBL_OPS        "LblOpsHoraScalping"
#define LBL_LOCK       "LblLockScalping"
#define LBL_TP_STATUS  "LblTpStatusScalping"
#define LBL_EMA        "LblEmaInfoScalping"
#define SEP1           "SepPanel1"
#define SEP2           "SepPanel2"

//--- Variables globales
CTrade   operador;
double   lote_final;
int      handle_ema;
datetime hora_inicio_ventana;
int      ops_en_ventana;

//--- Lock de Max_Ops_Por_Hora (bloqueado 1 hora desde el primer inicio)
int      max_ops_efectivo;     // Valor en uso (bloqueado)
datetime bloqueo_ops_hasta;    // Timestamp fin del bloqueo

//--- Control de TP de sesión
datetime sesion_inicio;        // Momento del OnInit (inicio de sesión)
double   profit_sesion;        // P&L acumulado en deals cerrados esta sesión
bool     tp_sesion_alcanzado;  // true = objetivo cumplido, sin nuevas entradas

//+------------------------------------------------------------------+
//| Inicialización del EA                                            |
//+------------------------------------------------------------------+
int OnInit()
  {
   operador.SetExpertMagicNumber(Magic_Number);
   operador.SetDeviationInPoints(10);
   operador.SetTypeFilling(ORDER_FILLING_IOC);

   //--- Volumen directo desde el input (sin bloqueo por variable global)
   double lote_min  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double lote_max  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lote_step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   lote_final = MathMax(lote_min, MathRound(Input_Volumen_Inicial / lote_step) * lote_step);
   lote_final = MathMin(lote_final, lote_max);

   hora_inicio_ventana  = TimeCurrent();
   ops_en_ventana       = 0;
   sesion_inicio        = TimeCurrent();
   profit_sesion        = 0;
   tp_sesion_alcanzado  = false;

   //--- Lock de Max_Ops_Por_Hora: usa GlobalVariable para sobrevivir re-inits
   string gv_val   = "SP_LockOps_" + IntegerToString(Magic_Number) + "_Val";
   string gv_until = "SP_LockOps_" + IntegerToString(Magic_Number) + "_Until";

   datetime lock_until_stored = (datetime)GlobalVariableGet(gv_until);
   if(GlobalVariableCheck(gv_until) && lock_until_stored > TimeCurrent())
     {
      // Dentro del período de bloqueo: ignorar el input actual y usar el valor guardado
      max_ops_efectivo  = (int)GlobalVariableGet(gv_val);
      bloqueo_ops_hasta = lock_until_stored;
      if(Max_Ops_Por_Hora != max_ops_efectivo)
        {
         int mins_rest = (int)((bloqueo_ops_hasta - TimeCurrent()) / 60);
         Alert(StringFormat("ScalpingPro: Max_Ops_Por_Hora BLOQUEADO en %d op/h por %d min más. Cambio ignorado.",
                            max_ops_efectivo, mins_rest));
        }
     }
   else
     {
      // Primera vez o bloqueo expirado: usar el input y bloquear 1 hora
      max_ops_efectivo  = Max_Ops_Por_Hora;
      bloqueo_ops_hasta = TimeCurrent() + 3600;
      GlobalVariableSet(gv_val,   (double)max_ops_efectivo);
      GlobalVariableSet(gv_until, (double)bloqueo_ops_hasta);
      Print("ScalpingPro: Max_Ops_Por_Hora fijado en ", max_ops_efectivo,
            " | Bloqueado hasta ", TimeToString(bloqueo_ops_hasta, TIME_MINUTES));
     }

   //--- EMA: crear handle y DIBUJAR en el gráfico principal
   handle_ema = iMA(_Symbol, PERIOD_CURRENT, Periodo_EMA, 0, MODE_EMA, PRICE_CLOSE);
   if(handle_ema == INVALID_HANDLE)
     {
      Alert("ScalpingPro ERROR: No se pudo crear EMA ", Periodo_EMA);
      return(INIT_FAILED);
     }
   ChartIndicatorAdd(0, 0, handle_ema); // <-- Dibuja la EMA en el gráfico

   ChartSetInteger(0, CHART_SHOW_ONE_CLICK, false);
   AplicarColoresProfesionales();
   CrearPanel();

   Print("ScalpingPro v1.03 | ", _Symbol, " | Lote: ", lote_final,
         " | EMA", Periodo_EMA, " | Max ops/h: ", max_ops_efectivo,
         " | TP sesión: $", TP_Objetivo_USD);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| Desinicialización del EA                                         |
//+------------------------------------------------------------------+
void OnDeinit(const int razon)
  {
   if(handle_ema != INVALID_HANDLE)
     {
      ChartIndicatorDelete(0, 0, "MA(" + IntegerToString(Periodo_EMA) + ")");
      IndicatorRelease(handle_ema);
     }
   EliminarPanel();
  }

//+------------------------------------------------------------------+
//| Conteo real de ops abiertas del EA en la ventana actual        |
//+------------------------------------------------------------------+
int ContarOpsEnVentana()
  {
   int total = 0;
   datetime limite = hora_inicio_ventana;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL)  != _Symbol)    continue;
      if(PositionGetInteger(POSITION_MAGIC)  != Magic_Number) continue;
      if((datetime)PositionGetInteger(POSITION_TIME) >= limite)
         total++;
     }
   // Historial: posiciones cerradas en la ventana actual
   HistorySelect(limite, TimeCurrent());
   for(int i = HistoryDealsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0) continue;
      if(HistoryDealGetString(ticket, DEAL_SYMBOL)           != _Symbol)      continue;
      if(HistoryDealGetInteger(ticket, DEAL_MAGIC)           != Magic_Number)  continue;
      if(HistoryDealGetInteger(ticket, DEAL_ENTRY)           != DEAL_ENTRY_IN) continue;
      total++;
     }
   return total;
  }

//+------------------------------------------------------------------+
//| Tick principal                                                   |
//+------------------------------------------------------------------+
void OnTick()
  {
   datetime ahora = TimeCurrent();
   if((ahora - hora_inicio_ventana) >= 3600)
     {
      hora_inicio_ventana = ahora;
      ops_en_ventana      = 0;
     }
   ops_en_ventana = ContarOpsEnVentana();

   //--- Verificar TP de sesión (deals cerrados + posiciones abiertas flotantes)
   if(!tp_sesion_alcanzado)
     {
      profit_sesion = CalcProfitSesion();
      if(profit_sesion >= TP_Objetivo_USD)
        {
         tp_sesion_alcanzado = true;
         Print("ScalpingPro: TP DE SESIÓN alcanzado | Profit: $",
               DoubleToString(profit_sesion, 2), " | Objetivo: $", TP_Objetivo_USD);
         Alert("ScalpingPro: ¡Objetivo de sesión $", DoubleToString(TP_Objetivo_USD, 2),
               " alcanzado! No se permiten nuevas operaciones.");
        }
     }
   else
     {
      profit_sesion = CalcProfitSesion();
     }

   ActualizarTimerVela();
   ActualizarContadorOps();
   ActualizarInfoEMA();
   ActualizarEstadoBloqueosPanel();
  }

//+------------------------------------------------------------------+
//| Eventos del gráfico                                              |
//+------------------------------------------------------------------+
void OnChartEvent(const int id, const long &lparam,
                  const double &dparam, const string &sparam)
  {
   if(id != CHARTEVENT_OBJECT_CLICK)
      return;
   if(sparam == BTN_BUY)
     {
      ObjectSetInteger(0, BTN_BUY, OBJPROP_STATE, false);
      EjecutarOrden(ORDER_TYPE_BUY);
     }
   if(sparam == BTN_SELL)
     {
      ObjectSetInteger(0, BTN_SELL, OBJPROP_STATE, false);
      EjecutarOrden(ORDER_TYPE_SELL);
     }
  }

//+------------------------------------------------------------------+
//| Lógica de ejecución de órdenes                                  |
//+------------------------------------------------------------------+
void EjecutarOrden(ENUM_ORDER_TYPE tipo_orden)
  {
   //--- Bloqueo por TP de sesión alcanzado
   if(tp_sesion_alcanzado)
     {
      Alert("ScalpingPro: TP de sesión $", DoubleToString(TP_Objetivo_USD, 2),
            " ya fue alcanzado ($", DoubleToString(profit_sesion, 2), "). Sin nuevas entradas.");
      return;
     }

   if(!VerificarLimiteHorario())
      return;
   if(!VerificarFiltroEMA(tipo_orden))
      return;

   double precio_ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double precio_bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double punto      = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   int    digitos    = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);

   double tick_value      = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tick_size       = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double valor_por_punto = lote_final * tick_value * (punto / tick_size);
   double tp_puntos       = (valor_por_punto > 0) ? MathRound(TP_Objetivo_USD / valor_por_punto) : 700;

   double sl = 0, tp = 0, precio_entrada = 0;
   if(tipo_orden == ORDER_TYPE_BUY)
     {
      precio_entrada = precio_ask;
      tp = NormalizeDouble(precio_ask + tp_puntos * punto, digitos);
     }
   else
     {
      precio_entrada = precio_bid;
      tp = NormalizeDouble(precio_bid - tp_puntos * punto, digitos);
     }

   bool ok = (tipo_orden == ORDER_TYPE_BUY)
             ? operador.Buy(lote_final, _Symbol, precio_entrada, sl, tp, "ScalpingPro BUY")
             : operador.Sell(lote_final, _Symbol, precio_entrada, sl, tp, "ScalpingPro SELL");

   if(ok)
     {
      ops_en_ventana++;
      Print("ScalpingPro: ", (tipo_orden == ORDER_TYPE_BUY ? "BUY" : "SELL"),
            " | Lote:", lote_final, " | TP:", tp, " | Ops/h:", ops_en_ventana);
      ActualizarContadorOps();
     }
   else
     {
      string err = "Error " + IntegerToString(GetLastError());
      Print("ScalpingPro ERROR: ", err);
      Alert("ScalpingPro: ", err);
     }
  }

//+------------------------------------------------------------------+
//| Verificar límite horario de operaciones                         |
//+------------------------------------------------------------------+
bool VerificarLimiteHorario()
  {
   datetime ahora = TimeCurrent();
   if((ahora - hora_inicio_ventana) >= 3600)
     {
      hora_inicio_ventana = ahora;
      ops_en_ventana      = 0;
     }
   if(ops_en_ventana >= max_ops_efectivo)
     {
      int rest = (int)(3600 - (ahora - hora_inicio_ventana));
      Alert("ScalpingPro: LÍMITE HORARIO ", ops_en_ventana, "/", max_ops_efectivo,
            " ops/h. Próxima ventana en ", rest / 60, "m ", rest % 60, "s");
      return false;
     }
   return true;
  }

//+------------------------------------------------------------------+
//| Verificar filtro EMA                                            |
//+------------------------------------------------------------------+
bool VerificarFiltroEMA(ENUM_ORDER_TYPE tipo_orden)
  {
   double buf[];
   ArraySetAsSeries(buf, true);
   if(CopyBuffer(handle_ema, 0, 0, 3, buf) < 3)
      return true;

   double ema   = buf[0];
   double precio = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   if(tipo_orden == ORDER_TYPE_BUY && precio < ema)
     {
      string aviso = "Precio BAJO la EMA" + IntegerToString(Periodo_EMA) +
                     " (" + DoubleToString(ema, _Digits) + ")\n" +
                     "Tendencia BAJISTA.\n\n¿Confirmar BUY contra tendencia?";
      if(MessageBox(aviso, "ScalpingPro - Filtro EMA", MB_YESNO | MB_ICONWARNING) != IDYES)
         return false;
     }
   else if(tipo_orden == ORDER_TYPE_SELL && precio > ema)
     {
      string aviso = "Precio SOBRE la EMA" + IntegerToString(Periodo_EMA) +
                     " (" + DoubleToString(ema, _Digits) + ")\n" +
                     "Tendencia ALCISTA.\n\n¿Confirmar SELL contra tendencia?";
      if(MessageBox(aviso, "ScalpingPro - Filtro EMA", MB_YESNO | MB_ICONWARNING) != IDYES)
         return false;
     }
   return true;
  }

//+------------------------------------------------------------------+
//| CalcProfitSesion: suma P&L de deals cerrados desde sesion_inicio|
//+------------------------------------------------------------------+
double CalcProfitSesion()
  {
   double total = 0;
   HistorySelect(sesion_inicio, TimeCurrent());
   for(int i = HistoryDealsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0) continue;
      if(HistoryDealGetString(ticket, DEAL_SYMBOL)          != _Symbol)       continue;
      if(HistoryDealGetInteger(ticket, DEAL_MAGIC)          != Magic_Number)  continue;
      if(HistoryDealGetInteger(ticket, DEAL_ENTRY)          != DEAL_ENTRY_OUT) continue;
      total += HistoryDealGetDouble(ticket, DEAL_PROFIT)
             + HistoryDealGetDouble(ticket, DEAL_SWAP)
             + HistoryDealGetDouble(ticket, DEAL_COMMISSION);
     }
   return total;
  }

//+------------------------------------------------------------------+
//| ActualizarEstadoBloqueosPanel: refresca etiquetas de lock y TP  |
//+------------------------------------------------------------------+
void ActualizarEstadoBloqueosPanel()
  {
   //--- Etiqueta bloqueo de ops/h
   if(ObjectFind(0, LBL_LOCK) >= 0)
     {
      string txt_lock;
      color  col_lock;
      if(TimeCurrent() < bloqueo_ops_hasta)
        {
         int mins = (int)((bloqueo_ops_hasta - TimeCurrent()) / 60);
         txt_lock = StringFormat("Lock ops: %d/h | %dm restantes", max_ops_efectivo, mins);
         col_lock = clrOrange;
        }
      else
        {
         txt_lock = StringFormat("Ops/h: %d (libre)", max_ops_efectivo);
         col_lock = C'100,160,100';
        }
      ObjectSetString(0,  LBL_LOCK, OBJPROP_TEXT,  txt_lock);
      ObjectSetInteger(0, LBL_LOCK, OBJPROP_COLOR, col_lock);
     }

   //--- Etiqueta TP de sesión
   if(ObjectFind(0, LBL_TP_STATUS) >= 0)
     {
      string txt_tp;
      color  col_tp;
      if(tp_sesion_alcanzado)
        {
         txt_tp = StringFormat("TP SESION ALCANZADO $%.2f !", profit_sesion);
         col_tp = clrLime;
        }
      else
        {
         txt_tp = StringFormat("Profit sesión: $%.2f / $%.2f", profit_sesion, TP_Objetivo_USD);
         col_tp = (profit_sesion > 0) ? C'0,200,120' : clrLightGray;
        }
      ObjectSetString(0,  LBL_TP_STATUS, OBJPROP_TEXT,  txt_tp);
      ObjectSetInteger(0, LBL_TP_STATUS, OBJPROP_COLOR, col_tp);
     }

   ChartRedraw(0);
  }

//+------------------------------------------------------------------+
//| Crear panel visual                                              |
//+------------------------------------------------------------------+
void CrearPanel()
  {
   int x = 15;
   int y = 20;
   int w = 225;
   int h = 265;

   //--- Fondo principal
   CrearRectangulo(PANEL_NOMBRE, x, y, w, h, C'13,16,28', C'45,65,120', 2);

   //--- Barra de título (franja superior destacada)
   CrearRectangulo(PANEL_TITLEBAR, x, y, w, 52, C'18,28,58', C'45,65,120', 0);

   //--- Título del EA
   CrearEtiqueta(LBL_TITULO, x + 10, y + 7,
                 "SCALPING PRO", clrGold, 10, true);

   //--- Nombre del par (grande y prominente)
   CrearEtiqueta(LBL_SIMBOLO, x + 10, y + 25,
                 _Symbol, C'200,225,255', 14, true);

   //--- Separador 1
   CrearRectangulo(SEP1, x + 5, y + 54, w - 10, 1, C'50,70,130', C'50,70,130', 0);

   //--- Lote actual
   CrearEtiqueta(LBL_VOLUMEN, x + 10, y + 62,
                 "Lote: " + DoubleToString(lote_final, 2),
                 C'160,185,255', 9, false);

   //--- Timer de vela (grande y visible)
   CrearEtiqueta(LBL_TIMER, x + 10, y + 79,
                 "Vela cierra: --",
                 clrLightYellow, 11, true);

   //--- Operaciones por hora
   CrearEtiqueta(LBL_OPS, x + 10, y + 102,
                 "Ops: 0/" + IntegerToString(max_ops_efectivo),
                 clrLightCyan, 9, false);

   //--- Estado del lock horario
   CrearEtiqueta(LBL_LOCK, x + 10, y + 119,
                 "Lock ops: calculando...",
                 clrOrange, 9, false);

   //--- Estado TP de sesión
   CrearEtiqueta(LBL_TP_STATUS, x + 10, y + 136,
                 StringFormat("Profit sesión: $0.00 / $%.2f", TP_Objetivo_USD),
                 clrLightGray, 9, false);

   //--- Info EMA
   CrearEtiqueta(LBL_EMA, x + 10, y + 153,
                 "EMA" + IntegerToString(Periodo_EMA) + ": calculando...",
                 clrLightGray, 9, false);

   //--- Separador 2
   CrearRectangulo(SEP2, x + 5, y + 171, w - 10, 1, C'50,70,130', C'50,70,130', 0);

   //--- Botón BUY
   CrearBoton(BTN_BUY, x + 10, y + 179, 98, 58,
              "BUY", clrWhite, C'0,165,65', C'0,120,45');

   //--- Botón SELL
   CrearBoton(BTN_SELL, x + 117, y + 179, 98, 58,
              "SELL", clrWhite, C'200,35,35', C'150,20,20');

   ChartRedraw(0);
  }

//+------------------------------------------------------------------+
//| Actualizar timer de la vela                                     |
//+------------------------------------------------------------------+
void ActualizarTimerVela()
  {
   int periodo_segs = PeriodSeconds(PERIOD_CURRENT);
   int elapsed      = (int)(TimeCurrent() % periodo_segs);
   int rest         = periodo_segs - elapsed;

   string texto;
   int minutos = rest / 60;
   int segs    = rest % 60;
   if(minutos > 0)
      texto = StringFormat("Vela cierra: %dm %02ds", minutos, segs);
   else
      texto = StringFormat("Vela cierra: %ds", segs);

   color col = (rest <= 5)  ? clrOrangeRed :
               (rest <= 15) ? clrOrange    : clrLightYellow;

   if(ObjectFind(0, LBL_TIMER) >= 0)
     {
      ObjectSetString(0, LBL_TIMER, OBJPROP_TEXT, texto);
      ObjectSetInteger(0, LBL_TIMER, OBJPROP_COLOR, col);
     }
  }

//+------------------------------------------------------------------+
//| Actualizar contador de operaciones en panel                     |
//+------------------------------------------------------------------+
void ActualizarContadorOps()
  {
   int rest  = max_ops_efectivo - ops_en_ventana;
   string txt = "Ops: " + IntegerToString(ops_en_ventana) +
                "/" + IntegerToString(max_ops_efectivo) +
                "  (" + IntegerToString(MathMax(0, rest)) + " disp.)";
   color col = (rest <= 0) ? clrOrangeRed : clrLightCyan;

   if(ObjectFind(0, LBL_OPS) >= 0)
     {
      ObjectSetString(0, LBL_OPS, OBJPROP_TEXT, txt);
      ObjectSetInteger(0, LBL_OPS, OBJPROP_COLOR, col);
     }
   if(ObjectFind(0, LBL_VOLUMEN) >= 0)
      ObjectSetString(0, LBL_VOLUMEN, OBJPROP_TEXT,
                      "Lote: " + DoubleToString(lote_final, 2));

   ChartRedraw(0);
  }

//+------------------------------------------------------------------+
//| Actualizar info EMA en el panel                                 |
//+------------------------------------------------------------------+
void ActualizarInfoEMA()
  {
   if(ObjectFind(0, LBL_EMA) < 0)
      return;

   double buf[];
   ArraySetAsSeries(buf, true);
   if(CopyBuffer(handle_ema, 0, 0, 2, buf) < 2)
      return;

   double ema    = buf[0];
   double precio = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   bool alcista  = precio > ema;

   string txt = "EMA" + IntegerToString(Periodo_EMA) + ": " +
                DoubleToString(ema, _Digits) +
                (alcista ? "  ALCISTA ^" : "  BAJISTA v");
   color col = alcista ? C'0,220,120' : C'255,90,90';

   ObjectSetString(0, LBL_EMA, OBJPROP_TEXT, txt);
   ObjectSetInteger(0, LBL_EMA, OBJPROP_COLOR, col);
  }

//+------------------------------------------------------------------+
//| Eliminar todos los objetos del panel                            |
//+------------------------------------------------------------------+
void EliminarPanel()
  {
   string objs[] = {
      PANEL_NOMBRE, PANEL_TITLEBAR,
      BTN_BUY, BTN_SELL,
      LBL_TITULO, LBL_SIMBOLO, LBL_VOLUMEN,
      LBL_TIMER, LBL_OPS, LBL_LOCK, LBL_TP_STATUS, LBL_EMA,
      SEP1, SEP2
   };
   for(int i = 0; i < ArraySize(objs); i++)
      if(ObjectFind(0, objs[i]) >= 0)
         ObjectDelete(0, objs[i]);
   ChartRedraw(0);
  }

//+------------------------------------------------------------------+
//| Helper: Rectángulo de fondo                                     |
//+------------------------------------------------------------------+
void CrearRectangulo(string nombre, int x, int y, int ancho, int alto,
                     color col_fondo, color col_borde, int grosor)
  {
   if(ObjectFind(0, nombre) >= 0)
      ObjectDelete(0, nombre);
   ObjectCreate(0, nombre, OBJ_RECTANGLE_LABEL, 0, 0, 0);
   ObjectSetInteger(0, nombre, OBJPROP_XDISTANCE,   x);
   ObjectSetInteger(0, nombre, OBJPROP_YDISTANCE,   y);
   ObjectSetInteger(0, nombre, OBJPROP_XSIZE,        ancho);
   ObjectSetInteger(0, nombre, OBJPROP_YSIZE,        alto);
   ObjectSetInteger(0, nombre, OBJPROP_BGCOLOR,      col_fondo);
   ObjectSetInteger(0, nombre, OBJPROP_BORDER_COLOR, col_borde);
   ObjectSetInteger(0, nombre, OBJPROP_BORDER_TYPE,  BORDER_FLAT);
   ObjectSetInteger(0, nombre, OBJPROP_WIDTH,         grosor);
   ObjectSetInteger(0, nombre, OBJPROP_CORNER,        CORNER_LEFT_UPPER);
   ObjectSetInteger(0, nombre, OBJPROP_SELECTABLE,   false);
   ObjectSetInteger(0, nombre, OBJPROP_HIDDEN,       true);
   ObjectSetInteger(0, nombre, OBJPROP_ZORDER,       0);
  }

//+------------------------------------------------------------------+
//| Helper: Etiqueta de texto                                       |
//+------------------------------------------------------------------+
void CrearEtiqueta(string nombre, int x, int y, string texto,
                   color col, int tamanio, bool negrita)
  {
   if(ObjectFind(0, nombre) >= 0)
      ObjectDelete(0, nombre);
   ObjectCreate(0, nombre, OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, nombre, OBJPROP_XDISTANCE,  x);
   ObjectSetInteger(0, nombre, OBJPROP_YDISTANCE,  y);
   ObjectSetString(0, nombre,  OBJPROP_TEXT,       texto);
   ObjectSetInteger(0, nombre, OBJPROP_COLOR,      col);
   ObjectSetInteger(0, nombre, OBJPROP_FONTSIZE,   tamanio);
   ObjectSetString(0, nombre,  OBJPROP_FONT,       negrita ? "Arial Bold" : "Arial");
   ObjectSetInteger(0, nombre, OBJPROP_CORNER,     CORNER_LEFT_UPPER);
   ObjectSetInteger(0, nombre, OBJPROP_ANCHOR,     ANCHOR_LEFT_UPPER);
   ObjectSetInteger(0, nombre, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nombre, OBJPROP_HIDDEN,     true);
   ObjectSetInteger(0, nombre, OBJPROP_ZORDER,     1);
  }

//+------------------------------------------------------------------+
//| Helper: Botón personalizado                                     |
//+------------------------------------------------------------------+
void CrearBoton(string nombre, int x, int y, int ancho, int alto,
                string texto, color col_texto, color col_fondo, color col_borde)
  {
   if(ObjectFind(0, nombre) >= 0)
      ObjectDelete(0, nombre);
   ObjectCreate(0, nombre, OBJ_BUTTON, 0, 0, 0);
   ObjectSetInteger(0, nombre, OBJPROP_XDISTANCE,    x);
   ObjectSetInteger(0, nombre, OBJPROP_YDISTANCE,    y);
   ObjectSetInteger(0, nombre, OBJPROP_XSIZE,         ancho);
   ObjectSetInteger(0, nombre, OBJPROP_YSIZE,         alto);
   ObjectSetString(0, nombre,  OBJPROP_TEXT,         texto);
   ObjectSetInteger(0, nombre, OBJPROP_COLOR,        col_texto);
   ObjectSetInteger(0, nombre, OBJPROP_FONTSIZE,     16);
   ObjectSetString(0, nombre,  OBJPROP_FONT,         "Arial Bold");
   ObjectSetInteger(0, nombre, OBJPROP_BGCOLOR,      col_fondo);
   ObjectSetInteger(0, nombre, OBJPROP_BORDER_COLOR, col_borde);
   ObjectSetInteger(0, nombre, OBJPROP_CORNER,       CORNER_LEFT_UPPER);
   ObjectSetInteger(0, nombre, OBJPROP_SELECTABLE,   false);
   ObjectSetInteger(0, nombre, OBJPROP_HIDDEN,       true);
   ObjectSetInteger(0, nombre, OBJPROP_ZORDER,       2);
  }

//+------------------------------------------------------------------+
//| Paleta profesional oscura institucional                         |
//+------------------------------------------------------------------+
void AplicarColoresProfesionales()
  {
   ChartSetInteger(0, CHART_COLOR_BACKGROUND,  C'10,12,20');
   ChartSetInteger(0, CHART_COLOR_FOREGROUND,  C'170,185,210');
   ChartSetInteger(0, CHART_COLOR_GRID,        C'22,26,40');
   ChartSetInteger(0, CHART_COLOR_CHART_LINE,  C'80,130,210');
   ChartSetInteger(0, CHART_COLOR_CANDLE_BULL, C'0,200,120');
   ChartSetInteger(0, CHART_COLOR_CANDLE_BEAR, C'215,50,50');
   ChartSetInteger(0, CHART_COLOR_CHART_UP,    C'0,200,120');
   ChartSetInteger(0, CHART_COLOR_CHART_DOWN,  C'215,50,50');
   ChartSetInteger(0, CHART_COLOR_BID,         C'215,50,50');
   ChartSetInteger(0, CHART_COLOR_ASK,         C'0,200,120');
   ChartSetInteger(0, CHART_COLOR_LAST,        C'200,200,75');
   ChartSetInteger(0, CHART_COLOR_STOP_LEVEL,  C'255,185,0');
   ChartSetInteger(0, CHART_COLOR_VOLUME,      C'55,90,160');
   ChartSetInteger(0, CHART_SHOW_GRID,         true);
   ChartSetInteger(0, CHART_MODE,              CHART_CANDLES);
   ChartRedraw(0);
  }

//+------------------------------------------------------------------+
//| FIN DEL EA ScalpingPro v1.02                                    |
//+------------------------------------------------------------------+
