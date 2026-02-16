from src.data_loader import load_price_data
from src.forecast import train_forecast_model

def main():
    df = load_price_data("data/iex_dam_hourly_2024_25.csv")
    model, residuals = train_forecast_model(df)
    print("Model trained successfully.")

if __name__ == "__main__":
    main()