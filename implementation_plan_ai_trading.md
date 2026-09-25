# Implementation Plan — Sistema de Trading con IA

## Objetivo

Construir una plataforma cuantitativa multimodelo capaz de:

- Recoger datos de mercado en tiempo real.
- Generar features numéricas y de contexto.
- Entrenar y comparar múltiples modelos de IA.
- Validar estrategias con backtesting y walk-forward.
- Ejecutar paper trading y, posteriormente, trading real.
- Aplicar gestión de riesgo independiente de los modelos.
- Monitorizar rendimiento, señales, errores y estabilidad.
- Automatizar experimentación y optimización.

La prioridad del proyecto es evitar construir muchos modelos a la vez sin saber si los datos, el backtest o la ejecución son correctos.

---

## Restricciones del Proyecto

| Restricción | Decisión |
|-------------|----------|
| **Hardware** | Ryzen 9 9950X3D · RTX 5080 16GB · 64GB DDR5 · 6TB NVMe |
| **OS** | Dual boot: Windows 11 Pro (SSD 4TB) + Ubuntu 24.04 (SSD 2TB) |
| **Datos** | Solo fuentes gratuitas / open source |
| **LLM** | Sin APIs de pago — modelos locales via Ollama en RTX 5080 |
| **Cloud** | Nada — todo corre en la máquina local |
| **Coste recurrente** | Solo electricidad (~30-40€/mes con PC 24/7) |

---

## Infraestructura de Hardware

```
CPU:    AMD Ryzen 9 9950X3D — 16C/32T, 4.3-5.7GHz, 144MB L3 V-Cache
GPU:    Gigabyte RTX 5080 GAMING OC — 16GB GDDR7, Tensor Cores 5ª gen
RAM:    64GB DDR5 6000MHz (G.Skill Trident Z5 Neo)
SSD 1:  Samsung 4TB NVMe PCIe 5.0 (14.800 MB/s) → Windows
SSD 2:  Samsung 9100 PRO 2TB NVMe PCIe 5.0 (14.700 MB/s) → Ubuntu + Trading System
PSU:    Corsair RM1000e 1000W 80+ Gold
Cool:   Arctic Liquid Freezer III Pro 360mm
Case:   Fractal Design North XL
```

---

## Configuración Dual Boot

### Particionado SSD 4TB — Windows

```
├── Partición EFI             512 MB
├── Windows 11 Pro             500 GB
└── Datos / uso personal      ~3.5 TB  (NTFS, accesible desde Ubuntu)
```

### Particionado SSD 2TB — Ubuntu (Trading System)

```
├── /boot/efi                  512 MB
├── /                          100 GB  (sistema + Docker)
├── /home                      100 GB  (configs, código, scripts)
├── swap                       32 GB   (para hibernación)
└── /data                      ~1.75 TB
    ├── /data/timescaledb              (base de datos)
    ├── /data/redis                    (estado real-time)
    ├── /data/mlflow                   (experimentos)
    ├── /data/models                   (checkpoints, artefactos)
    ├── /data/raw                      (datos históricos descargados)
    ├── /data/features                 (feature store)
    ├── /data/ollama                   (modelos LLM locales)
    └── /data/logs                     (logs del sistema)
```

### GRUB

```
GRUB_DEFAULT=ubuntu
GRUB_TIMEOUT=5
```

Ubuntu arranca por defecto para que el sistema de trading corra 24/7.

---

## Estrategia de Latencia — Sistema de Dos Velocidades

```
┌─────────────────────────────────────────────────────┐
│                CAPA LENTA (principal)                │
│                                                     │
│  Timeframe:   5m — 15m — 1h                         │
│  Latencia:    < 2 segundos end-to-end               │
│  Modelos:     XGBoost, Transformer, LLM context     │
│  Decisión:    ¿Entro? ¿Dirección? ¿Tamaño?         │
│  Frecuencia:  1-20 operaciones/día                  │
│                                                     │
├─────────────────────────────────────────────────────┤
│              CAPA RÁPIDA (complementaria)            │
│                                                     │
│  Timeframe:   10s — 30s — 1m                        │
│  Latencia:    < 200ms end-to-end                    │
│  Modelos:     Order book model (LightGBM)           │
│  Decisión:    ¿Cuándo exactamente ejecuto la orden? │
│  Función:     Timing de entrada/salida              │
│                                                     │
└─────────────────────────────────────────────────────┘
```

