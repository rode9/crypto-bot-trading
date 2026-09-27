"""
Paper trading: corre la misma lógica del bot contra precios REALES en vivo,
pero sin conectar ninguna API key ni ejecutar órdenes de verdad.
Registra cada operación simulada en un log para que revises el desempeño
antes de siquiera pensar en pasar a modo real.

Config actual = la única combinación que sobrevivió validación out-of-sample
sobre 9 años de histórico real (ver CLAUDE.md, sección "Hallazgo más
importante"): BTC/USDT en 4h. No cambiar el símbolo/timeframe sin volver a
correr backtest.py + validación walk-forward sobre la nueva combinación.

Uso:
    python3 paper_trading.py          # loop infinito, para correr manualmente en tu propia terminal
    python3 paper_trading.py --once   # una sola revisión y termina (para cron / GitHub Actions)
"""

import sys
import time
import csv
import json
import os
from datetime import datetime

import ccxt
import pandas as pd

from strategy import compute_indicators, generate_signal

SYMBOL = "BTC/USDT"
TIMEFRAME = "4h"           # validado out-of-sample; ver CLAUDE.md antes de cambiar
CHECK_INTERVAL_SEC = 900   # revisa cada 15 min (sobra para no perderse el cierre de una vela de 4h)
CAPITAL_VIRTUAL = 1_000_000
RIESGO_POR_TRADE = 0.02
STOP_LOSS_PCT = 0.02
TAKE_PROFIT_PCT = 0.04
FEE_PCT = 0.001
LOG_FILE = "paper_trades_log.csv"
ESTADO_FILE = "paper_trading_estado.json"  # para no perder la posición abierta si el proceso se corta

exchange = ccxt.binance()


def log_trade(row: dict):
    existe = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=row.keys())
        if not existe:
            writer.writeheader()
        writer.writerow(row)


def guardar_estado(capital: float, posicion: dict | None):
    with open(ESTADO_FILE, "w") as f:
        json.dump({"capital": capital, "posicion": posicion}, f)


def cargar_estado() -> tuple[float, dict | None]:
    if not os.path.isfile(ESTADO_FILE):
        return CAPITAL_VIRTUAL, None
    with open(ESTADO_FILE) as f:
        estado = json.load(f)
    return estado["capital"], estado["posicion"]


def revisar_una_vez():
    """Una sola revisión: trae precios, evalúa señal, actúa si corresponde, guarda estado."""
    capital, posicion = cargar_estado()
    if posicion:
        print(f"Retomando posición abierta desde antes: entrada={posicion['entrada']:,.2f} @ {posicion['fecha_entrada']}")

    # limit alto porque el filtro de tendencia usa EMA200: necesita
    # bastante historia previa para que ese promedio ya esté estabilizado
    ohlcv = exchange.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME, limit=500)
    df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = compute_indicators(df)

    precio_actual = df.iloc[-1]["close"]
    senal = generate_signal(df)
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ahora}] precio={precio_actual:,.2f} señal={senal} posición_abierta={posicion is not None}")

    if posicion is None:
        if senal == "buy":
            riesgo_clp = capital * RIESGO_POR_TRADE
            tamano = riesgo_clp / (precio_actual * STOP_LOSS_PCT)
            tamano_max = capital / (precio_actual * (1 + FEE_PCT))
            tamano = min(tamano, tamano_max)
            costo = tamano * precio_actual * (1 + FEE_PCT)

            posicion = {
                "entrada": precio_actual,
                "tamano": tamano,
                "stop": precio_actual * (1 - STOP_LOSS_PCT),
                "target": precio_actual * (1 + TAKE_PROFIT_PCT),
                "fecha_entrada": ahora,
            }
            capital -= costo
            guardar_estado(capital, posicion)
            print(f"[{ahora}] 🟢 COMPRA simulada @ {precio_actual:,.2f} | tamaño={tamano:.6f} | capital restante={capital:,.0f}")
    else:
        salida = None
        if precio_actual <= posicion["stop"]:
            salida = ("stop_loss", posicion["stop"])
        elif precio_actual >= posicion["target"]:
            salida = ("take_profit", posicion["target"])
        elif senal == "sell":
            salida = ("señal_venta", precio_actual)

        if salida:
            razon, precio_salida = salida
            ingreso = posicion["tamano"] * precio_salida * (1 - FEE_PCT)
            capital += ingreso
            pnl = ingreso - (posicion["tamano"] * posicion["entrada"] * (1 + FEE_PCT))

            print(f"[{ahora}] 🔴 VENTA simulada @ {precio_salida:,.2f} ({razon}) | PnL={pnl:,.0f} | capital={capital:,.0f}")

            log_trade({
                "fecha_entrada": posicion["fecha_entrada"],
                "fecha_salida": ahora,
                "entrada": posicion["entrada"],
                "salida": precio_salida,
                "razon": razon,
                "pnl": pnl,
                "capital_resultante": capital,
            })
            posicion = None
            guardar_estado(capital, posicion)


def run():
    """Loop infinito para correr manualmente en tu propia terminal (no usar en GitHub Actions)."""
    capital, _ = cargar_estado()
    print(f"Paper trading iniciado — {SYMBOL} {TIMEFRAME} — capital virtual {capital:,.0f}")
    print("NINGUNA orden real será ejecutada. Presiona Ctrl+C para detener.\n")

    while True:
        try:
            revisar_una_vez()
            time.sleep(CHECK_INTERVAL_SEC)
        except KeyboardInterrupt:
            print("\nPaper trading detenido por el usuario.")
            break
        except Exception as e:
            print(f"Error (reintentando en {CHECK_INTERVAL_SEC}s): {e}")
            time.sleep(CHECK_INTERVAL_SEC)


if __name__ == "__main__":
    if "--once" in sys.argv:
        revisar_una_vez()
    else:
        run()
