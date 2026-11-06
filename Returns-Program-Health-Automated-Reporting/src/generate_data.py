"""Generate seeded synthetic data for the Returns Program Health WBR.

Outputs (data/raw/):
  shipments_daily.csv   date x marketplace x category  units shipped
  returns_daily.csv     date x marketplace x category x return channel  additive return measures
  kpi_targets.csv       one row per WBR KPI: target, direction, owner team, linked initiative
  initiatives.csv       program initiatives
  milestones.csv        initiative tracker (planned vs actual vs forecast dates, status, dependency)
  risks.csv             risk register
  issues.csv            issue log

All data is synthetic. None of it comes from Amazon or any employer. It follows common
e-commerce returns patterns (holiday seasonality, a post-holiday return peak, channel mix shifts),
and a few dirty records are added on purpose (duplicates, mixed-case keys, negative and missing
values) so build_db.py has something real to clean.
"""
import numpy as np
import pandas as pd

from config import RAW, SEED, DATA_START, DATA_END

rng = np.random.default_rng(SEED)

MKTS = {"US": 1.00, "UK": 0.35, "DE": 0.30, "CA": 0.18}
MKT_CYCLE = {"US": 1.00, "UK": 1.04, "DE": 1.08, "CA": 1.15}
# category: share of units, base return rate, avg refund $/unit, disposition probs [resale, liquidate, recycle, waste]
CATS = {
    "Electronics": dict(share=0.22, rr=0.105, aov=168.0, disp=[0.44, 0.38, 0.12, 0.06]),
    "Apparel":     dict(share=0.30, rr=0.150, aov=41.0,  disp=[0.58, 0.30, 0.06, 0.06]),
    "Home":        dict(share=0.22, rr=0.068, aov=63.0,  disp=[0.40, 0.42, 0.08, 0.10]),
    "Toys":        dict(share=0.12, rr=0.058, aov=29.0,  disp=[0.36, 0.40, 0.10, 0.14]),
    "Beauty":      dict(share=0.14, rr=0.034, aov=21.0,  disp=[0.10, 0.30, 0.18, 0.42]),
}
CHANNELS = ["Mail-in", "Drop-off", "Carrier Pickup", "Returnless"]
# base transit (customer -> receive) and processing (receive -> refund) days by channel
TRANSIT = {"Mail-in": 3.05, "Drop-off": 1.70, "Carrier Pickup": 2.20, "Returnless": 0.0}
PROCESS = {"Mail-in": 1.00, "Drop-off": 0.85, "Carrier Pickup": 1.05, "Returnless": 0.25}
CPR = {"Mail-in": 0.205, "Drop-off": 0.150, "Carrier Pickup": 0.180, "Returnless": 0.070}
COST = {"Mail-in": 7.40, "Drop-off": 5.20, "Carrier Pickup": 9.30, "Returnless": 1.10}
TOTAL_DAILY_UNITS = 240_000


def ramp(dates, start, end, size):
    """Linear ramp from 0 to `size` between start and end dates."""
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    frac = np.asarray((dates - s).days, dtype=float) / max((e - s).days, 1)
    return np.clip(frac, 0, 1) * size


def make_shipments(dates):
    rows = []
    doy = dates.dayofyear.values
    month = dates.month.values
    holiday = np.where(month == 11, 1.30, np.where(month == 12, 1.55, 1.0))
    prime = np.where((month == 7) & (dates.day.values >= 8) & (dates.day.values <= 12), 1.45, 1.0)
    dow = np.array([1.04, 1.00, 0.98, 0.99, 1.02, 0.97, 0.95])[dates.dayofweek.values]
    growth = 1.0 + 0.08 * ((dates - dates[0]).days.values / 365.0)
    base = TOTAL_DAILY_UNITS * holiday * prime * dow * growth * (1 + 0.03 * np.sin(2 * np.pi * doy / 365))
    mtot = sum(MKTS.values())
    for m, mw in MKTS.items():
        for c, cp in CATS.items():
            mu = base * (mw / mtot) * cp["share"]
            units = rng.poisson(mu * rng.lognormal(0, 0.04, len(dates)))
            rows.append(pd.DataFrame({"date": dates, "marketplace": m, "category": c, "units_shipped": units}))
    return pd.concat(rows, ignore_index=True)