Implementar la capa lenta primero (Fases 0-7).
La capa rápida se añade después (Fase 9+).

---

## Fuentes de Datos — 100% Gratuitas

### Datos de mercado

| Fuente | Datos | Método | Coste |
|--------|-------|--------|-------|
| Binance API REST | OHLCV, funding, OI, trades | REST API | Gratis |
| Binance Data Vision | Trades, aggTrades, klines históricos | CSV bulk download | Gratis |
| Binance WebSocket | Order book, trades, liquidaciones en vivo | WebSocket streams | Gratis |
| CCXT | Acceso unificado a 100+ exchanges | Librería Python | Gratis |

### Datos macro y contexto

| Fuente | Datos | Método | Coste |
|--------|-------|--------|-------|
| FRED API | Tipos de interés, DXY, inflación, M2 | REST API (key gratuita) | Gratis |
| Yahoo Finance (yfinance) | S&P500, VIX, DXY, Gold, bonos | Librería Python | Gratis |
| Fear & Greed Index | Sentimiento crypto | REST API (alternative.me) | Gratis |
| CoinGecko | Market cap, dominance, trending | REST API (tier gratuito) | Gratis |

### Noticias y sentimiento

| Fuente | Datos | Método | Coste |
|--------|-------|--------|-------|
| RSS Feeds | CoinDesk, CoinTelegraph, The Block, Decrypt | feedparser | Gratis |
| Reddit | r/Bitcoin, r/cryptocurrency | API gratuita | Gratis |
| CryptoPanic | Agregador de noticias crypto | API free tier | Gratis |
| Google Trends | Interés en "Bitcoin", "crypto" | pytrends | Gratis |

### Volumen de datos estimado

| Tipo | Período | Tamaño |
|------|---------|--------|
| OHLCV 1m BTC/USDT (spot + futures) | 2019-2026 | ~4 GB |
| Funding rate | 2019-2026 | ~100 MB |
| Open interest | 2020-2026 | ~500 MB |
| aggTrades (order book proxy) | 2022-2026 | ~100-150 GB |
| Macro + sentimiento | 2019-2026 | ~100 MB |

---

## LLM Local — Reemplazo de APIs de Pago

### Stack

```
Ollama (servidor de LLM local)
├── API REST compatible con OpenAI (localhost:11434)
├── Soporte CUDA nativo
├── Gestión automática de modelos
└── Docker compatible
```

### Modelos recomendados para RTX 5080 16GB

| Modelo | VRAM | Velocidad | Calidad sentimiento |
|--------|------|-----------|-------------------|
| Qwen 2.5 14B Q4 (recomendado) | ~9 GB | ~35 tok/s | Excelente |
| Llama 3.1 8B Q4 | ~5 GB | ~60 tok/s | Muy buena |
| Mistral 7B Q4 | ~4.5 GB | ~65 tok/s | Muy buena |
| Phi-3 Mini 3.8B | ~2.5 GB | ~90 tok/s | Buena |

### Gestión de VRAM

```
MODO TRAINING:
  Ollama apagado → 16 GB VRAM disponibles para PyTorch

MODO PRODUCCIÓN (24/7):
  Ollama (Qwen 14B ~9 GB) + inferencia Transformer (~7 GB)

MODO LIGERO:
  Ollama (Llama 8B ~5 GB) + más margen para otros modelos (~11 GB)
```

---

# Fase 0 — Base del Proyecto

## Objetivo

Dejar preparada la infraestructura de desarrollo.

## Tareas

### Sistema operativo

- Instalar Ubuntu 24.04 LTS en SSD 2TB.
- Configurar particionado según esquema definido.
- Configurar GRUB con Ubuntu como default.
- Instalar NVIDIA Driver 550+ para RTX 5080.
- Instalar CUDA 12.x + cuDNN 9.x.
- Verificar GPU con `nvidia-smi`.

### Repositorio

- Crear repositorio `ai-trading-system`.
- Definir estructura de carpetas (ver sección Estructura).
- Inicializar Git + `.gitignore`.
- Crear `pyproject.toml` con dependencias.
- Configurar linter (ruff) y formateador (black).
- Añadir pre-commit hooks.

### Servicios (Docker Compose)

