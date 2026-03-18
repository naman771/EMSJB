from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


# ── Simulation ──────────────────────────────────────────────

class SimulationStepBase(BaseModel):
    step_index: int
    price: float
    battery_power: float
    soc: float
    profit: float


class SimulationStepCreate(SimulationStepBase):
    pass


class SimulationStep(SimulationStepBase):
    id: int
    run_id: int

    class Config:
        from_attributes = True


class SimulationRunBase(BaseModel):
    total_profit: float


class SimulationRunCreate(SimulationRunBase):
    pass


class SimulationRun(SimulationRunBase):
    id: int
    timestamp: datetime
    steps: List[SimulationStep] = []

    class Config:
        from_attributes = True


# ── Config ──────────────────────────────────────────────────

class ConfigResponse(BaseModel):
    battery_power_kw: float
    battery_energy_kwh: float
    round_trip_efficiency: float
    capex_inr: float
    opex_per_year_inr: float
    cycle_life: int
    degradation_cost_per_kwh: float
    deviation_penalty: float
    forecast_lag_hours: int
    planning_horizon_hours: int
    scenarios: int
    cvar_alpha: float
    cvar_lambda: float


# ── Data Summary ────────────────────────────────────────────

class DataSummary(BaseModel):
    total_hours: int
    date_start: str
    date_end: str
    price_mean: float
    price_min: float
    price_max: float
    price_std: float


# ── Metrics ─────────────────────────────────────────────────

class MetricsResponse(BaseModel):
    total_profit: float
    avg_daily_profit: float
    total_cycles: float
    profit_per_cycle: float
    max_drawdown: float
    sharpe_ratio: float
    utilization_rate: float


# ── Baseline Comparison ─────────────────────────────────────

class BaselineResult(BaseModel):
    strategy: str
    total_profit: float
    total_cycles: float
    sharpe_ratio: float
    utilization_rate: float


class BaselineComparison(BaseModel):
    optimized: BaselineResult
    naive: BaselineResult
    no_storage: BaselineResult
