import logging
import math

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List
from contextlib import asynccontextmanager
import pandas as pd
import numpy as np
import io
import sys
import os

# Add root directory to sys.path to import src modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import models, schemas
from backend.database import Base, engine, SessionLocal
from src.data_loader import load_price_data
from src.forecast import train_forecast_model
from src.simulation import simulate_operation
from src.baseline import naive_strategy, no_storage_baseline
from src.metrics import compute_all_metrics, total_profit, total_cycles, sharpe_ratio, utilization_rate
import src.config as cfg

# ── Logging ─────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("emsjb")

# ── Global State ────────────────────────────────────────────
app_state = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Loading data and training model...")
    df = load_price_data("data/iex_dam_hourly_2024_25.csv")
    model, residuals, accuracy, train_end = train_forecast_model(df)
    app_state["df"] = df
    app_state["model"] = model
    app_state["residuals"] = residuals
    app_state["forecast_accuracy"] = accuracy
    app_state["train_end"] = train_end
    logger.info(f"Startup complete. Dataset: {len(df)} hours, Train end idx: {train_end}")
    logger.info(f"Forecast accuracy: {accuracy}")
    yield
    app_state.clear()


app = FastAPI(title="EMSJB Energy Dashboard API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create tables
Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════

@app.get("/api/config", response_model=schemas.ConfigResponse)
def get_config():
    """Return current battery & simulation configuration."""
    return schemas.ConfigResponse(
        battery_power_kw=cfg.BATTERY_POWER,
        battery_energy_kwh=cfg.BATTERY_ENERGY,
        round_trip_efficiency=cfg.ETA ** 2,
        capex_inr=cfg.CAPEX,
        opex_per_year_inr=cfg.OPEX_PER_YEAR,
        cycle_life=cfg.CYCLE_LIFE,
        degradation_cost_per_kwh=cfg.DEGR_COST,
        deviation_penalty=cfg.DEV_PENALTY,
        forecast_lag_hours=cfg.LAG,
        planning_horizon_hours=cfg.HORIZON,
        scenarios=cfg.SCENARIOS,
        cvar_alpha=cfg.ALPHA,
        cvar_lambda=cfg.LAMBDA,
    )


@app.post("/api/config", response_model=schemas.ConfigResponse)
def update_config(update: schemas.ConfigUpdate):
    """Update simulation parameters at runtime."""
    if update.battery_power_kw is not None:
        cfg.BATTERY_POWER = update.battery_power_kw
    if update.battery_energy_kwh is not None:
        cfg.BATTERY_ENERGY = update.battery_energy_kwh
    if update.round_trip_efficiency is not None:
        cfg.ETA = math.sqrt(update.round_trip_efficiency)
    if update.cycle_life is not None:
        cfg.CYCLE_LIFE = update.cycle_life
    if update.cvar_alpha is not None:
        cfg.ALPHA = update.cvar_alpha
    if update.cvar_lambda is not None:
        cfg.LAMBDA = update.cvar_lambda
    if update.planning_horizon_hours is not None:
        cfg.HORIZON = update.planning_horizon_hours
    if update.scenarios is not None:
        cfg.SCENARIOS = update.scenarios

    # Recompute derived values
    cfg.CAPEX = (300 * 84 * cfg.BATTERY_ENERGY) / 5
    cfg.OPEX_PER_YEAR = 0.02 * cfg.CAPEX
    cfg.DEGR_COST = cfg.CAPEX / (2 * cfg.CYCLE_LIFE * cfg.BATTERY_ENERGY)

    logger.info(f"Config updated: Power={cfg.BATTERY_POWER}, Energy={cfg.BATTERY_ENERGY}, λ={cfg.LAMBDA}")
    return get_config()


# ══════════════════════════════════════════════════════════════
#  DATA SUMMARY
# ══════════════════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════════════════
#  FORECAST ACCURACY
# ══════════════════════════════════════════════════════════════

@app.get("/api/forecast/accuracy", response_model=schemas.ForecastAccuracy)
def get_forecast_accuracy():
    """Return the out-of-sample forecast accuracy metrics."""
    if "forecast_accuracy" not in app_state:
        raise HTTPException(status_code=503, detail="Model not trained yet.")
    acc = app_state["forecast_accuracy"]
    return schemas.ForecastAccuracy(
        train_mae=acc["mae"],
        train_rmse=acc["rmse"],
        train_mape=acc["mape"],
    )


# ══════════════════════════════════════════════════════════════
#  SIMULATION
# ══════════════════════════════════════════════════════════════

@app.get("/api/simulation/run", response_model=schemas.SimulationRun)
def run_simulation(steps: int = 168, db: Session = Depends(get_db)):
    """
    Run simulation for a specified number of steps (default 1 week = 168 hours).
    Stores result in DB and returns it.
    """
    if "df" not in app_state:
        raise HTTPException(status_code=503, detail="Server is starting up, try again.")

    df = app_state["df"]
    model = app_state["model"]
    residuals = app_state["residuals"]

    # Need LAG + steps + HORIZON buffer
    sim_df = df.head(cfg.LAG + steps + cfg.HORIZON)

    logger.info(f"Starting simulation: {steps} steps")
    results_df = simulate_operation(sim_df, model, residuals)

    # Trim to requested steps
    results_df = results_df.head(steps)
    total = results_df["Profit"].sum()

    # Save to DB
    db_run = models.SimulationRun(total_profit=total, steps_count=len(results_df))
    db.add(db_run)
    db.commit()
    db.refresh(db_run)

    # Save steps
    db_steps = []
    for idx, row in results_df.iterrows():
        step = models.SimulationStep(
            run_id=db_run.id,
            step_index=idx,
            price=row["Price"],
            forecast_price=row.get("Forecast_Price", 0.0),
            battery_power=row["Battery_Power"],
            soc=row["SOC"],
            profit=row["Profit"],
            energy_revenue=row.get("Energy_Revenue", 0.0),
            degradation_cost=row.get("Degradation_Cost", 0.0),
            deviation_penalty=row.get("Deviation_Penalty", 0.0),
        )
        db_steps.append(step)

    db.add_all(db_steps)
    db.commit()

    logger.info(f"Simulation complete: Run #{db_run.id}, Profit={total:.2f}, Steps={len(results_df)}")
    return db_run


@app.get("/api/simulation/history", response_model=List[schemas.SimulationRun])
def get_history(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    runs = db.query(models.SimulationRun).order_by(
        models.SimulationRun.timestamp.desc()
    ).offset(skip).limit(limit).all()
    return runs


@app.get("/api/simulation/{run_id}", response_model=schemas.SimulationRun)
def get_simulation(run_id: int, db: Session = Depends(get_db)):
    run = db.query(models.SimulationRun).filter(models.SimulationRun.id == run_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


# ══════════════════════════════════════════════════════════════
#  METRICS
# ══════════════════════════════════════════════════════════════

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
        "Forecast_Price": s.forecast_price or 0.0,
        "Energy_Revenue": s.energy_revenue or 0.0,
        "Degradation_Cost": s.degradation_cost or 0.0,
        "Deviation_Penalty": s.deviation_penalty or 0.0,
    } for s in steps])

    metrics = compute_all_metrics(df)
    return schemas.MetricsResponse(**metrics)