- Crear `docker-compose.yml` con:
  - TimescaleDB (PostgreSQL + extensión temporal).
  - Redis.
  - MLflow (con backend en TimescaleDB).
  - Grafana.
  - Ollama (LLM local con GPU passthrough).
- Configurar volúmenes persistentes en `/data/`.
- Crear `Dockerfile` para la aplicación Python.
- Verificar que todos los servicios se comunican.

### Configuración

- Crear `.env` para claves de exchange y configuraciones.
- Crear `config/` con archivos YAML de configuración.
- Añadir logging centralizado (loguru o structlog).
- Crear esquema de base de datos inicial.

### Testing y CI

- Añadir pytest + estructura de tests.
- Configurar CI básico (GitHub Actions o similar).
- Añadir Makefile con comandos comunes.

## Entregable

```
infraestructura arrancando
+
servicios comunicándose
+
entorno reproducible
+
GPU accesible desde Docker
```

---

# Fase 1 — Data Ingestion

## Objetivo

Recopilar datos históricos y en tiempo real.

## Tareas

### Descarga de datos históricos

- Crear `historical_downloader.py`:
  - Descarga OHLCV 1m BTC/USDT spot desde 2019 (Binance API).
  - Descarga OHLCV 1m BTC/USDT futures desde 2019.
  - Descarga funding rate histórico.
  - Descarga open interest histórico.
  - Guarda en TimescaleDB con formato normalizado.
  - Detecta gaps y los rellena.
  - Checksum de integridad.
- Crear `binance_data_vision_loader.py`:
  - Descarga CSVs de aggTrades de data.binance.vision.
  - Parsea y carga en TimescaleDB.
  - Descomprime automáticamente (.zip).
- Crear `data_quality_validator.py`:
  - Verifica que no hay gaps temporales.
  - Detecta datos duplicados.
  - Compara datos de distintas fuentes.
  - Genera reporte de calidad.

### Captura en tiempo real

- Crear conector WebSocket de Binance.
- Capturar:
  - trades.
  - OHLCV.
  - bid/ask.
  - order book (L2, top 20 niveles).
  - funding rate.
  - open interest.
  - liquidaciones.
- Guardar timestamps correctamente (UTC).
- Normalizar formatos.
- Detectar datos perdidos.
- Implementar reconexión automática del WebSocket.
- Guardar datos raw sin modificar.

### Datos de contexto

- Crear `macro_downloader.py`:
  - FRED API → tipos de interés, DXY, M2, CPI.
  - yfinance → S&P500, VIX, Gold.
  - alternative.me → Fear & Greed Index.
  - CoinGecko → market cap, BTC dominance.
- Crear `news_scraper.py`:
  - RSS feeds → CoinDesk, CoinTelegraph, The Block, Decrypt.
  - Reddit API → r/Bitcoin, r/cryptocurrency.
  - CryptoPanic API → noticias agregadas.
  - Google Trends → pytrends.

## Primera versión

```
BTC/USDT spot + futures
1m candles (2019-presente)
trades
funding rate
open interest
order book L2 (solo real-time)
macro data
```

## Flujo

```
Datos históricos           Datos en vivo
     │                          │
     ▼                          ▼
Historical Downloader     WebSocket Collector
     │                          │
     └──────────┬───────────────┘
                ▼
          TimescaleDB
```

---

# Fase 2 — Feature Engine

## Objetivo

Transformar los datos de mercado en información utilizable por los modelos.

## Features iniciales

```
# Returns
return_1m, return_5m, return_15m, return_1h

# Indicadores técnicos
RSI, MACD, EMA20, EMA50, ATR, Bollinger Bands

# Volatilidad y volumen
volatility_5m, volatility_1h, volume_ratio, VWAP

# Microestructura
bid_ask_spread, orderbook_imbalance

# Funding y derivados
funding_rate, funding_delta, open_interest_delta

# Macro y sentimiento
fear_greed_index, btc_dominance, dxy_change, sp500_change
```

## Tareas

- Crear pipeline de cálculo de features.
- Evitar data leakage (no usar datos futuros).
- Versionar features (esquema versionado).
- Almacenar features históricas en feature store.
- Calcular features en tiempo real (streaming).
- Validar NaN y manejar valores faltantes.
- Detectar outliers.
- Asegurar consistencia entre entrenamiento y tiempo real.
- Crear tests de integridad de features.

## Flujo

