import pulp
from src.config import *

def optimize_battery(dam_prices, rtm_prices, soc_current):

    model = pulp.LpProblem("Battery_CVaR", pulp.LpMaximize)

    q = pulp.LpVariable.dicts("q", range(HORIZON),
                              lowBound=-BATTERY_POWER,
                              upBound=BATTERY_POWER)

    q_pos = pulp.LpVariable.dicts("q_pos", range(HORIZON), lowBound=0)
    q_neg = pulp.LpVariable.dicts("q_neg", range(HORIZON), lowBound=0)

    soc = pulp.LpVariable.dicts("soc", range(HORIZON),
                                lowBound=0,
                                upBound=BATTERY_ENERGY)

    profit_s = pulp.LpVariable.dicts("profit", range(SCENARIOS))
    eta = pulp.LpVariable("VaR")
    xi = pulp.LpVariable.dicts("xi", range(SCENARIOS), lowBound=0)

    model += (
        pulp.lpSum(profit_s[s] for s in range(SCENARIOS)) / SCENARIOS
        - LAMBDA * (eta + pulp.lpSum(xi[s] for s in range(SCENARIOS))
                    / ((1 - ALPHA) * SCENARIOS))
    )

    for t in range(HORIZON):
        prev_soc = soc[t-1] if t > 0 else soc_current
        model += soc[t] == prev_soc + ETA * q[t] - q[t] / ETA
        model += q[t] == q_pos[t] - q_neg[t]

    for s in range(SCENARIOS):
        model += profit_s[s] == pulp.lpSum(
            q[t] * rtm_prices[s][t]
            - DEV_PENALTY * (q_pos[t] + q_neg[t])
            - DEGR_COST * (q_pos[t] + q_neg[t])
            for t in range(HORIZON)
        )
        model += xi[s] >= eta - profit_s[s]

    model.solve(pulp.PULP_CBC_CMD(msg=False))

    return pulp.value(q[0])
