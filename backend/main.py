from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import pandas as pd
import numpy as np
import sys
import os

# Add root directory to sys.path to import src modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import models, schemas, database
from src.data_loader import load_price_data
from src.forecast import train_forecast_model
from src.simulation import simulate_operation
from src.baseline import naive_strategy, no_storage_baseline
from src.metrics import compute_all_metrics, total_profit, total_cycles, sharpe_ratio, utilization_rate
from src.config import (
    BATTERY_POWER, BATTERY_ENERGY, ETA, CAPEX, OPEX_PER_YEAR,
    CYCLE_LIFE, DEGR_COST, DEV_PENALTY, LAG, HORIZON, SCENARIOS, ALPHA, LAMBDA
)
from contextlib import asynccontextmanager

models.Base.metadata.create_all(bind=database.engine)

# Global variables to hold loaded data and model
app_state = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load data and train model on startup
    print("Loading data and training model...")
    df = load_price_data("data/iex_dam_hourly_2024_25.csv")
    model, residuals = train_forecast_model(df)
    app_state["df"] = df
    app_state["model"] = model
    app_state["residuals"] = residuals
    print("Startup complete.")
    yield
    # Clean up
    app_state.clear()

app = FastAPI(title="EMSJB Energy Dashboard API", lifespan=lifespan)

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Config Endpoint ─────────────────────────────────────────

@app.get("/api/config", response_model=schemas.ConfigResponse)
def get_config():
    """Return current battery & simulation configuration."""
    return schemas.ConfigResponse(
        battery_power_kw=BATTERY_POWER,
        battery_energy_kwh=BATTERY_ENERGY,
        round_trip_efficiency=ETA ** 2,  # ETA is sqrt(round-trip)
        capex_inr=CAPEX,
        opex_per_year_inr=OPEX_PER_YEAR,
        cycle_life=CYCLE_LIFE,
        degradation_cost_per_kwh=DEGR_COST,
        deviation_penalty=DEV_PENALTY,
        forecast_lag_hours=LAG,
        planning_horizon_hours=HORIZON,
        scenarios=SCENARIOS,
        cvar_alpha=ALPHA,
        cvar_lambda=LAMBDA,
    )


# ── Data Summary Endpoint ──────────────────────────────────

@app.get("/api/data/summary", response_model=schemas.DataSummary)
def get_data_summary():
    """Return summary statistics of the loaded price dataset."""
    if "df" not in app_state:
        raise HTTPException(status_code=503, detail="Data not loaded yet.")
    df = app_state["df"]
    prices = df["Price_INR_kWh"]
    return schemas.DataSummary(
        total_hours=len(df),
        date_start=str(df["Timestamp"].min()),
        date_end=str(df["Timestamp"].max()),
        price_mean=round(float(prices.mean()), 4),
        price_min=round(float(prices.min()), 4),
        price_max=round(float(prices.max()), 4),
        price_std=round(float(prices.std()), 4),
    )


# ── Simulation Endpoints ───────────────────────────────────

@app.get("/api/simulation/run", response_model=schemas.SimulationRun)
def run_simulation(steps: int = 168, db: Session = Depends(get_db)):
    """
    Run simulation for a specified number of steps (default 1 week = 168 hours).
    Stores result in DB and returns it.
    """
    if "df" not in app_state:
        raise HTTPException(status_code=503, detail="Server is potentially starting up, try again.")
    
    df = app_state["df"]
    model = app_state["model"]
    residuals = app_state["residuals"]
    
    # Run simulation on a subset
    sim_df = df.head(LAG + steps + HORIZON)  # Need LAG + horizon buffer
    
    results_df = simulate_operation(sim_df, model, residuals)
    
    # Calculate stats
    total = results_df["Profit"].sum()
    
    # Save to DB
    db_run = models.SimulationRun(total_profit=total)
    db.add(db_run)
    db.commit()
    db.refresh(db_run)
    
    # Save steps
    db_steps = []
    for idx, row in results_df.iterrows():
        if idx >= steps: 
            break
            
        step = models.SimulationStep(
            run_id=db_run.id,
            step_index=idx,
            price=row["Price"],
            battery_power=row["Battery_Power"],
            soc=row["SOC"],
            profit=row["Profit"]
        )
        db_steps.append(step)
    
    db.add_all(db_steps)
    db.commit()
    
    return db_run

@app.get("/api/simulation/history", response_model=List[schemas.SimulationRun])
def get_history(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    runs = db.query(models.SimulationRun).order_by(models.SimulationRun.timestamp.desc()).offset(skip).limit(limit).all()
    return runs

@app.get("/api/simulation/{run_id}", response_model=schemas.SimulationRun)
def get_simulation(run_id: int, db: Session = Depends(get_db)):
    run = db.query(models.SimulationRun).filter(models.SimulationRun.id == run_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


# ── Metrics Endpoint ────────────────────────────────────────

@app.get("/api/simulation/{run_id}/metrics", response_model=schemas.MetricsResponse)
def get_metrics(run_id: int, db: Session = Depends(get_db)):
    """Compute performance metrics for a given simulation run."""
    run = db.query(models.SimulationRun).filter(models.SimulationRun.id == run_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    
    steps = db.query(models.SimulationStep).filter(
        models.SimulationStep.run_id == run_id
    ).order_by(models.SimulationStep.step_index).all()
    
    if not steps:
        raise HTTPException(status_code=404, detail="No steps found for this run")
    
    df = pd.DataFrame([{
        "Battery_Power": s.battery_power,
        "SOC": s.soc,
        "Profit": s.profit,
        "Price": s.price,
    } for s in steps])
    
    metrics = compute_all_metrics(df)
    return schemas.MetricsResponse(**metrics)


# ── Baseline Comparison Endpoint ────────────────────────────

@app.get("/api/simulation/{run_id}/baseline", response_model=schemas.BaselineComparison)
def get_baseline_comparison(run_id: int, db: Session = Depends(get_db)):
    """Compare optimized run against naive and no-storage baselines."""
    run = db.query(models.SimulationRun).filter(models.SimulationRun.id == run_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    
    steps = db.query(models.SimulationStep).filter(
        models.SimulationStep.run_id == run_id
    ).order_by(models.SimulationStep.step_index).all()
    
    if not steps:
        raise HTTPException(status_code=404, detail="No steps found")
    
    # Reconstruct optimized results
    opt_df = pd.DataFrame([{
        "Battery_Power": s.battery_power,
        "SOC": s.soc,
        "Profit": s.profit,
        "Price": s.price,
    } for s in steps])
    
    # Get the corresponding slice of raw data for baselines
    n_steps = len(steps)
    df = app_state["df"]
    raw_slice = df.head(n_steps + HORIZON)
    
    naive_df = naive_strategy(raw_slice)
    naive_df = naive_df.head(n_steps)
    
    no_stor_df = no_storage_baseline(raw_slice)
    no_stor_df = no_stor_df.head(n_steps)
    
    def make_result(name, result_df):
        return schemas.BaselineResult(
            strategy=name,
            total_profit=round(total_profit(result_df), 2),
            total_cycles=round(total_cycles(result_df), 2),
            sharpe_ratio=round(sharpe_ratio(result_df), 4),
            utilization_rate=round(utilization_rate(result_df), 4),
        )
    
    return schemas.BaselineComparison(
        optimized=make_result("CVaR Optimized", opt_df),
        naive=make_result("Naive Peak/Off-Peak", naive_df),
        no_storage=make_result("No Storage", no_stor_df),
    )
