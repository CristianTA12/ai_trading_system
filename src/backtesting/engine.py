"""Sequential OPEN / CLOSE execution for unlevered spot, with one long position."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

STEP = pd.Timedelta(minutes=15)


@dataclass(frozen=True)
class ExecutionConfig:
    initial_capital: float = 10_000.0
    position_fraction: float = 1.0
    maker_fee: float = 0.0002
    taker_fee: float = 0.0004
    slippage: float = 0.0001
    liquidity: str = "taker"

    def __post_init__(self) -> None:
        values = (
            self.initial_capital,
            self.position_fraction,
            self.maker_fee,
            self.taker_fee,
            self.slippage,
        )
        if not np.isfinite(values).all() or self.initial_capital <= 0:
            raise ValueError("Capital y parámetros deben ser finitos; capital > 0")
        if not 0 < self.position_fraction <= 1:
            raise ValueError("position_fraction debe estar en (0, 1]")
        if any(not 0 <= value < 1 for value in values[2:]):
            raise ValueError("Comisiones y slippage deben estar en [0, 1)")
        if self.liquidity not in {"maker", "taker"}:
            raise ValueError("liquidity debe ser maker o taker")

    @property
    def fee_rate(self) -> float:
        return self.maker_fee if self.liquidity == "maker" else self.taker_fee


@dataclass
class BacktestResult:
    equity: pd.DataFrame
    fills: pd.DataFrame
    trades: pd.DataFrame
    exposure: float


def validate_index(index: pd.Index) -> None:
    if (
        not isinstance(index, pd.DatetimeIndex)
        or str(index.tz) != "UTC"
        or index.has_duplicates
        or not index.is_monotonic_increasing
        or index.hasnans
    ):
        raise ValueError("Se requiere índice UTC, ordenado, único y sin NaT")


def run_backtest(
    bars: pd.DataFrame, targets: pd.Series, config: ExecutionConfig | None = None
) -> BacktestResult:
    """A target available at t trades at open(t); missing targets mean flat.

    Maker is a fee sensitivity scenario, not a limit order fill simulator.
    Gaps are not filled or anticipated. The final position is sold at the last close.
    """
    config = config or ExecutionConfig()
    validate_index(bars.index)
    validate_index(targets.index)
    if bars.empty or (bars.index != bars.index.floor("15min")).any():
        raise ValueError("Se requieren velas de 15 minutos no vacías")
    prices = bars[["open", "high", "low", "close"]]
    if (
        not np.isfinite(prices.to_numpy()).all()
        or (prices <= 0).any().any()
        or (bars.high < prices[["open", "close", "low"]].max(axis=1)).any()
        or (bars.low > prices[["open", "close", "high"]].min(axis=1)).any()
    ):
        raise ValueError("Precios OHLC inválidos")
    if not targets.isin([0, 1]).all():
        raise ValueError("Las posiciones objetivo deben ser 0 (efectivo) o 1 (largo)")
    aligned = targets.reindex(bars.index, fill_value=0).to_numpy()
    cash, quantity = config.initial_capital, 0.0
    entry_cost, entry_time = 0.0, None
    fills, trades = [], []
    curve = [(bars.index[0], cash, cash, quantity)]
    exposed = 0

    def execute(side: str, reference: float, timestamp: pd.Timestamp, reason: str) -> None:
        nonlocal cash, quantity, entry_cost, entry_time
        price = reference * (1 + config.slippage if side == "buy" else 1 - config.slippage)
        if side == "buy":
            entry_cost = cash * config.position_fraction
            quantity = entry_cost / (price * (1 + config.fee_rate))
            size = quantity
            fee = size * price * config.fee_rate
            cash -= entry_cost
            entry_time = timestamp
        else:
            size = quantity
            fee = size * price * config.fee_rate
            proceeds = size * price - fee
            cash += proceeds
            trades.append(
                (entry_time, timestamp, size, entry_cost, proceeds, proceeds - entry_cost, reason)
            )
            quantity = 0.0
        fills.append(
            (
                timestamp,
                side,
                size,
                reference,
                price,
                fee,
                size * abs(price - reference),
                size * price,
                reason,
            )
        )

    for i, row in enumerate(bars.itertuples()):
        timestamp = row.Index
        if quantity > 0 and aligned[i] == 0:
            execute("sell", row.open, timestamp, "signal")
        elif quantity == 0 and aligned[i] == 1:
            execute("buy", row.open, timestamp, "signal")
        exposed += int(quantity > 0)
        close_time = timestamp + STEP
        if i == len(bars) - 1 and quantity > 0:
            execute("sell", row.close, close_time, "end_of_period")
        curve.append((close_time, cash + quantity * row.close, cash, quantity))

    return BacktestResult(
        pd.DataFrame(curve, columns=["time", "equity", "cash", "quantity"]).set_index("time"),
        pd.DataFrame(
            fills,
            columns=[
                "time",
                "side",
                "quantity",
                "reference_price",
                "fill_price",
                "fee",
                "slippage_cost",
                "notional",
                "reason",
            ],
        ),
        pd.DataFrame(
            trades,
            columns=[
                "entry_time",
                "exit_time",
                "quantity",
                "entry_cost",
                "exit_proceeds",
                "net_pnl",
                "reason",
            ],
        ),
        exposed / len(bars),
    )
