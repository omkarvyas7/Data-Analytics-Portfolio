"""Monte Carlo comparison of dispatch protocols over N seeded batching windows.

A window is a short batch (think 30 seconds) of rider requests in a 6 x 6 mile zone with some
open drivers. All five protocols run on the same riders and drivers:

  greedy_first_dispatch       riders in arrival order each take the nearest open driver (no radius)
  greedy_first_dispatch_mdr   same, but only drivers within the max dispatch radius (MDR) count
  batched_min_eta             optimal assignment minimising total ETA (no radius)
  batched_min_eta_mdr         within MDR: most feasible matches first, then lowest total ETA
  batched_max_profit_mdr      within MDR: highest modelled contribution ($)

Batched protocols use scipy.optimize.linear_sum_assignment, which gives the same optimum as the
notebook's 0-1 integer programs (src/validate_ilp.py checks this against cvxpy).

Outputs
  data/raw/dispatch_windows.csv            one row per window: demand, supply, MDR
  data/processed/simulation_results.csv    one row per window x protocol with KPIs
  data/processed/simulation_matches.csv    one row per matched rider (for ETA distributions)

All data is synthetic (numpy seed 42). None of it comes from Uber or any employer.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment

from common import (DATA_PROCESSED, DATA_RAW, GREEDY, GREEDY_MDR, BATCH, BATCH_MDR,
                    BATCH_PROFIT_MDR)

SEED = 42
N_WINDOWS = 1_000
ZONE_MILES = 6.0                       # square service zone side length
MEAN_RIDERS = 15                       # Poisson mean requests per window
SUPPLY_RATIOS = [0.6, 0.8, 1.0, 1.2, 1.5]   # design drivers-per-rider ratio
MDR_OPTIONS = [1.5, 2.0, 3.0, 4.0]     # max dispatch radius (miles, Manhattan)
MIN_PER_MILE = 60 / 18                 # 18 mph average city speed
PICKUP_OVERHEAD_MIN = 1.0              # accept + curbside time
ETA_NOISE_SIGMA = 0.20                 # lognormal traffic noise on en-route time
BASE_FARE, PER_MILE, PER_MIN = 2.50, 1.25, 0.30
ENROUTE_COST_PER_MILE = 0.65           # unpaid deadhead cost per en-route mile
BIG = 1e6                              # penalty for infeasible (outside MDR) pairs


def make_window(rng: np.random.Generator, window_id: int) -> dict:
    """Draw one batching window: riders, drivers, distances, ETAs and fares."""
    ratio = float(rng.choice(SUPPLY_RATIOS))
    mdr = float(rng.choice(MDR_OPTIONS))
    n_r = max(2, int(rng.poisson(MEAN_RIDERS)))
    n_d = max(1, int(rng.poisson(ratio * n_r)))
    riders = rng.uniform(0, ZONE_MILES, (n_r, 2))
    drivers = rng.uniform(0, ZONE_MILES, (n_d, 2))
    dist = np.abs(riders[:, None, :] - drivers[None, :, :]).sum(axis=2)   # Manhattan miles
    noise = rng.lognormal(0.0, ETA_NOISE_SIGMA, dist.shape)
    eta = dist * MIN_PER_MILE * noise + PICKUP_OVERHEAD_MIN                # minutes
    trip_miles = rng.lognormal(np.log(4.0), 0.6, n_r)
    fare = BASE_FARE + PER_MILE * trip_miles + PER_MIN * trip_miles * 2.5   # 2.5 min per trip mile
    contrib = fare[:, None] - ENROUTE_COST_PER_MILE * dist                 # $ per rider-driver pair
    return dict(window_id=window_id, supply_ratio_design=ratio, mdr_miles=mdr,
                riders=n_r, drivers=n_d, dist=dist, eta=eta, contrib=contrib)


def greedy(eta: np.ndarray, feasible: np.ndarray) -> list[tuple[int, int]]:
    """First-dispatch: riders in arrival order (row order) take the lowest-ETA open driver."""
    open_drivers = np.ones(eta.shape[1], dtype=bool)
    pairs = []
    for r in range(eta.shape[0]):
        cand = open_drivers & feasible[r]
        if not cand.any():
            continue                                   # rider goes unmatched this window
        d = int(np.argmin(np.where(cand, eta[r], np.inf)))
        open_drivers[d] = False
        pairs.append((r, d))
    return pairs


def batched(score: np.ndarray, feasible: np.ndarray, maximize: bool) -> list[tuple[int, int]]:
    """Optimal one-to-one assignment. Infeasible pairs get a BIG penalty and are dropped after.

    BIG outweighs any real score, so the solver maximises feasible matches first and only then
    picks the best total ETA (or contribution) among them.
    """
    cost = -score if maximize else score.copy()
    cost = np.where(feasible, cost, BIG)
    rows, cols = linear_sum_assignment(cost)
    return [(int(r), int(c)) for r, c in zip(rows, cols) if feasible[r, c]]


def kpis(w: dict, protocol: str, pairs: list[tuple[int, int]]) -> tuple[dict, list[dict]]:
    etas = np.array([w["eta"][r, d] for r, d in pairs])
    miles = np.array([w["dist"][r, d] for r, d in pairs])
    profit = float(sum(w["contrib"][r, d] for r, d in pairs))
    m = len(pairs)
    row = dict(
        window_id=w["window_id"], protocol=protocol,
        supply_ratio_design=w["supply_ratio_design"], mdr_miles=w["mdr_miles"],
        riders=w["riders"], drivers=w["drivers"], matched=m, unmatched_riders=w["riders"] - m,
        match_rate=m / w["riders"],
        avg_eta_min=float(etas.mean()) if m else np.nan,
        p90_eta_min=float(np.percentile(etas, 90)) if m else np.nan,
        max_eta_min=float(etas.max()) if m else np.nan,
        total_enroute_min=float(etas.sum()),
        avg_enroute_miles=float(miles.mean()) if m else np.nan,
        driver_utilization=m / w["drivers"],
        profit_usd=profit,
    )
    match_rows = [dict(window_id=w["window_id"], protocol=protocol, rider_idx=r, driver_idx=d,
                       eta_min=float(w["eta"][r, d]), enroute_miles=float(w["dist"][r, d]),
                       contribution_usd=float(w["contrib"][r, d])) for r, d in pairs]
    return row, match_rows


def run(n_windows: int = N_WINDOWS, seed: int = SEED):
    rng = np.random.default_rng(seed)
    windows, results, matches = [], [], []
    for wid in range(1, n_windows + 1):
        w = make_window(rng, wid)
        all_ok = np.ones_like(w["dist"], dtype=bool)
        in_mdr = w["dist"] <= w["mdr_miles"]
        plans = {
            GREEDY: greedy(w["eta"], all_ok),
            GREEDY_MDR: greedy(w["eta"], in_mdr),
            BATCH: batched(w["eta"], all_ok, maximize=False),
            BATCH_MDR: batched(w["eta"], in_mdr, maximize=False),
            BATCH_PROFIT_MDR: batched(w["contrib"], in_mdr & (w["contrib"] > 0), maximize=True),
        }
        for proto, pairs in plans.items():
            row, mrows = kpis(w, proto, pairs)
            results.append(row)
            matches.extend(mrows)
        windows.append(dict(window_id=wid, supply_ratio_design=w["supply_ratio_design"],
                            mdr_miles=w["mdr_miles"], riders=w["riders"], drivers=w["drivers"],
                            supply_ratio_actual=round(w["drivers"] / w["riders"], 4)))
    res = pd.DataFrame(results)
    # sanity checks: the optimum should never lose to greedy on its own objective
    piv = res.pivot(index="window_id", columns="protocol")
    assert (piv["total_enroute_min"][BATCH] <= piv["total_enroute_min"][GREEDY] + 1e-9).all()
    assert (piv["matched"][BATCH_MDR] >= piv["matched"][GREEDY_MDR]).all()
    assert (piv["matched"][BATCH] == piv["matched"][GREEDY]).all()
    return pd.DataFrame(windows), res, pd.DataFrame(matches)


def main():
    windows, res, matches = run()
    windows.to_csv(DATA_RAW / "dispatch_windows.csv", index=False)
    res.round(4).to_csv(DATA_PROCESSED / "simulation_results.csv", index=False)
    matches.round(4).to_csv(DATA_PROCESSED / "simulation_matches.csv", index=False)
    print(f"simulated {len(windows)} windows, {len(res)} protocol rows, {len(matches)} matches")
    g = res.groupby("protocol").sum(numeric_only=True)
    summary = {"match_rate": g.matched / g.riders,                      # rider-weighted, as in sql/01
               "avg_eta_min": g.total_enroute_min / g.matched,
               "driver_utilization": g.matched / g.drivers,
               "profit_usd_per_window": g.profit_usd / len(windows)}
    print(pd.DataFrame(summary).round(3).to_string())


if __name__ == "__main__":
    main()
