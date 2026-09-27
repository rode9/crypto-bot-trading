# Crypto Bot — Contexto del proyecto

## Qué es esto
Bot de trading cripto para Rode (parte de cero en trading, viene de datos/analytics
en TWL — SQL Server, Power BI, Python). Objetivo: automatizar, pero primero
**validar con backtest + paper trading** antes de tocar plata real.

## Estado actual
- `strategy.py`: cruce EMA9/EMA21 + filtro RSI + **filtro de tendencia EMA200**
  (solo compra si precio > EMA200, para evitar cruces falsos en mercado lateral).
  Con este filtro, sobre ~1 año de datos reales: BTC 1h -2.8%, BTC 4h -8.6%,
  ETH 1h -4.1%, ETH 4h -1.7%, SOL 1h +6.6%, SOL 4h +1.2% — mucho mejor que sin
  el filtro (antes: -5.7% a -26.4% en las 6), pero todavía no es una ventaja
  clara y consistente (4 de 6 siguen en rojo).
  También se probó en **forex** (EUR/USD, GBP/USD, USD/JPY vía `yfinance`,
  1h, ~2 años): resultado peor que cripto (-15% a -21%, Sharpe -2 a -4.1).
  Motivo: el stop-loss (2%) / take-profit (4%) están calibrados para la
  volatilidad de cripto, no para forex (que se mueve mucho menos por vela).
  **Decisión: descartado el camino forex por ahora, foco 100% en cripto.**
- `backtest.py`: motor de backtest con position sizing por % de riesgo, stop-loss,
  take-profit, comisiones, drawdown máximo, Sharpe ratio anualizado, y
  `fetch_historical_amplio()` para traer más de 1000 velas paginando contra
  Binance. **Ya se corrió contra datos reales**, primero con muestra chica
  (~1000 velas, ~1 mes) y después con ~1 año de historia real por par/timeframe.
  Con ~1 año de datos el veredicto es claro: **pierde en las 6 combinaciones
  probadas** (BTC/ETH/SOL × 1h/4h) — retornos entre -5.7% y -26.4%, drawdowns
  de 14% a 35%, Sharpe negativo en todas. El resultado mixto que se vio con la
  muestra chica (2 de 5 positivas) era ruido de corto plazo, no ventaja real.
  **Conclusión: la lógica actual (cruce EMA9/21 + RSI) no tiene edge probado.**
  No tiene sentido pasar a paper trading con esta versión — hay que repensar
  la estrategia (ej. filtro de tendencia tipo EMA200 para evitar operar en
  mercados laterales) antes de seguir.
- `paper_trading.py`: mismo motor pero corriendo en vivo contra Binance real,
  sin ejecutar órdenes — solo simula y loggea a `paper_trades_log.csv`.
- `README.md`: instrucciones de uso y próximos pasos sugeridos.
- `fetch_datos.py` + carpeta `data/`: descarga y cachea en CSV **todo el
  histórico real disponible en Binance** (no simulado) para BTC/ETH/SOL en
  1h y 4h — BTC y ETH desde 2017-08 (~9.1 años), SOL desde 2020-08 (~6.1 años,
  no existe antes en Binance). Se pidieron "10 años" pero Binance no tiene
  tanto — esto es el máximo real disponible. Volver a correr `fetch_datos.py`
  si se necesita refrescar los datos a la fecha actual.

## Hallazgo más importante hasta ahora (histórico completo)
Corriendo el baseline (stop 2% / take 4%, filtro EMA200) sobre TODO el
histórico real (no un año, no un mes — 9 años con múltiples ciclos: bull
2017, crypto winter 2018, covid rally 2020, bull 2021, crash 2022, 2023-26):

| Par/TF | Retorno total | Drawdown máx | Sharpe | Años positivos |
|---|---|---|---|---|
| BTC/USDT 1h | -57.91% | **-73.74%** | -0.47 | 2 de 10 |
| **BTC/USDT 4h** | **+90.86%** | -15.92% | **0.70** | **9 de 10** |
| ETH/USDT 1h | -32.96% | -59.26% | -0.14 | 2 de 10 |
| ETH/USDT 4h | +23.88% | -28.83% | 0.25 | 6 de 10 |
| SOL/USDT 1h | +102.64% | -40.97% | 0.60 | 6 de 7 |
| SOL/USDT 4h | +3.32% | -24.09% | 0.10 | mixto |

**BTC/USDT 4h es el candidato más sólido de toda la investigación**: rentable
9 de 10 años, incluido el crash de 2022 (no perdió ese año), con drawdown
razonable (-15.9%) para el retorno obtenido. A diferencia de los ajustes de
stop/take-profit anteriores, esto NO salió de buscar el mejor número — es el
mismo baseline de siempre, mostrando consistencia real across-time. Es la
primera evidencia de esta investigación que no parece ruido.

**1h queda descartado en BTC/ETH** — pierde estructuralmente en 8 de 10 años,
con un drawdown de -73.74% en BTC que sería un riesgo de ruina real con plata
de verdad. La razón intuida: en 1h hay demasiadas señales falsas (673 trades
en 9 años vs 149 en 4h); menos trades pero más selectivos parece ser mejor
para esta lógica de entrada.

