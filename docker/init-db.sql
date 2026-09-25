-- ============================================
-- AI Trading System — Database Initialization
-- ============================================
-- Este script se ejecuta automáticamente al crear
-- el contenedor de TimescaleDB por primera vez.
-- ============================================

-- Activar extensión TimescaleDB
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ============================================
-- TABLAS DE DATOS DE MERCADO
-- ============================================

-- OHLCV (velas)
CREATE TABLE IF NOT EXISTS ohlcv (
    time        TIMESTAMPTZ NOT NULL,
    symbol      TEXT        NOT NULL,
    exchange    TEXT        NOT NULL DEFAULT 'binance',
    timeframe   TEXT        NOT NULL DEFAULT '1m',
    open        DOUBLE PRECISION NOT NULL,
    high        DOUBLE PRECISION NOT NULL,
    low         DOUBLE PRECISION NOT NULL,
    close       DOUBLE PRECISION NOT NULL,
    volume      DOUBLE PRECISION NOT NULL,
    trades      INTEGER,
    UNIQUE (time, symbol, exchange, timeframe)
);
SELECT create_hypertable('ohlcv', 'time', if_not_exists => TRUE);

-- Trades
CREATE TABLE IF NOT EXISTS trades (
    time        TIMESTAMPTZ      NOT NULL,
    symbol      TEXT             NOT NULL,
    exchange    TEXT             NOT NULL DEFAULT 'binance',
    trade_id    BIGINT,
    price       DOUBLE PRECISION NOT NULL,
    quantity    DOUBLE PRECISION NOT NULL,
    side        TEXT             NOT NULL, -- 'buy' or 'sell'
    UNIQUE (time, symbol, exchange, trade_id)
);
SELECT create_hypertable('trades', 'time', if_not_exists => TRUE);

-- Order Book Snapshots
CREATE TABLE IF NOT EXISTS orderbook_snapshots (
    time        TIMESTAMPTZ NOT NULL,
    symbol      TEXT        NOT NULL,
    exchange    TEXT        NOT NULL DEFAULT 'binance',
    bids        JSONB       NOT NULL, -- [{price, qty}, ...]
    asks        JSONB       NOT NULL, -- [{price, qty}, ...]
    spread      DOUBLE PRECISION,
    mid_price   DOUBLE PRECISION,
    imbalance   DOUBLE PRECISION
);
SELECT create_hypertable('orderbook_snapshots', 'time', if_not_exists => TRUE);

-- Funding Rate
CREATE TABLE IF NOT EXISTS funding_rate (
    time           TIMESTAMPTZ      NOT NULL,
    symbol         TEXT             NOT NULL,
    exchange       TEXT             NOT NULL DEFAULT 'binance',
    funding_rate   DOUBLE PRECISION NOT NULL,
    UNIQUE (time, symbol, exchange)
);
SELECT create_hypertable('funding_rate', 'time', if_not_exists => TRUE);

-- Open Interest
CREATE TABLE IF NOT EXISTS open_interest (
    time            TIMESTAMPTZ      NOT NULL,
    symbol          TEXT             NOT NULL,
    exchange        TEXT             NOT NULL DEFAULT 'binance',
    open_interest   DOUBLE PRECISION NOT NULL,
    UNIQUE (time, symbol, exchange)
);
SELECT create_hypertable('open_interest', 'time', if_not_exists => TRUE);

-- Liquidaciones
CREATE TABLE IF NOT EXISTS liquidations (
    time        TIMESTAMPTZ      NOT NULL,
    symbol      TEXT             NOT NULL,
    exchange    TEXT             NOT NULL DEFAULT 'binance',
    side        TEXT             NOT NULL, -- 'long' or 'short'
    price       DOUBLE PRECISION NOT NULL,
    quantity    DOUBLE PRECISION NOT NULL
);
SELECT create_hypertable('liquidations', 'time', if_not_exists => TRUE);

-- ============================================
-- TABLAS DE CONTEXTO / MACRO
-- ============================================

-- Datos macro
CREATE TABLE IF NOT EXISTS macro_data (
    time        TIMESTAMPTZ      NOT NULL,
    indicator   TEXT             NOT NULL, -- 'dxy', 'sp500', 'vix', 'fear_greed', etc.
    value       DOUBLE PRECISION NOT NULL,
    source      TEXT             NOT NULL DEFAULT 'unknown',
    UNIQUE (time, indicator, source)
);
SELECT create_hypertable('macro_data', 'time', if_not_exists => TRUE);