```
raw data (TimescaleDB)
     ↓
feature_engine
     ↓
feature_store (TimescaleDB + Redis cache)
```

---

# Fase 3 — Backtesting

## Objetivo

Poder saber si una estrategia realmente habría funcionado.

## Elementos a simular

- Fees (maker/taker de Binance: 0.02% / 0.04%).
- Spread (bid-ask real o estimado).
- Slippage (estimado según volumen).
- Latencia (simulada).
- Tamaño de posición.
- Stop loss.
- Take profit.
- Órdenes market y limit.
- Capital disponible.
- Apalancamiento.

## Benchmarks iniciales

```
Buy & Hold
Random
EMA crossover
RSI overbought/oversold
Momentum
Mean Reversion
```

## Métricas

```
Total Return
Annualized Return
Sharpe Ratio
Sortino Ratio
Max Drawdown
Profit Factor
Win Rate
Avg Win / Avg Loss
Turnover
Total Fees
Calmar Ratio
```

## Tareas

- Crear motor de backtesting event-driven.
- Implementar simulador de ejecución con costes reales.
- Crear sistema de métricas estandarizado.
- Implementar todos los benchmarks.
- Generar reportes automáticos (HTML o Grafana).
- Crear tests del backtester con escenarios conocidos.

## Flujo

```
strategy + features
     ↓
historical data
     ↓
backtesting engine
     ↓
metrics report
```

---

# Fase 4 — Primer Modelo ML (XGBoost / LightGBM)

## Objetivo

Crear el primer modelo serio para buscar edge.

## Target inicial

```
DOWN:    retorno próximo 15m < -0.25%
NEUTRAL: retorno entre -0.25% y +0.25%
UP:      retorno próximo 15m > +0.25%
```

## Entrada

```
features actuales + features anteriores (lag features)
```

## Salida

```
P(DOWN), P(NEUTRAL), P(UP)
```

## Tareas

- Crear dataset builder (train / val / test temporal).
- Implementar purge gap (7 días entre splits).
- Entrenar XGBoost con parámetros iniciales.
- Entrenar LightGBM como alternativa.
- Evaluar métricas predictivas (accuracy, log loss, AUC).
- Analizar feature importance.
- Registrar experimentos en MLflow.
- Ejecutar backtest con predicciones del modelo.
- Comparar contra todos los benchmarks.

## Entregable

Primera prueba seria de si existe una señal explotable.

---

# Fase 5 — Walk-forward Validation

## Objetivo

Validar el sistema fuera de muestra evitando sobreajuste temporal.

## Ejemplo

```
Ventana 1:  TRAIN 2019-2022  →  TEST 2023
Ventana 2:  TRAIN 2020-2023  →  TEST 2024
Ventana 3:  TRAIN 2021-2024  →  TEST 2025
Ventana 4:  TRAIN 2022-2025  →  TEST 2026
```

## Automatización

```
train → predict → backtest → metrics → advance window → repeat
```

## Tareas

- Crear walk-forward engine automatizado.
- Implementar ventanas deslizantes configurables.
- Reentrenar modelo en cada ventana.
- Agregar métricas across todas las ventanas.
- Detectar si el modelo es estable o inconsistente.
- Integrar con MLflow (un experimento por ventana).

## Criterio

Esta fase decide si el modelo merece seguir existiendo.
Si el modelo no supera Buy & Hold de forma consistente en todas las ventanas, se descarta.

---

# Fase 6 — Paper Trading

## Objetivo

Probar el sistema con datos reales sin arriesgar dinero.

## Flujo

```
Market data (WebSocket en vivo)
     ↓
features realtime
     ↓
XGBoost inference
     ↓
signal
     ↓
risk manager
     ↓
paper broker (simulado)
```

## Datos a guardar por operación

```
timestamp
features_snapshot
prediction (UP/DOWN/NEUTRAL)
confidence
decision (BUY/SELL/HOLD)
position_size
entry_price
exit_price
PnL
fees_simuladas
slippage_estimado
```

## Tareas

- Crear PaperBroker (simulador de broker).
- Crear trading loop principal.
- Implementar logging de todas las decisiones.
- Crear dashboard en Grafana para paper trading.
- Implementar comparación automática paper vs backtest.

## Requisito

Dejar el sistema funcionando durante un mínimo de 4 semanas antes de escalar.
Verificar que paper trading ≈ backtest.