**Antes de confiar en BTC/USDT 4h para paper trading**, falta: validar que no
sea casualidad de años específicos (ej. correr walk-forward: ajustar en
2017-2022, validar en 2023-2026 sin tocar nada), y decidir si limitarse solo
a ese par/timeframe o incluir también ETH 4h (más débil pero también positivo
en la mayoría de los años).

## Bugs ya resueltos
1. El sizing por riesgo (arriesgar 2% del capital con stop de 2%) implica usar
   ~100% del capital en cada trade. Al sumar la comisión, el costo se pasaba por
   unos pesos del capital disponible y la condición `costo <= capital` rechazaba
   la entrada SIEMPRE. Se arregló capando `tamano` a `capital / (precio * (1+fee))`.
   Si ves algo raro con 0 trades ejecutados, esta es la primera sospecha.
2. `run_backtest` devolvía como "capital final" solo el efectivo, sin sumar el
   valor de una posición que quedara abierta al final del período (marcado a
   mercado). Si el backtest terminaba con un trade sin cerrar, se veía un
   retorno de ~-100% aunque la posición siguiera teniendo valor real. Se
   arregló devolviendo `equity_df["equity"].iloc[-1]` (efectivo + posición
   abierta) como capital final. Si ves un retorno de exactamente -100%, esta
   es la primera sospecha.

## Pendiente / lo que sigue
1. ~~Correr `backtest.py` contra datos reales~~ — hecho, ver "Estado actual".
2. ~~Calcular drawdown máximo y Sharpe ratio~~ — hecho, ya está en `backtest.py`.
3. ~~Probar sobre más historia para descartar ruido de muestra chica~~ — hecho
   con ~1 año de datos. Confirmado: pierde en las 6 combinaciones probadas.
4. ~~Agregar filtro de tendencia EMA200~~ — hecho, mejora bastante pero no
   alcanza para una ventaja consistente (4 de 6 combos siguen en rojo).
5. ~~Probar forex~~ — hecho vía `yfinance`. Peor que cripto, descartado por
   ahora (stop/take calibrados para volatilidad cripto, no forex).
6. **Se probó un grid de stop-loss/take-profit y se detectó overfitting**:
   al elegir el "mejor" combo mirando 8 meses de datos (in-sample) y probarlo
   en los 4 meses siguientes que el ajuste nunca vio (out-of-sample), el
   resultado empeoró en casi todos los casos (ej. ETH pasó de +7.17% in-sample
   a -13.23% out-of-sample). Lección para todo ajuste futuro de parámetros:
   **siempre separar datos de ajuste y datos de validación** — si un combo
   se ve bien solo en la parte que se usó para elegirlo, no sirve.
7. ~~Conseguir más historia~~ — hecho, se descargó todo lo disponible en
   Binance (~9 años BTC/ETH, ~6 años SOL). Ver "Hallazgo más importante".
8. ~~Validación walk-forward de BTC/USDT 4h~~ — hecho: 2017-2022 dio +77.91%
   (Sharpe 1.00), y 2023-2026 (nunca visto al validar) dio **+15.93%** (Sharpe
   0.40, drawdown -16.97%). Se debilita pero sigue positivo — pasa la prueba.
   ETH/USDT 4h también se sostiene positivo pero muy al límite (+3.60% en
   2023-2026, Sharpe 0.14) — candidato secundario débil, no prioritario.
9. Descartar definitivamente 1h en BTC/ETH (drawdown de ruina, pierde
   estructuralmente) — no reconsiderar sin una razón nueva y concreta.
10. ~~Configurar `paper_trading.py` con la config validada~~ — hecho:
    `SYMBOL="BTC/USDT"`, `TIMEFRAME="4h"`, `CHECK_INTERVAL_SEC=900`, y
    `limit=500` velas (necesario para que la EMA200 esté bien calentada).
    **Rode lo corre manualmente en su propia terminal** (`python
    paper_trading.py`, dejarlo abierto) — un proceso lanzado dentro de una
    sesión de Claude Code no sobrevive días/semanas, así que esto no se
    puede dejar corriendo "desde acá".
11. Revisar `paper_trades_log.csv` después de mínimo 2-4 semanas corriendo
    antes de considerar cualquier cosa con plata real. Con velas de 4h el
    volumen de trades va a ser bajo (backtest de 9 años dio ~150 trades en
    total para BTC 4h) — no alarmarse si pasan días sin actividad.
12. Modo "live" real (no implementado — ni pensarlo hasta que el paper
    trading en curso confirme resultados consistentes con lo que dio el
    backtest)

## Cómo trabajar conmigo en esto
- Rode tiene background técnico fuerte (Python, SQL, DAX) — sin explicaciones
  de fundamentos de programación, directo al grano
- Es su primera vez en trading — sí vale la pena explicar conceptos de trading
  (qué es un stop-loss, por qué importa el drawdown, etc.) cuando sea relevante
- Prioridad: que la estrategia se valide con evidencia (backtest + paper) antes
  de escalar a algo real. No apurar el paso a plata real.
