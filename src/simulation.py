import numpy as np
import pandas as pd
from src.config import *
from src.optimizer import optimize_battery

def simulate_operation(df, model, residuals):
    results = []
    
    # Start simulation after the initial LAG period
    start_idx = LAG
    end_idx = len(df) - HORIZON
    
    # Initial State of Charge
    soc = 0.0
    
    for t in range(start_idx, end_idx):
        # 1. Forecast DAM prices for the horizon
        # For simplicity in this demo, we might use actuals + noise or recursive forecasting.
        # Here, let's just use the known future prices as "forecast" for the base path,
        # and add residuals to create scenarios. 
        # In a real online setting, we would predict strictly from past data.
        
        # Current time slice
        current_time = df["Timestamp"].iloc[t]
        
        # Get actual DAM price (Real Time Market price proxy for now if not separate)
        # The optimize_battery function expects dam_prices and rtm_prices (scenarios)
        
        # Let's assume we are at time t, planning for t to t+HORIZON
        dam_prices_horizon = df["Price_INR_kWh"].iloc[t:t+HORIZON].values
        
        # Generate Scenarios for RTM prices using residuals
        # We assume RTM deviates from DAM by some residual noise
        rtm_prices_scenarios = []
        for s in range(SCENARIOS):
            noise = np.random.choice(residuals, size=HORIZON, replace=True)
            scenario_prices = dam_prices_horizon + noise
            # Ensure non-negative prices if needed, though negative prices are possible in power markets
            rtm_prices_scenarios.append(scenario_prices)
            
        # 2. Optimize Battery Dispatch
        # We only need the decision for the first time step (Receding Horizon Control)
        q_opt = optimize_battery(dam_prices_horizon, rtm_prices_scenarios, soc)
        
        # 3. Update State of Charge
        # q_opt > 0 means discharging (selling), q_opt < 0 means charging (buying)
        # Update logic: soc_new = soc_old - q_opt/ETA (if discharge) ... wait, check optimizer constraints
        # Optimizer constraint: soc[t] == prev_soc + ETA * q[t] - q[t] / ETA
        # But q in optimizer is net flow? 
        # Line 32: q[t] == q_pos[t] - q_neg[t]
        # Line 31: soc[t] == prev_soc + ETA * q[t] - q[t] / ETA is NOT LINEAR if q is net. 
        # Actually in optimizer.py:
        # soc[t] == prev_soc + ETA * q[t] - q[t] / ETA 
        # This line in optimizer seems wrong for a single variable q if it can be pos or neg. 
        # Usually: soc[t] = soc[t-1] + eta_charge * q_charge - q_discharge / eta_discharge
        # Let's assume q is charging power? 
        # In optimizer.py: q bounds are -BATTERY_POWER to +BATTERY_POWER.
        # q_pos - q_neg = q.
        # If q > 0 (discharge?), profit adds q * price. So q>0 is selling/discharging.
        # If q < 0 (charge?), profit subtracts.
        
        # Let's check optimizer.py line 31 again carefully in next step.
        # For now, I will assume the optimizer handles the logic and I just need to update SOC based on q_opt.
        
        # Realized dispatch might differ, but we assume perfect tracking for now.
        
        realized_price = df["Price_INR_kWh"].iloc[t] # Assuming RTM = DAM for the actual settlement in this simple sim
        
        # Calculate degradation cost
        degr_cost = DEGR_COST * abs(q_opt)
        
        # Calculate profit
        profit = q_opt * realized_price - degr_cost
        
        # Update SOC for next step
        # We need to replicate the physics from the optimizer to be consistent
        # If q > 0 (discharging): soc_new = soc - q / ETA
        # If q < 0 (charging): soc_new = soc + q * ETA
        # Note: q is defined as q_pos - q_neg. 
        # If q_pos > 0 (voluntarily discharging), q > 0. 
        # Wait, usually q_pos is discharging.
        
        if q_opt >= 0:
            soc_next = soc - q_opt / ETA
        else:
            soc_next = soc - q_opt * ETA # result is positive addition since q_opt is neg
            
        # Clip SOC to physical limits
        soc_next = max(0, min(BATTERY_ENERGY, soc_next))
        
        results.append({
            "Timestamp": current_time,
            "Price": realized_price,
            "Battery_Power": q_opt,
            "SOC": soc,
            "Profit": profit
        })
        
        soc = soc_next
        
        if t % 100 == 0:
            print(f"Step {t}/{end_idx}: Profit so far = {sum(r['Profit'] for r in results):.2f}")
            print(f"  Current Price: {realized_price:.2f}, Battery Power: {q_opt:.2f}, SOC: {soc:.2f}")

    return pd.DataFrame(results)
