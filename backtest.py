"""
Backtester: simula la estrategia sobre histórico y calcula métricas de resultado.
No conecta con ninguna cuenta real. Solo usa datos públicos de mercado.
"""

import ccxt
import numpy as np
import pandas as pd
from strategy import compute_indicators, generate_signal


def fetch_historical(symbol="BTC/USDT", timeframe="1h", limit=1000, exchange_id="binance"):
    exchange = getattr(ccxt, exchange_id)()
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    return df


def fetch_historical_amplio(symbol="BTC/USDT", timeframe="1h", total_velas=8760, exchange_id="binance"):
    """Igual que fetch_historical pero pagina hacia atrás para traer más de 1000 velas."""
    exchange = getattr(ccxt, exchange_id)()
    timeframe_ms = int(exchange.parse_timeframe(timeframe) * 1000)
    since = exchange.milliseconds() - total_velas * timeframe_ms

    todas = []
    while len(todas) < total_velas:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=1000)
        if not ohlcv:
            break
        todas.extend(ohlcv)
        since = ohlcv[-1][0] + timeframe_ms
        if len(ohlcv) < 1000:
            break  # ya llegamos a las velas más recientes disponibles

    df = pd.DataFrame(todas, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df.drop_duplicates(subset="timestamp").reset_index(drop=True)
    return df.tail(total_velas).reset_index(drop=True)


def run_backtest(
    df: pd.DataFrame,
    capital_inicial=1_000_000,   # CLP, ajusta a tu moneda
    riesgo_por_trade=0.02,       # 2% del capital arriesgado por operación
    stop_loss_pct=0.02,          # sale si cae 2% desde entrada
    take_profit_pct=0.04,        # sale si sube 4% desde entrada
    fee_pct=0.001,                # 0.1% comisión típica spot
):
    df = compute_indicators(df)

    capital = capital_inicial
    posicion = None  # dict con entrada, tamaño, etc. o None si está fuera del mercado
    trades = []
    equity_curve = []  # (timestamp, equity) marcado a mercado en cada vela

    for i in range(2, len(df)):
        ventana = df.iloc[: i + 1]
        fila_actual = ventana.iloc[-1]
        precio_actual = fila_actual["close"]
        senal = generate_signal(ventana)

        if posicion is None:
            if senal == "buy":
                riesgo_clp = capital * riesgo_por_trade
                tamano = riesgo_clp / (precio_actual * stop_loss_pct)  # tamaño de posición ajustado al riesgo
                tamano_max = capital / (precio_actual * (1 + fee_pct))  # nunca gastar más capital del disponible
                tamano = min(tamano, tamano_max)
                costo = tamano * precio_actual * (1 + fee_pct)
                if tamano > 0 and costo <= capital:
                    posicion = {
                        "entrada": precio_actual,
                        "tamano": tamano,
                        "stop": precio_actual * (1 - stop_loss_pct),
                        "target": precio_actual * (1 + take_profit_pct),
                        "fecha_entrada": fila_actual["timestamp"],
                    }
                    capital -= costo
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
                ingreso = posicion["tamano"] * precio_salida * (1 - fee_pct)
                capital += ingreso
                pnl = ingreso - (posicion["tamano"] * posicion["entrada"] * (1 + fee_pct))
                trades.append({
                    "fecha_entrada": posicion["fecha_entrada"],
                    "fecha_salida": fila_actual["timestamp"],
                    "entrada": posicion["entrada"],
                    "salida": precio_salida,
                    "razon": razon,
                    "pnl": pnl,
                    "pnl_pct": pnl / (posicion["tamano"] * posicion["entrada"]) * 100,
                })
                posicion = None

        equity = capital + (posicion["tamano"] * precio_actual if posicion else 0)
        equity_curve.append((fila_actual["timestamp"], equity))

    trades_df = pd.DataFrame(trades)
    equity_df = pd.DataFrame(equity_curve, columns=["timestamp", "equity"])
    # capital_final debe reflejar el valor total de la cuenta (efectivo + posición
    # abierta marcada a mercado), no solo el efectivo, o un trade sin cerrar al
    # final del período se ve como una pérdida del ~100% del capital.
    capital_final = equity_df["equity"].iloc[-1] if not equity_df.empty else capital
    return trades_df, capital_final, equity_df


def calcular_drawdown_maximo(equity_df: pd.DataFrame) -> float:
    """Máxima caída porcentual desde un pico de equity hasta el valle siguiente."""
    pico = equity_df["equity"].cummax()
    drawdown = (equity_df["equity"] - pico) / pico
    return drawdown.min() * 100  # número negativo, ej. -8.5


def calcular_sharpe(equity_df: pd.DataFrame) -> float | None:
    """Sharpe anualizado (asume 365 días de mercado, típico de cripto) sobre retornos diarios de equity."""
    equity_diaria = equity_df.set_index("timestamp")["equity"].resample("1D").last().dropna()
    retornos = equity_diaria.pct_change().dropna()
    if len(retornos) < 2 or retornos.std() == 0:
        return None
    return (retornos.mean() / retornos.std()) * np.sqrt(365)


def print_metricas(trades_df: pd.DataFrame, capital_inicial: float, capital_final: float, equity_df: pd.DataFrame):
    if trades_df.empty:
        print("No se ejecutó ningún trade en el período. Prueba con más datos o ajusta la estrategia.")
        return

    ganadores = trades_df[trades_df["pnl"] > 0]
    perdedores = trades_df[trades_df["pnl"] <= 0]
    drawdown_maximo = calcular_drawdown_maximo(equity_df)
    sharpe = calcular_sharpe(equity_df)

    print(f"--- Resultado del backtest ---")
    print(f"Capital inicial:   {capital_inicial:,.0f}")
    print(f"Capital final:     {capital_final:,.0f}")
    print(f"Retorno total:     {(capital_final / capital_inicial - 1) * 100:.2f}%")
    print(f"N° de trades:      {len(trades_df)}")
    print(f"Win rate:          {len(ganadores) / len(trades_df) * 100:.1f}%")
    if len(ganadores):
        print(f"Ganancia prom.:    {ganadores['pnl_pct'].mean():.2f}%")
    if len(perdedores):
        print(f"Pérdida prom.:     {perdedores['pnl_pct'].mean():.2f}%")
    print(f"Mejor trade:       {trades_df['pnl_pct'].max():.2f}%")
    print(f"Peor trade:        {trades_df['pnl_pct'].min():.2f}%")
    print(f"Drawdown máximo:   {drawdown_maximo:.2f}%")
    print(f"Sharpe (anualiz.): {sharpe:.2f}" if sharpe is not None else "Sharpe (anualiz.): N/A (muy pocos días de datos)")


if __name__ == "__main__":
    print("Descargando histórico BTC/USDT (1h, últimas 1000 velas)...")
    df = fetch_historical(symbol="BTC/USDT", timeframe="1h", limit=1000)

    capital_inicial = 1_000_000
    trades_df, capital_final, equity_df = run_backtest(df, capital_inicial=capital_inicial)

    print_metricas(trades_df, capital_inicial, capital_final, equity_df)

    if not trades_df.empty:
        trades_df.to_csv("resultados_backtest.csv", index=False)
        print("\nDetalle de trades guardado en resultados_backtest.csv")
