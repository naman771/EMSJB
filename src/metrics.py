import numpy as np
import pandas as pd
from src.config import BATTERY_ENERGY


def total_profit(df):
    """Sum of all hourly profits."""
    return float(df["Profit"].sum())


def avg_daily_profit(df):
    """Average profit per day."""
    if "Timestamp" in df.columns:
        daily = df.copy()
        daily["date"] = pd.to_datetime(daily["Timestamp"]).dt.date
        daily_totals = daily.groupby("date")["Profit"].sum()
        return float(daily_totals.mean())
    n_days = max(1, len(df) / 24)
    return float(df["Profit"].sum() / n_days)


def total_cycles(df):
    """
    Count equivalent full cycles.
    One full cycle = discharge BATTERY_ENERGY kWh.
    """
    total_discharge = df.loc[df["Battery_Power"] > 0, "Battery_Power"].sum()
    return float(total_discharge / BATTERY_ENERGY) if BATTERY_ENERGY > 0 else 0.0


def profit_per_cycle(df):
    """Profit earned per full equivalent cycle."""
    cycles = total_cycles(df)
    if cycles == 0:
        return 0.0
    return float(df["Profit"].sum() / cycles)


def max_drawdown(df):
    """
    Maximum peak-to-trough drop in cumulative profit.
    Returns a positive number representing the worst loss streak.
    """
    cum_profit = df["Profit"].cumsum()
    running_max = cum_profit.cummax()
    drawdowns = running_max - cum_profit
    return float(drawdowns.max())


def sharpe_ratio(df):
    """
    Annualised Sharpe ratio of hourly profits.
    Assumes risk-free rate ≈ 0 for simplicity.
    """
    hourly = df["Profit"]
    if hourly.std() == 0:
        return 0.0
    # Annualise: √8760 hours per year
    return float((hourly.mean() / hourly.std()) * np.sqrt(8760))


def utilization_rate(df):
    """
    Fraction of hours where the battery is actively charging or discharging
    (i.e., abs(Battery_Power) > 0).
    """
    active = (df["Battery_Power"].abs() > 1e-6).sum()
    return float(active / len(df)) if len(df) > 0 else 0.0


def compute_all_metrics(df):
    """Return a dict of all key performance metrics."""
    return {
        "total_profit": total_profit(df),
        "avg_daily_profit": avg_daily_profit(df),
        "total_cycles": total_cycles(df),
        "profit_per_cycle": profit_per_cycle(df),
        "max_drawdown": max_drawdown(df),
        "sharpe_ratio": sharpe_ratio(df),
        "utilization_rate": utilization_rate(df),
    }