---

# Fase 7 — Risk Manager

## Objetivo

Crear una capa de seguridad independiente de los modelos.

## Parámetros

```
max_risk_per_trade     (ej: 1% del capital)
max_position_size      (ej: 20% del capital)
max_daily_loss         (ej: 2% del capital)
max_drawdown           (ej: 10% del capital)
max_leverage           (ej: 3x)
max_open_positions     (ej: 3)
min_confidence         (ej: 0.65)
min_edge_after_costs   (ej: predicted_return > fees + spread + margin)
```

## Reglas de ejemplo

```
confidence < 0.65
→ no trade

predicted_edge < costs + margin
→ no trade

daily_loss > 2%
→ stop trading hasta mañana

drawdown > 10%
→ stop trading, alerta, revisión manual

volatility > threshold
→ reducir tamaño de posición
```

## Tareas

- Crear módulo de risk manager independiente.
- Implementar todas las reglas configurables via YAML.
- Crear tests exhaustivos del risk manager.
- Implementar kill switch manual y automático.
- Crear alertas por email/Telegram cuando se activan reglas.
- Documentar todas las reglas y sus justificaciones.

## Principio

El Risk Manager no debe poder ser modificado por los modelos.
Es una capa de seguridad que opera de forma independiente.

---

# Fase 8 — Transformer Temporal

## Objetivo

Añadir un modelo de deep learning especializado en secuencias temporales.

## Dataset

```
240 últimas velas × 50-100 features
```

## Modelos candidatos

```
PatchTST
Temporal Fusion Transformer (TFT)
```

## Targets

```
return_5m, return_15m, return_1h
volatility
direction (UP/DOWN/NEUTRAL)
```

## Tareas

- Crear dataset secuencial (sliding windows).
- Crear DataLoader para PyTorch.
- Implementar trainer con:
  - Mixed precision (FP16/BF16).
  - Gradient accumulation.
  - Learning rate scheduling.
  - Early stopping.
- Guardar checkpoints en MLflow.
- Ejecutar hyperparameter search con Optuna.
- Ejecutar walk-forward validation.
- Ejecutar backtest.
- Comparar contra XGBoost.

## Gestión de VRAM durante entrenamiento

```
Apagar Ollama → 16 GB VRAM disponibles
Batch size: ajustar hasta llenar ~14 GB
Mixed precision: obligatorio para maximizar rendimiento
```

## Criterio

Si el Transformer no mejora el sistema significativamente, se elimina.

---

# Fase 9 — Order Book Model

## Objetivo

Crear un modelo especializado en microestructura de mercado.

## Dataset

```
timestamp
bid_1...bid_n (top 20 niveles)
ask_1...ask_n (top 20 niveles)
spread
microprice
imbalance
market_buys (aggTrades)
market_sells (aggTrades)
```

## Datos históricos

Usar aggTrades de Binance Data Vision como proxy del order book.
Datos de order book real: capturar en vivo desde Fase 1.

## Targets

```
movement_10s
movement_30s
movement_1m
movement_5m
```

## Modelos

```
Primera versión: LightGBM
Posteriormente:  CNN o Transformer (si mejora)
```

## Tareas

- Descargar aggTrades históricos de data.binance.vision.
- Crear features de microestructura.
- Entrenar LightGBM baseline.
- Walk-forward validation.
- Integrar con la capa rápida de ejecución.

## Principio

Cada modelo nuevo debe compararse contra un baseline simple.
La capa rápida no decide QUÉ operar, sino CUÁNDO ejecutar.

---

# Fase 10 — Regime Detector

## Objetivo

Identificar el tipo de mercado actual.

## Regímenes iniciales

```
trend_up
trend_down
range / lateral
high_volatility
low_volatility
```

## Implementación progresiva

```
Paso 1: Reglas + clustering (KMeans, DBSCAN)
Paso 2: HMM (Hidden Markov Model)
Paso 3: Modelo ML (si aporta valor)
```

## Función

El detector de régimen no compra ni vende.
Su función es indicar qué estrategia o pesos del ensemble tienen más sentido en cada régimen.

## Tareas

- Implementar detector basado en reglas (volatilidad, tendencia, volumen).
- Implementar clustering.
- Evaluar HMM si las reglas son insuficientes.
- Integrar con el ensemble como feature adicional.
- Validar que el detector mejora el rendimiento global.

