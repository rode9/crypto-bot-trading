# Crypto Bot — Backtest + Paper Trading

Bot de trading cripto con estrategia de cruce de EMAs (9/21) + filtro RSI,
gestión de riesgo (stop-loss, take-profit, sizing por % de riesgo).

**No ejecuta órdenes reales.** Es para aprender y validar una estrategia antes
de arriesgar plata de verdad.

## Instalación

```bash
pip install ccxt pandas numpy
```

## 1. Backtest (histórico)

Corre la estrategia sobre datos pasados para ver si tiene sentido:

```bash
python3 backtest.py
```

Ajusta `symbol`, `timeframe`, `capital_inicial`, `riesgo_por_trade`,
`stop_loss_pct`, `take_profit_pct` directamente en el `if __name__` de
`backtest.py` para probar variantes.

## 2. Paper trading (vivo, sin plata real)

Corre contra el mercado real en tiempo real, pero solo simula:

```bash
python3 paper_trading.py
```

Déjalo corriendo en la noche. Revisa `paper_trades_log.csv` al día
siguiente para ver cómo le fue.

## Métricas a mirar antes de pensar en ir a real

- **Win rate**: no tiene que ser alto (una estrategia con 35% de winrate
  puede ser rentable si las ganancias son más grandes que las pérdidas)
- **Retorno total** vs. **drawdown máximo** (cuánto cae el capital en el
  peor momento — este bot aún no lo calcula, es el siguiente paso)
- Corre el paper trading **mínimo 2-4 semanas** antes de considerar plata
  real. Un buen o mal resultado en pocos días no dice nada.

## Próximos pasos posibles

- Calcular drawdown máximo y Sharpe ratio en el backtest
- Probar la estrategia en varios pares y timeframes para ver si es robusta
  o solo funcionó por casualidad en un período específico
- Modo "live" real: mismo motor pero llamando `exchange.create_order()`
  con tus API keys (requiere manejo de errores mucho más robusto que esto)
- Notificaciones (Telegram/email) en vez de mirar la consola

## Importante

Esto es una herramienta técnica, no asesoría financiera. Cripto es volátil
y el 90%+ de los bots caseros pierden plata cuando pasan de paper a real
sin el testing suficiente. Yo no soy asesor financiero — la plata que
pongas en real, que sea la que estás dispuesto a perder completa.
