import numpy as np
from sklearn.ensemble import RandomForestRegressor
from src.config import LAG

def train_forecast_model(df):
    prices = df["Price_INR_kWh"].values
    X, y = [], []

    for i in range(LAG, len(prices)):
        X.append(list(prices[i-LAG:i]) + [df["hour"].iloc[i], df["dow"].iloc[i]])
        y.append(prices[i])

    X, y = np.array(X), np.array(y)

    model = RandomForestRegressor(n_estimators=200, max_depth=12, random_state=42)
    model.fit(X, y)

    residuals = y - model.predict(X)

    return model, residuals