---

# Fase 11 — Ensemble / Meta-modelo

## Objetivo

Combinar las señales de múltiples modelos.

## Inputs

```
xgb_prediction
transformer_prediction
orderbook_prediction
market_regime
volatility
spread
model_disagreement
news_sentiment (del LLM local)
macro_context
```

## Output

```
expected_return
confidence
```

## Modelos candidatos

```
Logistic Regression
XGBoost (meta-learner)
Weighted Average (baseline)
```

No es necesario utilizar una red neuronal grande.

## Tareas

- Crear pipeline de recopilación de predicciones de todos los modelos.
- Implementar meta-modelo con walk-forward.
- Evaluar si el ensemble mejora sobre el mejor modelo individual.
- Si no mejora, usar el mejor modelo solo.

---

# Fase 12 — Noticias + LLM Local

## Objetivo

Convertir noticias y contexto externo en señales estructuradas usando LLM local.

## Stack

```
Ollama + Qwen 2.5 14B Q4 (en RTX 5080, ~9 GB VRAM)
Alternativa ligera: Llama 3.1 8B Q4 (~5 GB VRAM)
```

## Fuentes (gratuitas)

```
RSS Feeds (feedparser)
Reddit API (praw)
CryptoPanic API (free tier)
Google Trends (pytrends)
```

## Pipeline

```
RSS/Reddit/CryptoPanic
     ↓
Filtro de relevancia (keywords: bitcoin, btc, crypto, regulation, etf, fed...)
     ↓
Ollama (Qwen 14B local)
     ↓
Señal estructurada JSON
     ↓
Ensemble
```

## Salida del LLM

```json
{
  "sentiment": -0.42,
  "impact": 0.82,
  "time_horizon": "1-6h",
  "category": "regulation",
  "confidence": 0.75
}
```

## Gestión de VRAM en producción

```
Modo producción: Ollama (Qwen 14B ~9GB) + Transformer inference (~7GB)
Modo ligero:     Ollama (Llama 8B ~5GB)  + más margen (~11GB)
Modo training:   Ollama apagado          + 16GB completos para PyTorch
```

## Principio

El LLM no ejecuta operaciones directamente.
El LLM genera datos estructurados que alimentan al ensemble como una feature más.

---

# Fase 13 — Reinforcement Learning (Opcional / Experimental)

## Objetivo

Utilizar RL para optimizar position sizing y política de exposición.

> **NOTA**: Esta fase es experimental y de alto riesgo. Solo implementar
> si todas las fases anteriores son estables y rentables.

## Inputs

```
predicciones del ensemble
market regime
volatility
current position
PnL acumulado
drawdown actual
```

## Output

```
position_size: float (-1.0 a +1.0)

-1.0 → short 100%
-0.2 → small short
 0.0 → flat
+0.3 → small long
+1.0 → max long
```

## Alternativa recomendada (más segura)

```
Fracción fija (ej: 2% por trade)
Kelly Criterion (basado en win rate y payoff ratio)
Sizing por volatilidad (ATR-based)
```

Usar la alternativa por defecto. RL solo si la alternativa se queda corta.

## Principio

No pedir al RL que descubra todo el mercado desde cero.

---

# Fase 14 — Execution Engine

## Objetivo

Crear una interfaz genérica para ejecutar operaciones.

## Interfaz

```python
class Broker(ABC):
    def place_order(self, symbol, side, size, order_type) -> Order
    def cancel_order(self, order_id) -> bool
    def get_position(self, symbol) -> Position
    def get_balance(self) -> Balance
    def get_open_orders(self) -> list[Order]
```

## Implementaciones

```
PaperBroker     (Fase 6 — simulador)
BinanceBroker   (Fase 15 — trading real)
```

## Tareas

- Crear interfaz abstracta de Broker.
- Implementar PaperBroker con simulación realista.
- Implementar BinanceBroker con API REST + WebSocket.
- Añadir retry logic y manejo de errores.
- Crear tests para ambas implementaciones.
- Implementar rate limiting para API de Binance.

## Beneficio

Permite cambiar de exchange sin rehacer el sistema.

---

# Fase 15 — Trading Real

## Objetivo

Validar que el comportamiento real coincide con paper trading y backtesting.

## Escalado sugerido