def channel_shares(dates, m, c):
    n = len(dates)
    mail = np.full(n, 0.46)
    drop = np.full(n, 0.27)
    pick = np.full(n, 0.25)
    rless = np.full(n, 0.02 if c != "Electronics" else 0.0)
    # Drop-off point expansion: Wave 1 (US) went live 2026-07-10, shifts volume from mail-in
    if m == "US":
        shift = ramp(dates, "2026-07-10", "2026-08-31", 0.08)
        mail = mail - shift
        drop = drop + shift
    # Returnless refunds for low-value items: US Beauty/Toys from 2026-07-03
    if m == "US" and c in ("Beauty", "Toys"):
        extra = ramp(dates, "2026-07-03", "2026-08-15", 0.16)
        rless = rless + extra
        mail = mail - extra * 0.6
        pick = pick - extra * 0.4
    if m in ("UK", "DE") and c in ("Beauty", "Toys", "Apparel"):
        extra = ramp(dates, "2026-10-30", "2026-11-01", 0.04)
        rless = rless + extra
        mail = mail - extra
    sh = np.vstack([mail, drop, pick, rless]).T
    sh = np.clip(sh, 0.001, None)
    return sh / sh.sum(axis=1, keepdims=True)


def make_returns(ship):
    out = []
    for (m, c), g in ship.groupby(["marketplace", "category"], sort=False):
        g = g.sort_values("date")
        dates = pd.DatetimeIndex(g["date"])
        n = len(dates)
        cp = CATS[c]
        month = dates.month.values
        rr_season = np.where(month == 1, 1.28, np.where(month == 2, 1.10, np.where(month == 12, 1.08, 1.0)))
        rr = cp["rr"] * rr_season * rng.lognormal(0, 0.035, n)
        ret = rng.poisson(g["units_shipped"].values * rr)
        sh = channel_shares(dates, m, c)
        split = np.array([rng.multinomial(r, p) for r, p in zip(ret, sh)])
        for j, ch in enumerate(CHANNELS):
            u = split[:, j]
            refund = u * cp["aov"] * rng.lognormal(0, 0.06, n)
            transit = np.full(n, TRANSIT[ch]) * MKT_CYCLE[m]
            process = np.full(n, PROCESS[ch])
            # Holiday peak processing congestion
            process = process + np.where(np.isin(month, [12, 1]), 0.35, 0.0)
            # Injected incident: US Mail-in carrier linehaul consolidation adds transit days from 2026-09-28
            if m == "US" and ch == "Mail-in":
                transit = transit + ramp(dates, "2026-09-28", "2026-10-31", 2.4)
            # Drop-off expansion improves drop-off transit slightly in US
            if m == "US" and ch == "Drop-off":
                transit = transit - ramp(dates, "2026-07-10", "2026-09-30", 0.25)
            transit = np.clip(transit * rng.lognormal(0, 0.05, n), 0, None)
            process = np.clip(process * rng.lognormal(0, 0.06, n), 0.05, None)
            cycle = transit + process
            # Contacts rise when the refund takes longer than the channel norm
            norm = TRANSIT[ch] * MKT_CYCLE[m] + PROCESS[ch]
            cpr = np.clip(CPR[ch] + 0.034 * (cycle - norm), 0.02, None)
            contacts = rng.poisson(u * cpr)
            # Disposition mix (customer keeps item for returnless refunds)
            disp = np.tile(np.array(cp["disp"], dtype=float), (n, 1))
            if c == "Electronics":  # Grade-and-resell open-box electronics
                lift = ramp(dates, "2026-05-22", "2026-09-15", 0.055)
                disp[:, 0] += lift
                disp[:, 1] -= lift
            # Liquidation partner onboarding moves recycle/waste into liquidation
            lp = ramp(dates, "2026-06-26", "2026-08-31", 0.25) + (ramp(dates, "2026-10-09", "2026-10-31", 0.15) if m in ("UK", "DE") else 0)
            moved = disp[:, 3] * lp
            disp[:, 3] -= moved
            disp[:, 1] += moved
            disp = disp / disp.sum(axis=1, keepdims=True)
            if ch == "Returnless":
                dsplit = np.zeros((n, 4), dtype=int)
            else:
                dsplit = np.array([rng.multinomial(x, p) for x, p in zip(u, disp)])
            avg_ref = np.divide(refund, np.maximum(u, 1))
            resale_rec = 0.68 if c == "Electronics" else 0.58
            liq_rec = 0.15 + ramp(dates, "2026-06-26", "2026-08-15", 0.05) + (ramp(dates, "2026-10-09", "2026-10-31", 0.03) if m in ("UK", "DE") else 0)
            recovered = avg_ref * (dsplit[:, 0] * resale_rec + dsplit[:, 1] * liq_rec + dsplit[:, 2] * 0.02)
            recovered = recovered * rng.lognormal(0, 0.05, n)
            cost = u * COST[ch] * rng.lognormal(0, 0.04, n) + dsplit[:, 3] * 0.85
            out.append(pd.DataFrame({
                "date": dates, "marketplace": m, "category": c, "channel": ch,
                "return_units": u,
                "refund_usd": refund.round(2),
                "transit_hours": (transit * 24 * u).round(1),
                "processing_hours": (process * 24 * u).round(1),
                "customer_contacts": contacts,
                "resold_units": dsplit[:, 0], "liquidated_units": dsplit[:, 1],
                "recycled_units": dsplit[:, 2], "waste_units": dsplit[:, 3],
                "recovered_usd": recovered.round(2),
                "processing_cost_usd": cost.round(2),
            }))
    return pd.concat(out, ignore_index=True)


