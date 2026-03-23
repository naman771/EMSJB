import math

# ── Battery Parameters ──────────────────────────────────────
BATTERY_POWER = 1000.0          # kW — max charge/discharge rate
BATTERY_ENERGY = 4000.0         # kWh — total storage capacity (4-hour system)
ETA = math.sqrt(0.88)           # One-way efficiency (sqrt of round-trip 88%)

CAPEX = (300 * 84 * BATTERY_ENERGY) / 5   # Capital expenditure (₹)
OPEX_PER_YEAR = 0.02 * CAPEX              # Annual O&M cost (₹)

CYCLE_LIFE = 6000                                       # Expected lifetime cycles
DEGR_COST = CAPEX / (2 * CYCLE_LIFE * BATTERY_ENERGY)  # ₹/kWh degradation cost

DEV_PENALTY = 2.0               # ₹/kWh penalty for schedule deviation

# ── Forecasting ─────────────────────────────────────────────
LAG = 24                        # Lookback window (hours)

# ── Optimisation & Risk ─────────────────────────────────────
HORIZON = 24                    # Planning horizon (hours)
SCENARIOS = 5                   # Number of stochastic scenarios
ALPHA = 0.95                    # CVaR confidence level
LAMBDA = 0.3                    # Risk-aversion weight (0 = risk-neutral, 1 = pure CVaR)