```
Fase 1:   50 €    (2-4 semanas)
Fase 2:   100 €   (2-4 semanas)
Fase 3:   500 €   (4-8 semanas)
Fase 4:   1.000 € (4-8 semanas)
Fase 5:   escalado gradual
```

## Criterio principal

```
backtest ≈ paper ≈ real
```

Si divergen mucho (>20% de diferencia en Sharpe), existe un problema de ejecución, datos o sobreajuste.

## Tareas

- Crear cuenta de Binance con capital inicial de 50€.
- Configurar API keys con permisos mínimos (solo trading, no withdraw).
- Activar BinanceBroker en producción.
- Monitorizar 24/7 durante cada fase.
- Comparar métricas reales vs paper vs backtest.
- Documentar todas las divergencias encontradas.

## Requisitos mínimos para pasar a dinero real

```
✓ Paper trading rentable durante 4+ semanas
✓ Walk-forward Sharpe > 1.0 en todas las ventanas
✓ Max drawdown < 10% en paper trading
✓ Backtest ≈ paper (divergencia < 20%)
✓ Risk manager probado y funcionando
✓ Alertas configuradas y probadas
✓ Kill switch manual probado
```

---

# Fase 16 — Monitoring

## Objetivo

Supervisar rendimiento, riesgo, modelos y salud del sistema.

## Dashboard de Grafana

```
Portfolio:       value, PnL diario, PnL acumulado
Riesgo:          drawdown, daily loss, leverage
Modelos:         predictions, confidence, accuracy rolling
Régimen:         market regime actual, historial
Ejecución:       fees, slippage, latency
Infraestructura: CPU, GPU, RAM, disk, WebSocket status
Model health:    model disagreement, feature drift
```

## Alertas

```
daily_loss > threshold        → Telegram
model_offline                 → Telegram
market_feed_disconnected      → Telegram
database_failure              → Telegram
execution_failure             → Telegram
abnormal_latency              → Telegram
drawdown > max_drawdown       → Telegram + kill switch
model_accuracy_degradation    → Telegram
feature_distribution_shift    → Log + MLflow
```

## Tareas

- Configurar Grafana con datasources (TimescaleDB, Redis).
- Crear dashboards para cada categoría.
- Configurar Telegram bot para alertas.
- Implementar health checks automáticos.
- Crear alertas con umbrales configurables.

---

# Fase 17 — Experimentación Automática

## Objetivo

Aprovechar CPU y GPU para ejecutar muchos experimentos de forma controlada.

## Herramientas

```
Optuna   → optimización de hiperparámetros
Ray Tune → paralelización de experimentos
MLflow   → tracking y comparación
```

## Flujo

```
model + hyperparameter space
     ↓
100-1000 trials (Optuna)
     ↓
walk-forward validation por trial
     ↓
rank by Sharpe (no solo accuracy)
     ↓
mejor configuración → shadow mode → producción
```

## Regla fundamental

El test final nunca participa en la optimización.

---

# Feedback Loop / Retraining

## Flujo de retraining semanal

```
Scheduler (Domingo 02:00 AM)
     ↓
Retrainer
  1. Descarga nuevos datos de la última semana
  2. Recalcula features para ventana completa
  3. Entrena modelo candidato (ventana rolling 3 años)
  4. Walk-forward validation del candidato
     ↓
Evaluator
  ¿Nuevo modelo > actual?
  NO → Mantener modelo actual (log en MLflow)
  SÍ → Shadow mode 48h
     ↓
Promoter
  ¿Shadow mode OK?
  NO → Mantener modelo actual
  SÍ → Promover nuevo modelo a producción
```

## Reglas del retraining

```
# CUÁNDO reentrenar
schedule:           weekly (domingos noche)
emergency_triggers:
  - sharpe_rolling_30d < 0
  - model_accuracy < baseline - 5%
  - regime_change_detected

# CON QUÉ DATOS
training_window:    rolling 3 años
validation_window:  últimos 3 meses
test_window:        último mes (INTOCABLE)

# SEPARACIÓN
purge_gap:          7 días entre train/val/test
embargo_period:     24h (no usar datos recientes en train)

# CRITERIO DE PROMOCIÓN
promotion_criteria:
  - sharpe_new > sharpe_current * 0.95
  - max_drawdown_new < max_drawdown_current * 1.1
  - shadow_mode_48h_profitable
  - no_anomalous_behavior
```