def inject_dirty(df):
    """Inject realistic data-quality issues for build_db.py to clean."""
    df = df.copy()
    n = len(df)
    idx = rng.choice(n, 160, replace=False)
    df.loc[idx[:60], "marketplace"] = df.loc[idx[:60], "marketplace"].str.lower() + " "   # mixed-case keys
    df.loc[idx[60:100], ["transit_hours", "processing_hours"]] = np.nan                       # missing scans
    df.loc[idx[100:115], "return_units"] = -df.loc[idx[100:115], "return_units"].abs() - 1   # sign errors
    df.loc[idx[115:160], "channel"] = df.loc[idx[115:160], "channel"].str.upper()            # inconsistent labels
    dups = df.sample(45, random_state=SEED)                                                   # duplicate loads
    df = pd.concat([df, dups], ignore_index=True)
    return df.sample(frac=1.0, random_state=SEED).reset_index(drop=True)


def tracker_tables():
    initiatives = pd.DataFrame([
        ["INI-1", "Grade-and-resell open-box electronics", "ReCommerce Program Manager", "ReCommerce", "resale_pct", "2026-02-02", "2027-01-15"],
        ["INI-2", "Returnless refunds for low-value items", "Returns Policy Manager", "Returns Policy", "cost_per_return", "2026-03-02", "2026-12-18"],
        ["INI-3", "Drop-off point expansion", "Reverse Logistics Program Manager", "Reverse Logistics Ops", "refund_cycle_days", "2026-01-12", "2026-12-18"],
        ["INI-4", "Return reason capture redesign", "Returns Experience Product Manager", "Returns Experience Tech", "contacts_per_return", "2026-04-06", "2027-01-29"],
        ["INI-5", "Liquidation partner onboarding", "Disposition Program Manager", "Liquidation & Disposition", "recovery_rate", "2026-03-02", "2026-12-18"],
    ], columns=["initiative_id", "initiative", "owner_role", "team", "primary_kpi", "start_date", "target_end_date"])

    cols = ["milestone_id", "initiative_id", "milestone", "owner_role", "planned_start", "planned_end",
            "actual_start", "actual_end", "forecast_end", "status", "pct_complete", "depends_on"]
    ms = [
        ["M101", "INI-1", "Grading SOP and condition codes defined", "ReCommerce Program Manager", "2026-02-02", "2026-03-13", "2026-02-02", "2026-03-20", "", "Complete", 100, ""],
        ["M102", "INI-1", "Grading station pilot at 2 sites", "Returns Operations Manager", "2026-03-16", "2026-05-08", "2026-03-23", "2026-05-22", "", "Complete", 100, "M101"],
        ["M103", "INI-1", "Open-box listing integration", "Software Development Manager", "2026-05-11", "2026-07-31", "2026-05-26", "2026-08-21", "", "Complete", 100, "M102"],
        ["M104", "INI-1", "Scale grading to 6 sites", "Returns Operations Manager", "2026-08-03", "2026-10-30", "2026-08-24", "", "2026-11-20", "At Risk", 70, "M103"],
        ["M105", "INI-1", "Price optimization for graded tiers", "ReCommerce Analyst", "2026-10-05", "2026-12-11", "2026-10-12", "", "2026-12-18", "On Track", 35, ""],
        ["M106", "INI-1", "Program review and handoff to operations", "ReCommerce Program Manager", "2026-12-14", "2027-01-15", "", "", "", "Not Started", 0, "M104"],
        ["M201", "INI-2", "Policy thresholds and abuse guardrails", "Returns Policy Manager", "2026-03-02", "2026-04-10", "2026-03-02", "2026-04-10", "", "Complete", 100, ""],
        ["M202", "INI-2", "Abuse-prevention rules with Risk partner", "Risk & Abuse Prevention Manager", "2026-04-13", "2026-05-29", "2026-04-13", "2026-06-12", "", "Complete", 100, "M201"],
        ["M203", "INI-2", "Launch returnless in Beauty/Toys (US)", "Returns Policy Manager", "2026-06-01", "2026-06-30", "2026-06-01", "2026-07-03", "", "Complete", 100, "M202"],
        ["M204", "INI-2", "Extend to Apparel and UK/DE", "Returns Policy Manager", "2026-08-03", "2026-10-16", "2026-08-10", "2026-10-30", "", "Complete", 100, "M203"],
        ["M205", "INI-2", "Bad-debt and abuse monitoring dashboard", "Business Intelligence Engineer", "2026-09-07", "2026-11-13", "2026-09-07", "", "2026-11-13", "On Track", 75, ""],
        ["M206", "INI-2", "Expand to CA", "Returns Policy Manager", "2026-11-16", "2026-12-18", "", "", "", "Not Started", 0, "M205"],
        ["M301", "INI-3", "Site selection model and partner shortlist", "Reverse Logistics Program Manager", "2026-01-12", "2026-02-27", "2026-01-12", "2026-02-27", "", "Complete", 100, ""],
        ["M302", "INI-3", "Retail drop-off partner contracts signed", "Vendor Manager", "2026-03-02", "2026-04-24", "2026-03-02", "2026-05-15", "", "Complete", 100, "M301"],
        ["M303", "INI-3", "Wave 1 go-live (400 points, US)", "Reverse Logistics Program Manager", "2026-04-27", "2026-06-26", "2026-05-18", "2026-07-10", "", "Complete", 100, "M302"],
        ["M304", "INI-3", "Wave 2 go-live (900 points, US/CA)", "Reverse Logistics Program Manager", "2026-07-13", "2026-10-02", "2026-07-20", "", "2026-11-27", "Blocked", 55, "M402"],
        ["M305", "INI-3", "Carrier consolidation SLA review", "Transportation Manager", "2026-10-05", "2026-11-06", "2026-10-12", "", "2026-11-20", "At Risk", 40, ""],
        ["M306", "INI-3", "Wave 3 plan and business case", "Reverse Logistics Program Manager", "2026-11-09", "2026-12-18", "", "", "", "Not Started", 0, "M304"],
        ["M401", "INI-4", "Customer research and reason taxonomy", "UX Researcher", "2026-04-06", "2026-05-15", "2026-04-06", "2026-05-22", "", "Complete", 100, ""],
        ["M402", "INI-4", "QR label and reason-code API", "Software Development Manager", "2026-06-01", "2026-09-11", "2026-06-15", "", "2026-11-13", "At Risk", 60, "M401"],
        ["M403", "INI-4", "Return-flow UX redesign A/B test", "Returns Experience Product Manager", "2026-09-14", "2026-10-23", "", "", "2026-12-04", "Blocked", 10, "M402"],
        ["M404", "INI-4", "Reason-code data feed to Operations", "Data Engineer", "2026-10-26", "2026-12-04", "", "", "2026-12-18", "Not Started", 0, "M402"],
        ["M405", "INI-4", "Launch to all marketplaces", "Returns Experience Product Manager", "2026-12-07", "2027-01-29", "", "", "", "Not Started", 0, "M403"],
        ["M501", "INI-5", "RFP and partner scoring", "Disposition Program Manager", "2026-03-02", "2026-04-17", "2026-03-02", "2026-04-17", "", "Complete", 100, ""],
        ["M502", "INI-5", "Partner 1 onboarding (US electronics/home)", "Disposition Program Manager", "2026-04-20", "2026-06-26", "2026-04-20", "2026-06-26", "", "Complete", 100, "M501"],
        ["M503", "INI-5", "Partner 2 onboarding (EU)", "Disposition Program Manager", "2026-07-06", "2026-09-25", "2026-07-06", "2026-10-09", "", "Complete", 100, "M501"],
        ["M504", "INI-5", "Auction price floors and recovery tracking", "Finance Partner", "2026-09-28", "2026-11-20", "2026-09-28", "", "2026-11-20", "On Track", 50, "M502"],
        ["M505", "INI-5", "Partner 3 onboarding (apparel bulk lots)", "Disposition Program Manager", "2026-10-12", "2026-12-18", "2026-10-12", "", "2026-12-18", "On Track", 20, "M501"],
    ]
    milestones = pd.DataFrame(ms, columns=cols)

    rcols = ["risk_id", "initiative_id", "risk", "likelihood", "impact", "status", "owner_role", "mitigation",
             "opened_date", "target_close_date"]
    risks = pd.DataFrame([
        ["R01", "INI-1", "Grading labor not staffed at 4 of 6 scale sites before peak", 4, 4, "Open", "Returns Operations Manager", "Cross-train inbound associates; stagger site launches", "2026-09-14", "2026-11-13"],
        ["R02", "INI-1", "Open-box price erosion if graded supply outpaces demand", 3, 3, "Mitigating", "ReCommerce Analyst", "Tiered price floors; weekly sell-through review", "2026-07-06", "2026-12-11"],
        ["R03", "INI-2", "Returnless refunds increase abuse / bad debt in new categories", 3, 5, "Mitigating", "Risk & Abuse Prevention Manager", "Per-customer frequency caps; abuse dashboard (M205)", "2026-04-20", "2026-11-13"],
        ["R04", "INI-3", "QR label API slip blocks Wave 2 drop-off go-live", 5, 4, "Open", "Software Development Manager", "", "2026-09-14", "2026-10-30"],
        ["R05", "INI-3", "Carrier linehaul consolidation lengthens US mail-in transit", 5, 4, "Open", "Transportation Manager", "", "2026-10-12", "2026-11-06"],
        ["R06", "INI-3", "Retail partner capacity limits during holiday peak", 3, 3, "Open", "Vendor Manager", "Peak capacity clauses; overflow to carrier pickup", "2026-08-03", "2026-12-18"],
        ["R07", "INI-4", "Engineering capacity shared with peak code freeze", 4, 4, "Open", "Software Development Manager", "Request 2 additional SDEs; descope phase-2 fields", "2026-08-24", "2026-11-06"],
        ["R08", "INI-4", "Reason taxonomy change breaks downstream reports", 2, 3, "Mitigating", "Data Engineer", "Mapping table and parallel run for 4 weeks", "2026-06-01", "2026-12-04"],
        ["R09", "INI-5", "EU partner recovery below business case", 2, 4, "Closed", "Disposition Program Manager", "Auction floor pricing pilot", "2026-07-20", "2026-10-09"],
        ["R10", "INI-5", "Liquidation lot quality disputes delay payment", 3, 2, "Open", "Finance Partner", "Standard lot manifest and photo audit", "2026-10-12", "2026-12-18"],
    ], columns=rcols)

    issues = pd.DataFrame([
        ["ISS-001", "2026-05-12", "INI-1", "M102", "Pilot site grading accuracy below 95% in week 1", "Closed", "Returns Operations Manager"],
        ["ISS-002", "2026-08-05", "INI-1", "M103", "Listing integration defect duplicated open-box ASIN variants", "Closed", "Software Development Manager"],
        ["ISS-003", "2026-09-21", "INI-4", "M402", "API contract for reason codes not agreed with Ops tooling", "Open", "Software Development Manager"],
        ["ISS-004", "2026-10-02", "INI-3", "M304", "Wave 2 partners cannot print labels without QR API", "Open", "Reverse Logistics Program Manager"],
        ["ISS-005", "2026-10-14", "INI-3", "M305", "US mail-in transit scans show +2 day dwell at consolidation hubs", "Open", "Transportation Manager"],
        ["ISS-006", "2026-10-19", "INI-1", "M104", "Two scale sites missing grading benches", "Open", "Returns Operations Manager"],
        ["ISS-007", "2026-10-21", "INI-2", "M204", "UK returnless launch copy pending legal review", "Closed", "Returns Policy Manager"],
    ], columns=["issue_id", "logged_date", "initiative_id", "milestone_id", "issue", "status", "owner_role"])
    return initiatives, milestones, risks, issues