# ══════════════════════════════════════════════════════════════
#  BASELINE COMPARISON
# ══════════════════════════════════════════════════════════════

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

    opt_df = pd.DataFrame([{
        "Battery_Power": s.battery_power,
        "SOC": s.soc,
        "Profit": s.profit,
        "Price": s.price,
        "Forecast_Price": s.forecast_price or 0.0,
        "Energy_Revenue": s.energy_revenue or 0.0,
        "Degradation_Cost": s.degradation_cost or 0.0,
        "Deviation_Penalty": s.deviation_penalty or 0.0,
    } for s in steps])

    n_steps = len(steps)
    df = app_state["df"]
    raw_slice = df.head(n_steps + cfg.HORIZON)

    naive_df = naive_strategy(raw_slice).head(n_steps)
    no_stor_df = no_storage_baseline(raw_slice).head(n_steps)

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


# ══════════════════════════════════════════════════════════════
#  EXPORT CSV
# ══════════════════════════════════════════════════════════════

@app.get("/api/simulation/{run_id}/export")
def export_csv(run_id: int, db: Session = Depends(get_db)):
    """Download simulation results as CSV."""
    steps = db.query(models.SimulationStep).filter(
        models.SimulationStep.run_id == run_id
    ).order_by(models.SimulationStep.step_index).all()

    if not steps:
        raise HTTPException(status_code=404, detail="No steps found")

    df = pd.DataFrame([{
        "Step": s.step_index,
        "Price_INR_kWh": s.price,
        "Forecast_Price": s.forecast_price or 0.0,
        "Battery_Power_kW": s.battery_power,
        "SOC_kWh": s.soc,
        "Profit_INR": s.profit,
        "Energy_Revenue_INR": s.energy_revenue or 0.0,
        "Degradation_Cost_INR": s.degradation_cost or 0.0,
        "Deviation_Penalty_INR": s.deviation_penalty or 0.0,
    } for s in steps])

    stream = io.StringIO()
    df.to_csv(stream, index=False)
    stream.seek(0)

    return StreamingResponse(
        iter([stream.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=simulation_run_{run_id}.csv"}
    )
