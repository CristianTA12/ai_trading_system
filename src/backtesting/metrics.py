"""Net trading metrics; daily UTC returns and 365-day annualization."""

import numpy as np

from src.backtesting.engine import BacktestResult


def compute_metrics(result: BacktestResult) -> dict[str, float | int | None]:
    equity = result.equity.equity
    daily = equity.resample("1D", closed="right", label="right").last()
    # Some pandas versions emit an empty trailing bin at an exact midnight endpoint.
    # Carry values across internal gaps only, never beyond the observed period.
    daily = daily.loc[daily.first_valid_index() : daily.last_valid_index()].ffill()
    returns = daily.pct_change(fill_method=None).dropna()
    std = returns.std(ddof=1)
    downside = np.sqrt(np.mean(np.minimum(returns, 0) ** 2)) if len(returns) else 0
    pnl = result.trades.net_pnl.astype(float)
    losses = -pnl[pnl < 0].sum()
    return {
        "total_return": float(equity.iloc[-1] / equity.iloc[0] - 1),
        "final_equity": float(equity.iloc[-1]),
        "sharpe": float(np.sqrt(365) * returns.mean() / std) if std > 0 else None,
        "sortino": float(np.sqrt(365) * returns.mean() / downside) if downside > 0 else None,
        "max_drawdown": float((1 - equity / equity.cummax()).max()),
        "profit_factor": float(pnl[pnl > 0].sum() / losses) if losses > 0 else None,
        "win_rate": float((pnl > 0).mean()) if len(pnl) else None,
        "trades": len(pnl),
        "fees_paid": float(result.fills.fee.sum()),
        "slippage_cost": float(result.fills.slippage_cost.sum()),
        "turnover": float(result.fills.notional.sum() / equity.iloc[0]),
        "exposure": result.exposure,
        "daily_observations": len(returns),
    }