def targets_table():
    # direction: lower = lower is better; amber_band = tolerance before a miss turns Red
    return pd.DataFrame([
        ["return_rate", "Return rate", "pct", "lower", 0.0950, 0.05, "Returns Policy", "INI-2", 1],
        ["refund_cycle_days", "Refund cycle time", "days", "lower", 3.30, 0.05, "Reverse Logistics Ops", "INI-3", 2],
        ["contacts_per_return", "Customer contacts per return", "ratio", "lower", 0.180, 0.05, "Returns Experience Tech", "INI-4", 3],
        ["resale_pct", "Resold share of dispositions", "pct", "higher", 0.500, 0.03, "ReCommerce", "INI-1", 4],
        ["liquidation_pct", "Liquidated share of dispositions", "pct", "lower", 0.360, 0.05, "Liquidation & Disposition", "INI-5", 5],
        ["recovery_rate", "Recovery rate ($ recovered / $ refunded)", "pct", "higher", 0.360, 0.03, "Liquidation & Disposition", "INI-5", 6],
        ["waste_units", "Waste (landfill) units", "units", "lower", 11000, 0.05, "Liquidation & Disposition", "INI-5", 7],
        ["cost_per_return", "Cost per return", "usd", "lower", 6.80, 0.05, "Reverse Logistics Ops", "INI-3", 8],
    ], columns=["kpi", "display_name", "unit", "direction", "target", "amber_band", "owner_team", "initiative_id", "sort_order"])


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    dates = pd.date_range(DATA_START, DATA_END, freq="D")
    ship = make_shipments(dates)
    ret = make_returns(ship)
    ret = inject_dirty(ret)
    ship["date"] = ship["date"].dt.strftime("%Y-%m-%d")
    ret["date"] = pd.to_datetime(ret["date"]).dt.strftime("%Y-%m-%d")
    ship.to_csv(RAW / "shipments_daily.csv", index=False)
    ret.to_csv(RAW / "returns_daily.csv", index=False)
    targets_table().to_csv(RAW / "kpi_targets.csv", index=False)
    ini, ms, rk, iss = tracker_tables()
    ini.to_csv(RAW / "initiatives.csv", index=False)
    ms.to_csv(RAW / "milestones.csv", index=False)
    rk.to_csv(RAW / "risks.csv", index=False)
    iss.to_csv(RAW / "issues.csv", index=False)
    print(f"generate_data: shipments {len(ship):,} rows, returns {len(ret):,} rows (incl. injected dirty rows)")


if __name__ == "__main__":
    main()
