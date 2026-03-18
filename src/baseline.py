import numpy as np
import pandas as pd
from src.config import BATTERY_POWER, BATTERY_ENERGY, ETA, DEGR_COST


def naive_strategy(df):
    """
    Naive peak/off-peak strategy:
    - Identify the 4 cheapest hours of each day → charge at max power
    - Identify the 4 most expensive hours of each day → discharge at max power
    - Idle otherwise
    Returns a DataFrame with the same schema as simulation output.
    """
    results = []
    soc = 0.0

    df = df.copy()
    df["date"] = df["Timestamp"].dt.date

    for date, group in df.groupby("date"):
        sorted_hours = group.sort_values("Price_INR_kWh")
        cheap_indices = sorted_hours.head(4).index.tolist()
        expensive_indices = sorted_hours.tail(4).index.tolist()

        for idx in group.index:
            row = df.loc[idx]
            price = row["Price_INR_kWh"]

            if idx in cheap_indices and soc < BATTERY_ENERGY:
                # Charge
                q = -min(BATTERY_POWER, (BATTERY_ENERGY - soc) / ETA)
                soc_next = soc - q * ETA
            elif idx in expensive_indices and soc > 0:
                # Discharge
                q = min(BATTERY_POWER, soc * ETA)
                soc_next = soc - q / ETA
            else:
                q = 0.0
                soc_next = soc

            soc_next = max(0, min(BATTERY_ENERGY, soc_next))
            degr = DEGR_COST * abs(q)
            profit = q * price - degr

            results.append({
                "Timestamp": row["Timestamp"],
                "Price": price,
                "Battery_Power": q,
                "SOC": soc,
                "Profit": profit,
            })
            soc = soc_next

    return pd.DataFrame(results)


def no_storage_baseline(df):
    """
    No-storage baseline — battery is never used.
    Profit is always zero; useful as a floor reference.
    """
    results = []
    for idx in range(len(df)):
        row = df.iloc[idx]
        results.append({
            "Timestamp": row["Timestamp"],
            "Price": row["Price_INR_kWh"],
            "Battery_Power": 0.0,
            "SOC": 0.0,
            "Profit": 0.0,
        })
    return pd.DataFrame(results)
