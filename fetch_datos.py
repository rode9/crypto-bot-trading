"""
Descarga y cachea en disco (carpeta data/) todo el histórico disponible en
Binance para los pares/timeframes de interés. Evita tener que re-descargar
contra la API cada vez que se prueba un backtest distinto.

Uso:
    python3 fetch_datos.py
"""

import os
import pandas as pd

from backtest import fetch_historical_amplio

PARES = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
TIMEFRAMES = ["1h", "4h"]
ANIOS_OBJETIVO = 10  # se pide de más; si el par no tiene tanta historia, trae lo que haya
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def velas_para(timeframe: str, anios: int) -> int:
    velas_por_dia = {"1h": 24, "4h": 6}[timeframe]
    return velas_por_dia * 365 * anios


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    for symbol in PARES:
        for tf in TIMEFRAMES:
            nombre_archivo = symbol.replace("/", "") + f"_{tf}.csv"
            ruta = os.path.join(DATA_DIR, nombre_archivo)
            total_velas = velas_para(tf, ANIOS_OBJETIVO)
            print(f"Descargando {symbol} {tf} (pidiendo hasta {ANIOS_OBJETIVO} años = {total_velas} velas)...")
            df = fetch_historical_amplio(symbol=symbol, timeframe=tf, total_velas=total_velas)
            df.to_csv(ruta, index=False)
            if df.empty:
                print(f"  -> sin datos para {symbol} {tf}")
                continue
            desde = df["timestamp"].iloc[0]
            hasta = df["timestamp"].iloc[-1]
            dias = (pd.to_datetime(hasta) - pd.to_datetime(desde)).days
            print(f"  -> {len(df)} velas guardadas en {ruta} ({desde} a {hasta}, ~{dias/365:.1f} años reales)")


if __name__ == "__main__":
    main()
