"""Generate synthetic returns-processing data for the DMAIC defect-reduction project.

Data is synthetic and seeded. It mirrors the shape of e-commerce returns grading and
disposition work; no Amazon or employer data is used.

Root causes built into the data (the analysis has to find these, not assume them):
  * associates with tenure < 30 days misgrade more often
  * grading SOP v2.x is unclear for Electronics and open-box condition
  * night shift has higher defect rates
  * RC-CENTRAL has no photo-grading step before the pilot
  * backlog after Q4 (January peak) raises queue time and defects
Improve phase: SOP v3.0 + grading checklist + photo step piloted at RC-CENTRAL
(2026-03-01 to 2026-04-30), then rolled out to all sites (Control, 2026-05-01 onward).

Outputs (data/raw/):
  returns_units.csv, unit_cycle_stages.csv, audits.csv, associates.csv,
  sites.csv, sop_versions.csv, disposition_values.csv
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
SEED = 20260705

START = pd.Timestamp("2025-07-01")
END = pd.Timestamp("2026-06-30")
SOP22_START = pd.Timestamp("2025-10-01")
PILOT_START = pd.Timestamp("2026-03-01")
CONTROL_START = pd.Timestamp("2026-05-01")
PILOT_SITE = "RC-CENTRAL"
N_TARGET = 150_000

# site_id, name, region, daily_capacity_units, volume_share, photo_step_before_pilot
SITES = [
    ("RC-WEST", "West Returns Center", "West", 140, 0.30, 1),
    ("RC-CENTRAL", "Central Returns Center", "Central", 112, 0.25, 0),
    ("RC-EAST", "East Returns Center", "East", 128, 0.27, 1),
    ("RC-SOUTH", "South Returns Center", "South", 80, 0.18, 1),
]
SHIFTS = {"Day": (0.45, 6), "Swing": (0.35, 14), "Night": (0.20, 22)}  # share, start hour
CORE_HEADCOUNT = {"Day": 12, "Swing": 9, "Night": 6}  # for a 25%-share site
MONTHLY_ATTRITION = {"Day": 0.025, "Swing": 0.03, "Night": 0.05}

DISPOSITIONS = ["NEW", "OPEN_BOX", "REFURB", "LIQUIDATE", "RECYCLE", "DESTROY"]
RECOVERY_PCT = {"NEW": 0.90, "OPEN_BOX": 0.72, "REFURB": 0.55, "LIQUIDATE": 0.18,
                "RECYCLE": 0.03, "DESTROY": 0.0}
RESELLABLE = {"NEW", "OPEN_BOX", "REFURB"}

# category: share, median price, price sigma, true-disposition probabilities
CATEGORIES = {
    "Electronics": (0.22, 120, 0.80, [0.30, 0.25, 0.20, 0.12, 0.10, 0.03]),
    "Home & Kitchen": (0.18, 45, 0.70, [0.40, 0.22, 0.08, 0.20, 0.07, 0.03]),
    "Apparel": (0.20, 30, 0.55, [0.60, 0.10, 0.00, 0.20, 0.07, 0.03]),
    "Toys & Games": (0.10, 25, 0.60, [0.45, 0.20, 0.03, 0.22, 0.07, 0.03]),
    "Sports & Outdoors": (0.10, 50, 0.70, [0.42, 0.22, 0.06, 0.20, 0.07, 0.03]),
    "Beauty & Personal Care": (0.08, 20, 0.50, [0.25, 0.05, 0.00, 0.15, 0.20, 0.35]),
    "Tools & Home Improvement": (0.07, 70, 0.70, [0.38, 0.24, 0.12, 0.16, 0.07, 0.03]),
    "Books & Media": (0.05, 15, 0.50, [0.55, 0.15, 0.00, 0.20, 0.08, 0.02]),
}
MONTH_FACTOR = {7: 0.85, 8: 0.85, 9: 0.85, 10: 0.95, 11: 1.10, 12: 1.35, 1: 1.60,
                2: 1.10, 3: 0.95, 4: 0.90, 5: 0.90, 6: 0.90}
WEEKDAY_FACTOR = np.array([1.15, 1.05, 1.00, 0.97, 0.95, 0.90, 0.85])  # Mon..Sun

RETURN_REASONS = ["Changed mind", "No longer needed", "Better price elsewhere",
                  "Wrong item sent", "Defective", "Damaged in transit", "Missing parts"]
# reason probabilities by true disposition index
REASON_P = np.array([
    [0.35, 0.30, 0.15, 0.12, 0.03, 0.03, 0.02],  # NEW
    [0.25, 0.25, 0.10, 0.10, 0.10, 0.12, 0.08],  # OPEN_BOX
    [0.08, 0.07, 0.03, 0.05, 0.45, 0.20, 0.12],  # REFURB
    [0.15, 0.15, 0.05, 0.05, 0.25, 0.20, 0.15],  # LIQUIDATE
    [0.05, 0.05, 0.02, 0.03, 0.45, 0.30, 0.10],  # RECYCLE
    [0.05, 0.05, 0.02, 0.03, 0.35, 0.40, 0.10],  # DESTROY
])

DEFECT_CAUSES = ["Cosmetic grade misread", "Functional test skipped",
                 "Accessories/parts not verified", "Packaging condition misjudged",
                 "Wrong SOP criteria applied", "No photo evidence captured",
                 "System/data entry error"]


def build_associates(rng: np.random.Generator) -> pd.DataFrame:
    """Simulate associate hire/term stints per site and shift, including Q4 seasonal hires."""
    rows = []
    seq = 0
    for site_id, _, _, _, share, _ in SITES:
        scale = share / 0.25
        for shift in SHIFTS:
            core = int(round(CORE_HEADCOUNT[shift] * scale))
            mean_stint_days = 30.0 / MONTHLY_ATTRITION[shift]
            for _slot in range(core):
                hire = START - pd.Timedelta(days=int(rng.uniform(30, 1500)))
                # first stint: remaining length from START (memoryless)
                term = START + pd.Timedelta(days=int(rng.exponential(mean_stint_days)))
                while True:
                    seq += 1
                    rows.append((f"A{seq:04d}", site_id, shift, hire, term if term <= END else pd.NaT, "Core"))
                    if term > END:
                        break
                    hire = term + pd.Timedelta(days=int(rng.integers(3, 15)))
                    if hire > END:
                        break
                    term = hire + pd.Timedelta(days=int(rng.exponential(mean_stint_days)) + 1)
            # Q4 seasonal hires: about half of core headcount, hired mid-Oct to end-Nov, released 25 Jan to 28 Feb
            for _ in range(int(round(core * 0.5))):
                seq += 1
                hire = pd.Timestamp("2025-10-15") + pd.Timedelta(days=int(rng.integers(0, 47)))
                if rng.random() < 0.2:
                    term = pd.NaT  # converted to core
                else:
                    term = pd.Timestamp("2026-01-25") + pd.Timedelta(days=int(rng.integers(0, 35)))
                rows.append((f"A{seq:04d}", site_id, shift, hire, term, "Seasonal"))
    df = pd.DataFrame(rows, columns=["associate_id", "site_id", "shift", "hire_date",
                                     "term_date", "employment_type"])
    return df


def main() -> None:
    rng = np.random.default_rng(SEED)
    RAW.mkdir(parents=True, exist_ok=True)

    associates = build_associates(rng)

    days = pd.date_range(START, END, freq="D")
    dfac = np.array([MONTH_FACTOR[d.month] * WEEKDAY_FACTOR[d.weekday()] for d in days])
    base_daily = N_TARGET / dfac.sum()

    # --- unit skeleton: day x site x shift volumes ---------------------------------
    parts = []
    site_cap = {s[0]: s[3] for s in SITES}
    backlog_rows = []
    for site_id, _, _, cap, share, _ in SITES:
        site_daily = rng.poisson(base_daily * share * dfac)
        roll = pd.Series(site_daily).rolling(7, min_periods=1).mean().to_numpy()
        backlog_idx = np.clip(roll / cap, 0.5, None)
        backlog_rows.append(pd.DataFrame({"date": days, "site_id": site_id, "backlog_idx": backlog_idx}))
        for shift, (sshare, start_hr) in SHIFTS.items():
            a = associates[(associates.site_id == site_id) & (associates["shift"] == shift)]
            a_ids = a.associate_id.to_numpy()
            a_hire = a.hire_date.to_numpy()
            a_term = a.term_date.fillna(pd.Timestamp("2099-01-01")).to_numpy()
            n_shift = rng.binomial(site_daily, sshare)
            for di, d in enumerate(days):
                n = int(n_shift[di])
                if n == 0:
                    continue
                d64 = np.datetime64(d)
                active = (a_hire <= d64) & (a_term > d64)
                pool = a_ids[active] if active.any() else a_ids
                assoc = rng.choice(pool, size=n)
                minutes = rng.integers(0, 8 * 60, size=n)
                ts = d + pd.Timedelta(hours=start_hr) + pd.to_timedelta(minutes, unit="m")
                parts.append(pd.DataFrame({"received_ts": ts, "site_id": site_id, "shift": shift,
                                           "associate_id": assoc}))
    units = pd.concat(parts, ignore_index=True).sort_values("received_ts").reset_index(drop=True)
    backlog = pd.concat(backlog_rows, ignore_index=True)
    n = len(units)
    units["unit_id"] = [f"RU{i:07d}" for i in range(1, n + 1)]
    # Night shift crosses midnight; operational date = shift start date
    units["op_date"] = units.received_ts.dt.normalize()
    units.loc[units["shift"] == "Night", "op_date"] = (
        units.loc[units["shift"] == "Night", "received_ts"] - pd.Timedelta(hours=22)).dt.normalize()

    # --- item attributes ------------------------------------------------------------
    cat_names = list(CATEGORIES)
    cat_p = np.array([CATEGORIES[c][0] for c in cat_names])
    cat_idx = rng.choice(len(cat_names), size=n, p=cat_p / cat_p.sum())
    units["category"] = np.array(cat_names)[cat_idx]
    med = np.array([CATEGORIES[c][1] for c in cat_names])[cat_idx]
    sig = np.array([CATEGORIES[c][2] for c in cat_names])[cat_idx]
    units["item_price_usd"] = np.round(np.clip(med * np.exp(rng.normal(0, sig)), 4.99, 2500), 2)

    true_idx = np.empty(n, dtype=int)
    for ci, c in enumerate(cat_names):
        m = cat_idx == ci
        p = np.array(CATEGORIES[c][3])
        true_idx[m] = rng.choice(6, size=m.sum(), p=p / p.sum())
    reason_idx = np.array([rng.choice(7, p=REASON_P[t]) for t in true_idx])
    units["return_reason"] = np.array(RETURN_REASONS)[reason_idx]

    site_short = units.site_id.str.replace("RC-", "", regex=False).str[:3]
    units["grading_station"] = site_short + "-GS" + pd.Series(rng.integers(1, 7, size=n)).astype(str).str.zfill(2)

    # SOP version / photo step
    d = units.op_date
    is_pilot_site = units.site_id == PILOT_SITE
    v30 = (d >= CONTROL_START) | (is_pilot_site & (d >= PILOT_START))
    units["sop_version"] = np.where(v30, "v3.0", np.where(d >= SOP22_START, "v2.2", "v2.1"))
    photo_capable = units.site_id.map({s[0]: s[5] for s in SITES}).astype(bool) | v30
    units["photo_step_done"] = (photo_capable & (rng.random(n) < 0.96)).astype(int)

    # tenure (computed from associate hire date; stored only in associates.csv)
    hire = units.associate_id.map(associates.set_index("associate_id").hire_date)
    tenure = (units.op_date - hire).dt.days.clip(lower=0).to_numpy()

    units = units.merge(backlog, left_on=["op_date", "site_id"], right_on=["date", "site_id"], how="left")
    bidx = units.backlog_idx.to_numpy()

    # --- defect (misgrade) model ----------------------------------------------------
    assoc_eff = dict(zip(associates.associate_id, rng.normal(0, 0.25, len(associates))))
    station_eff = {s: rng.normal(0, 0.08) for s in units.grading_station.unique()}
    is_v30 = v30.to_numpy()
    is_elec = units.category.to_numpy() == "Electronics"
    is_ob = true_idx == 1
    logit = (-3.45
             + np.where(tenure < 30, 1.05, np.where(tenure < 90, 0.35, 0.0))
             + np.where(is_elec, np.where(is_v30, 0.15, 0.65), 0.0)
             + np.where(is_ob, np.where(is_v30, 0.10, 0.60), 0.0)
             + np.where(units["shift"].to_numpy() == "Night", 0.45, 0.0)
             + np.where(units.photo_step_done.to_numpy() == 0, 0.60, 0.0)
             + 0.9 * np.clip(bidx - 1.0, 0, None)
             + np.where(is_v30, -0.35, 0.0)
             + units.associate_id.map(assoc_eff).to_numpy()
             + units.grading_station.map(station_eff).to_numpy())
    p_def = 1 / (1 + np.exp(-logit))
    is_defect = rng.random(n) < p_def

    assigned_idx = true_idx.copy()
    dfx = np.where(is_defect)[0]
    down = rng.random(len(dfx)) < 0.62
    step = np.where(rng.random(len(dfx)) < 0.7, 1, 2)
    move = np.where(down, step, -1)
    new_idx = true_idx[dfx] + move
    # bounce off the ends of the disposition ladder
    new_idx = np.where(new_idx > 5, true_idx[dfx] - 1, new_idx)
    new_idx = np.where(new_idx < 0, true_idx[dfx] + 1, new_idx)
    # functional-test gaps push refurbishable / open-box units straight to recycle or destroy (waste)
    r = rng.random(len(dfx))
    t = true_idx[dfx]
    new_idx = np.where(down & (t == 2) & (r < 0.45), 4, new_idx)
    new_idx = np.where(down & (t == 2) & (r >= 0.45) & (r < 0.55), 5, new_idx)
    new_idx = np.where(down & (t == 1) & (r < 0.15), 4, new_idx)
    assigned_idx[dfx] = new_idx
    upgrade = assigned_idx < true_idx

    units["assigned_disposition"] = np.array(DISPOSITIONS)[assigned_idx]
    price = units.item_price_usd.to_numpy()
    pct = np.array([RECOVERY_PCT[x] for x in DISPOSITIONS])
    potential = price * pct[true_idx]
    achieved = np.where(~is_defect, potential * rng.uniform(0.97, 1.0, n),
                        np.where(upgrade, potential * 0.80, price * pct[assigned_idx]))
    units["potential_recovery_usd"] = np.round(potential, 2)
    units["recovery_achieved_usd"] = np.round(achieved, 2)
    units["waste_flag"] = (np.isin(assigned_idx, [4, 5]) & (true_idx <= 2)).astype(int)
    units["customer_complaint_flag"] = (np.where(upgrade, rng.random(n) < 0.42,
                                                 rng.random(n) < 0.004)).astype(int)
    p_regrade = 0.015 + 0.04 * (units.photo_step_done.to_numpy() == 0) + 0.01 * is_elec
    units["regrade_flag"] = (rng.random(n) < p_regrade).astype(int)

    # --- cycle-time stages (hours) -------------------------------------------------
    night = units["shift"].to_numpy() == "Night"
    stages = pd.DataFrame({"unit_id": units.unit_id})
    stages["dock_wait_hrs"] = 2.0 * np.exp(rng.normal(0, 0.5, n)) * bidx ** 1.5
    stages["triage_hrs"] = 0.40 * np.exp(rng.normal(0, 0.35, n))
    stages["queue_to_grade_hrs"] = 6.0 * np.exp(rng.normal(0, 0.6, n)) * bidx ** 2.5 * np.where(night, 1.3, 1.0)
    stages["grading_hrs"] = (np.where(is_elec, 0.60, 0.35) + np.where(is_v30, 0.05, 0.0)) * np.exp(rng.normal(0, 0.3, n))
    stages["routing_hrs"] = 3.0 * np.exp(rng.normal(0, 0.5, n)) * np.where(units.regrade_flag == 1, 2.5, 1.0)
    stages = stages.round({"dock_wait_hrs": 2, "triage_hrs": 2, "queue_to_grade_hrs": 2,
                           "grading_hrs": 2, "routing_hrs": 2})
    stages["dock_to_disposition_hrs"] = stages[["dock_wait_hrs", "triage_hrs", "queue_to_grade_hrs",
                                                "grading_hrs", "routing_hrs"]].sum(axis=1).round(2)

    # --- audits -----------------------------------------------------------------------
    pilot_window = is_pilot_site & (d >= PILOT_START) & (d < CONTROL_START)
    audit_rate = np.where(pilot_window, 0.20, 0.10)
    audited = rng.random(n) < audit_rate
    a_units = units.loc[audited, ["unit_id", "op_date", "site_id"]].copy()
    a_true = true_idx[audited]
    a_def = is_defect[audited]
    a_units["audit_date"] = a_units.op_date + pd.to_timedelta(rng.integers(1, 4, len(a_units)), unit="D")
    site_auditors = {s[0]: [f"QA{si * 3 + k + 1:02d}" for k in range(3)] for si, s in enumerate(SITES)}
    a_units["auditor_id"] = [site_auditors[s][i] for s, i in zip(a_units.site_id, rng.integers(0, 3, len(a_units)))]
    a_units["audited_disposition"] = np.array(DISPOSITIONS)[a_true]

    # defect cause: weights depend on which drivers were present
    idx_a = np.where(audited)[0]
    causes = np.array([""] * len(idx_a), dtype=object)
    for j, ui in enumerate(idx_a):
        if not a_def[j]:
            continue
        w = np.array([0.22, 0.08, 0.06, 0.08, 0.06, 0.0, 0.04])
        if (is_elec[ui] or is_ob[ui]) and not is_v30[ui]:
            w += np.array([0.05, 0.15, 0.02, 0.0, 0.45, 0.0, 0.0])
        if units.photo_step_done.iat[ui] == 0:
            w += np.array([0.25, 0.0, 0.0, 0.03, 0.0, 0.12, 0.0])
        if tenure[ui] < 30:
            w += np.array([0.03, 0.03, 0.06, 0.0, 0.20, 0.0, 0.02])
        if bidx[ui] > 1.1:
            w += np.array([0.0, 0.15, 0.02, 0.0, 0.0, 0.0, 0.04])
        causes[j] = DEFECT_CAUSES[rng.choice(7, p=w / w.sum())]
    a_units["defect_cause"] = causes
    audits = a_units[["unit_id", "audit_date", "auditor_id", "audited_disposition", "defect_cause"]].copy()
    audits.insert(0, "audit_id", [f"AU{i:06d}" for i in range(1, len(audits) + 1)])

    # --- dirty records (cleaned in build_db.py) ---------------------------------------
    out = units[["unit_id", "received_ts", "site_id", "shift", "associate_id", "category",
                 "return_reason", "grading_station", "sop_version", "photo_step_done",
                 "item_price_usd", "assigned_disposition", "regrade_flag", "potential_recovery_usd",
                 "recovery_achieved_usd", "waste_flag", "customer_complaint_flag"]].copy()
    out["received_ts"] = out.received_ts.dt.strftime("%Y-%m-%d %H:%M")
    out["item_price_usd"] = out.item_price_usd.astype(object)
    ix = rng.choice(n, 350, replace=False)
    out.loc[ix, "item_price_usd"] = np.nan
    ix = rng.choice(n, 12, replace=False)
    out.loc[ix, "item_price_usd"] = -out.loc[ix, "item_price_usd"].astype(float).abs()
    ix = rng.choice(n, 400, replace=False)
    out.loc[ix, "category"] = [c.lower() + " " if k % 2 else c.upper() for k, c in enumerate(out.loc[ix, "category"])]
    ix = rng.choice(n, 250, replace=False)
    out.loc[ix, "shift"] = np.nan
    dup = out.iloc[rng.choice(n, 180, replace=False)]
    out = pd.concat([out, dup], ignore_index=True)

    ix = rng.choice(n, 25, replace=False)
    stages.loc[ix, "queue_to_grade_hrs"] = -stages.loc[ix, "queue_to_grade_hrs"]
    stages["dock_to_disposition_hrs"] = stages[["dock_wait_hrs", "triage_hrs", "queue_to_grade_hrs",
                                                "grading_hrs", "routing_hrs"]].sum(axis=1).round(2)

    audits["audit_date"] = audits.audit_date.dt.strftime("%Y-%m-%d")
    orphans = audits.sample(8, random_state=SEED).copy()
    orphans["unit_id"] = [f"RU9{i:06d}" for i in range(8)]
    orphans["audit_id"] = [f"AU9{i:05d}" for i in range(8)]
    audits = pd.concat([audits, orphans, audits.sample(15, random_state=SEED + 1)], ignore_index=True)

    # --- dimensions -----------------------------------------------------------------------
    sites = pd.DataFrame([(s[0], s[1], s[2], s[3], s[5]) for s in SITES],
                         columns=["site_id", "site_name", "region", "daily_capacity_units",
                                  "photo_grading_step_baseline"])
    sop = pd.DataFrame([
        ("v2.1", "2024-01-15", "2025-09-30", "All sites", 0, 0,
         "Legacy grading SOP; open-box and electronics criteria described in free text"),
        ("v2.2", "2025-10-01", "2026-04-30", "All sites (RC-CENTRAL until 2026-02-28)", 0, 0,
         "Peak-season refresh; layout changes only, grading criteria unchanged"),
        ("v3.0", "2026-03-01", "", "RC-CENTRAL pilot from 2026-03-01; all sites from 2026-05-01", 1, 1,
         "Visual open-box/electronics grading matrix, 8-point grading checklist, mandatory photo capture"),
    ], columns=["sop_version", "effective_from", "effective_to", "scope", "has_checklist",
                "requires_photo", "change_summary"])
    disp = pd.DataFrame({"disposition": DISPOSITIONS, "ladder_rank": range(1, 7),
                         "recovery_pct_of_price": [RECOVERY_PCT[x] for x in DISPOSITIONS],
                         "resellable_flag": [int(x in RESELLABLE) for x in DISPOSITIONS]})

    assoc_out = associates.copy()
    assoc_out["hire_date"] = assoc_out.hire_date.dt.strftime("%Y-%m-%d")
    assoc_out["term_date"] = assoc_out.term_date.dt.strftime("%Y-%m-%d")

    out.to_csv(RAW / "returns_units.csv", index=False)
    stages.to_csv(RAW / "unit_cycle_stages.csv", index=False)
    audits.to_csv(RAW / "audits.csv", index=False)
    assoc_out.to_csv(RAW / "associates.csv", index=False)
    sites.to_csv(RAW / "sites.csv", index=False)
    sop.to_csv(RAW / "sop_versions.csv", index=False)
    disp.to_csv(RAW / "disposition_values.csv", index=False)
    print(f"units={len(out):,} (incl. dup rows) audits={len(audits):,} associates={len(assoc_out):,}")
    print(f"true defect rate (all units) = {is_defect.mean():.4f}")


if __name__ == "__main__":
    main()