-- Noticias procesadas por LLM
CREATE TABLE IF NOT EXISTS news_signals (
    time          TIMESTAMPTZ      NOT NULL,
    source        TEXT             NOT NULL, -- 'coindesk', 'reddit', etc.
    title         TEXT             NOT NULL,
    url           TEXT,
    sentiment     DOUBLE PRECISION, -- -1.0 to 1.0
    impact        DOUBLE PRECISION, -- 0.0 to 1.0
    time_horizon  TEXT,             -- '1h', '6h', '24h'
    category      TEXT,             -- 'regulation', 'adoption', etc.
    llm_model     TEXT,             -- 'qwen2.5:14b', etc.
    raw_response  JSONB
);
SELECT create_hypertable('news_signals', 'time', if_not_exists => TRUE);

-- ============================================
-- TABLAS DE FEATURES
-- ============================================

-- Feature Store
CREATE TABLE IF NOT EXISTS features (
    time        TIMESTAMPTZ NOT NULL,
    symbol      TEXT        NOT NULL,
    timeframe   TEXT        NOT NULL DEFAULT '1m',
    features    JSONB       NOT NULL, -- todas las features como JSON
    version     INTEGER     NOT NULL DEFAULT 1,
    UNIQUE (time, symbol, timeframe, version)
);
SELECT create_hypertable('features', 'time', if_not_exists => TRUE);

-- ============================================
-- TABLAS DE TRADING
-- ============================================

-- Predicciones de modelos
CREATE TABLE IF NOT EXISTS predictions (
    time          TIMESTAMPTZ      NOT NULL,
    symbol        TEXT             NOT NULL,
    model_name    TEXT             NOT NULL, -- 'xgboost_v1', 'transformer_v2', etc.
    model_version TEXT,
    prediction    JSONB            NOT NULL, -- {up: 0.6, neutral: 0.3, down: 0.1}
    confidence    DOUBLE PRECISION,
    features_hash TEXT             -- hash de las features usadas
);
SELECT create_hypertable('predictions', 'time', if_not_exists => TRUE);

-- Operaciones (paper y real)
CREATE TABLE IF NOT EXISTS trades_log (
    time          TIMESTAMPTZ      NOT NULL,
    trade_id      TEXT             NOT NULL,
    symbol        TEXT             NOT NULL,
    mode          TEXT             NOT NULL, -- 'paper' or 'live'
    side          TEXT             NOT NULL, -- 'buy' or 'sell'
    order_type    TEXT             NOT NULL, -- 'market' or 'limit'
    price         DOUBLE PRECISION NOT NULL,
    quantity      DOUBLE PRECISION NOT NULL,
    fee           DOUBLE PRECISION DEFAULT 0,
    slippage      DOUBLE PRECISION DEFAULT 0,
    pnl           DOUBLE PRECISION,
    confidence    DOUBLE PRECISION,
    model_name    TEXT,
    risk_check    JSONB,           -- resultado del risk manager
    UNIQUE (time, trade_id)
);
SELECT create_hypertable('trades_log', 'time', if_not_exists => TRUE);

-- Portfolio state
CREATE TABLE IF NOT EXISTS portfolio_state (
    time          TIMESTAMPTZ      NOT NULL,
    mode          TEXT             NOT NULL, -- 'paper' or 'live'
    balance       DOUBLE PRECISION NOT NULL,
    equity        DOUBLE PRECISION NOT NULL,
    drawdown      DOUBLE PRECISION NOT NULL DEFAULT 0,
    daily_pnl     DOUBLE PRECISION NOT NULL DEFAULT 0,
    open_positions INTEGER         NOT NULL DEFAULT 0,
    leverage      DOUBLE PRECISION NOT NULL DEFAULT 0
);
SELECT create_hypertable('portfolio_state', 'time', if_not_exists => TRUE);

-- ============================================
-- ÍNDICES
-- ============================================

CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_time ON ohlcv (symbol, time DESC);
CREATE INDEX IF NOT EXISTS idx_trades_symbol_time ON trades (symbol, time DESC);
CREATE INDEX IF NOT EXISTS idx_funding_symbol_time ON funding_rate (symbol, time DESC);
CREATE INDEX IF NOT EXISTS idx_oi_symbol_time ON open_interest (symbol, time DESC);
CREATE INDEX IF NOT EXISTS idx_features_symbol_time ON features (symbol, time DESC);
CREATE INDEX IF NOT EXISTS idx_predictions_model_time ON predictions (model_name, time DESC);
CREATE INDEX IF NOT EXISTS idx_trades_log_mode_time ON trades_log (mode, time DESC);

-- ============================================
-- POLÍTICAS DE RETENCIÓN (opcional)
-- ============================================
-- Descomentar si se necesita limitar el tamaño:
-- SELECT add_retention_policy('orderbook_snapshots', INTERVAL '6 months');
-- SELECT add_retention_policy('trades', INTERVAL '2 years');
