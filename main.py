from src.data_loader import load_price_data
from src.forecast import train_forecast_model
from src.plotting import plot_simulation_results
from src.simulation import simulate_operation
import os

def main():
    if not os.path.exists("outputs"):
        os.makedirs("outputs")

    print("Loading data...")
    df = load_price_data("data/iex_dam_hourly_2024_25.csv")
    
    print("Training forecast model...")
    model, residuals = train_forecast_model(df)
    print("Model trained successfully.")
    
    print("Starting simulation (this may take a while)...")
    # Run simulation (limiting to 1000 steps for demo speed, or full allowed)
    # Full dataset is 8772. Let's run 1000 steps which is ~42 days, sufficient for demo.
    # Running full 8772 takes ~5 mins. User can wait or I can just run 1000.
    # "verify functionality" suggests checking if it works.
    limit = 1000
    print(f"Running simulation for {limit} steps...")
    results_df = simulate_operation(df.head(limit), model, residuals)
    
    output_path = "outputs/simulation_results.csv"
    results_df.to_csv(output_path, index=False)
    print(f"Simulation completed. Results saved to {output_path}")
    
    # Calculate stats
    total_profit = results_df["Profit"].sum()
    print(f"Total Profit: {total_profit:,.2f} INR")
    
    print("Generating plot...")
    plot_simulation_results(results_df, "outputs/simulation_plot.png")

if __name__ == "__main__":
    main()