## Detección de model drift

```
Monitorizar continuamente:
1. Prediction accuracy (rolling 7d vs 30d)
2. Feature distribution shift (KL-divergence)
3. Confidence calibration
4. Regime-specific performance
```

---

# Workstreams / Epics

```
EPIC 1  — Infrastructure (Fase 0)
EPIC 2  — Market Data (Fase 1)
EPIC 3  — Feature Engineering (Fase 2)
EPIC 4  — Backtesting (Fase 3)
EPIC 5  — ML Baselines (Fase 4)
EPIC 6  — Walk-forward Validation (Fase 5)
EPIC 7  — Paper Trading (Fase 6)
EPIC 8  — Risk Management (Fase 7)
EPIC 9  — Deep Learning (Fase 8)
EPIC 10 — Order Book Intelligence (Fase 9)
EPIC 11 — Market Regime (Fase 10)
EPIC 12 — Ensemble (Fase 11)
EPIC 13 — News / LLM Local (Fase 12)
EPIC 14 — Reinforcement Learning [Opcional] (Fase 13)
EPIC 15 — Execution (Fase 14)
EPIC 16 — Monitoring (Fase 16)
EPIC 17 — Live Trading (Fase 15)
EPIC 18 — Auto Experimentation (Fase 17)
EPIC 19 — Retraining Loop
```

---

# Orden Recomendado de Implementación

```
Fase 0:  Infraestructura (Ubuntu, Docker, servicios)
    ↓
Fase 1:  Datos (históricos + real-time)
    ↓
Fase 2:  Features
    ↓
Fase 3:  Backtester + benchmarks
    ↓
Fase 4:  XGBoost / LightGBM
    ↓
Fase 5:  Walk-forward validation
    ↓
Fase 6:  Paper trading
    ↓
Fase 7:  Risk manager
    ↓
Fase 8:  Transformer temporal
    ↓
Fase 9:  Order book model
    ↓
Fase 10: Regime detector
    ↓
Fase 11: Ensemble
    ↓
Fase 12: LLM local (noticias)
    ↓
Fase 13: RL (opcional)
    ↓
Fase 14: Execution engine
    ↓
Fase 15: Trading real (50€ → escalado)
    ↓
Fase 16: Monitoring completo
    ↓
Fase 17: Experimentación automática
    ↓
Ongoing: Retraining loop semanal
```

---

# Arquitectura Final

```
                         MARKET
                           │
             ┌─────────────┼─────────────┐
             │             │             │
           trades        OHLCV       orderbook
             │             │             │
             └─────────────┼─────────────┘
                           ↓
                    Market Collector
                      │         │
                      ▼         ▼
                TimescaleDB   Redis
                      │
                      ▼
                 Feature Engine
                      ↓
                Feature Store
                      │
        ┌─────────────┼─────────────────┐
        │             │                 │
        ▼             ▼                 ▼
     XGBoost     Transformer        Orderbook
        │             │                 │
        └─────────┬───┴─────────────────┘
                  │
           Regime Detector
                  │
                  ▼
               Ensemble
                  │
            ┌─────┴─────┐
            │           │
        LLM Local     Risk
        (Ollama)     Manager
            │           │
            └─────┬─────┘
                  ▼
           Execution Engine
              │          │
              ▼          ▼
           Paper       Real
              │          │
              └────┬─────┘
                   ▼
                Grafana
                   │
                   ▼
            Retraining Loop
            (feedback semanal)
```

---

# Principios del Proyecto

1. No construir modelos complejos antes de validar los datos y el backtesting.
2. Cada modelo nuevo debe demostrar que mejora un baseline simple.
3. Nunca usar datos futuros durante entrenamiento o generación de features.
4. Simular fees, spread, slippage y latencia.
5. Mantener Risk Manager separado de los modelos.
6. No permitir que un LLM opere directamente.
7. Validar con walk-forward.
8. Comparar siempre contra Buy & Hold y estrategias simples.
9. Registrar todos los experimentos en MLflow.
10. Escalar a dinero real únicamente después de paper trading estable.
11. El objetivo no es construir la IA más compleja, sino el sistema más difícil de engañar a sí mismo.
12. Coste cero: no pagar por datos, APIs de LLM ni cloud.
13. Todo corre en local: la máquina es el datacenter.
