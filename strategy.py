"""
Estrategia: cruce de EMAs + filtro RSI + filtro de tendencia
- Compra: EMA rápida cruza hacia arriba a EMA lenta, RSI < umbral_sobrecompra
  (evita comprar caro), Y precio por sobre la EMA de tendencia (evita comprar
  cruces falsos en mercado lateral o bajista)
- Venta: EMA rápida cruza hacia abajo a EMA lenta, O se toca stop-loss / take-profit
"""

import pandas as pd
import numpy as np


def compute_indicators(df: pd.DataFrame, ema_fast=9, ema_slow=21, rsi_period=14, ema_trend=200) -> pd.DataFrame:
    df = df.copy()
    df["ema_fast"] = df["close"].ewm(span=ema_fast, adjust=False).mean()
    df["ema_slow"] = df["close"].ewm(span=ema_slow, adjust=False).mean()
    df["ema_trend"] = df["close"].ewm(span=ema_trend, adjust=False).mean()

    # RSI
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(rsi_period).mean()
    avg_loss = loss.rolling(rsi_period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))
    df["rsi"] = df["rsi"].fillna(50)

    return df


def generate_signal(df: pd.DataFrame, rsi_max_buy=70, usar_filtro_tendencia=True) -> str:
    """
    Devuelve 'buy', 'sell' o 'hold' basado en la última vela cerrada.
    Requiere al menos 2 filas para detectar el cruce.
    """
    if len(df) < 2:
        return "hold"

    prev, curr = df.iloc[-2], df.iloc[-1]

    cruce_alcista = prev["ema_fast"] <= prev["ema_slow"] and curr["ema_fast"] > curr["ema_slow"]
    cruce_bajista = prev["ema_fast"] >= prev["ema_slow"] and curr["ema_fast"] < curr["ema_slow"]
    tendencia_alcista = curr["close"] > curr["ema_trend"] if usar_filtro_tendencia else True

    if cruce_alcista and curr["rsi"] < rsi_max_buy and tendencia_alcista:
        return "buy"
    if cruce_bajista:
        return "sell"
    return "hold"
