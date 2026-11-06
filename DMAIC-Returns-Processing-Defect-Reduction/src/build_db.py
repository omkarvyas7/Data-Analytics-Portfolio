"""Clean raw CSVs and load them into a SQLite database (data/returns_dmaic.db).

Cleaning rules (logged to data/processed/data_quality_log.csv):
  * exact duplicate unit rows -> keep first occurrence of each unit_id
  * category casing / whitespace variants -> mapped to canonical category names
  * missing item price -> category median (price_imputed_flag = 1)
  * negative item price -> absolute value (sign error at source)
  * missing shift -> derived from received hour (06-14 Day, 14-22 Swing, else Night)
  * negative stage durations -> stage and total cycle time set to NULL (excluded from cycle stats)
  * duplicate audit rows -> dropped; audits with no matching unit (orphans) -> dropped
Views created: v_units (unit grain, enriched) and v_audited (audit sample, with is_defect).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
DB = ROOT / "data" / "returns_dmaic.db"

CANON_CATS = ["Electronics", "Home & Kitchen", "Apparel", "Toys & Games", "Sports & Outdoors",
              "Beauty & Personal Care", "Tools & Home Improvement", "Books & Media"]
STAGES = ["dock_wait_hrs", "triage_hrs", "queue_to_grade_hrs", "grading_hrs", "routing_hrs"]

VIEWS = """
DROP VIEW IF EXISTS v_units;
CREATE VIEW v_units AS
WITH base AS (
    SELECT u.*,
           CASE WHEN u.shift = 'Night' AND CAST(strftime('%H', u.received_ts) AS INTEGER) < 6
                THEN date(u.received_ts, '-1 day') ELSE date(u.received_ts) END AS op_date
    FROM units u
)
SELECT b.*,
       CAST(julianday(b.op_date) - julianday(a.hire_date) AS INTEGER)            AS tenure_days,
       CASE WHEN julianday(b.op_date) - julianday(a.hire_date) < 30 THEN '0-29 days'
            WHEN julianday(b.op_date) - julianday(a.hire_date) < 90 THEN '30-89 days'
            WHEN julianday(b.op_date) - julianday(a.hire_date) < 365 THEN '90-364 days'
            ELSE '365+ days' END                                                 AS tenure_band,
       a.employment_type,
       date(b.op_date, printf('-%d days', (CAST(strftime('%w', b.op_date) AS INTEGER) + 6) % 7)) AS week_start,
       strftime('%Y-%m', b.op_date)                                              AS month,
       CASE WHEN b.op_date < '2026-03-01' THEN 'Baseline'
            WHEN b.op_date < '2026-05-01' THEN 'Pilot'
            ELSE 'Control' END                                                   AS phase,
       CASE WHEN b.site_id = 'RC-CENTRAL' THEN 1 ELSE 0 END                      AS is_pilot_site,
       s.dock_wait_hrs, s.triage_hrs, s.queue_to_grade_hrs, s.grading_hrs, s.routing_hrs,
       s.dock_to_disposition_hrs,
       CASE WHEN s.dock_to_disposition_hrs > 48 THEN 1 ELSE 0 END                AS sla_breach_flag,
       b.potential_recovery_usd - b.recovery_achieved_usd                        AS recovery_leakage_usd
FROM base b
JOIN associates a ON a.associate_id = b.associate_id
LEFT JOIN cycle_stages s ON s.unit_id = b.unit_id;

DROP VIEW IF EXISTS v_audited;
CREATE VIEW v_audited AS
SELECT v.*,
       au.audit_id, au.audit_date, au.auditor_id, au.audited_disposition,
       NULLIF(au.defect_cause, '')                                               AS defect_cause,
       CASE WHEN v.assigned_disposition <> au.audited_disposition THEN 1 ELSE 0 END AS is_defect,
       CASE WHEN da.ladder_rank < dt.ladder_rank THEN 'Upgrade (graded too high)'
            WHEN da.ladder_rank > dt.ladder_rank THEN 'Downgrade (graded too low)'
            ELSE 'Correct' END                                                   AS defect_direction
FROM v_units v
JOIN audits au ON au.unit_id = v.unit_id
JOIN disposition_values da ON da.disposition = v.assigned_disposition
JOIN disposition_values dt ON dt.disposition = au.audited_disposition;
"""


def main() -> None:
    PROC.mkdir(parents=True, exist_ok=True)
    log = []

    units = pd.read_csv(RAW / "returns_units.csv")
    stages = pd.read_csv(RAW / "unit_cycle_stages.csv")
    audits = pd.read_csv(RAW / "audits.csv", keep_default_na=False, na_values=[""])
    associates = pd.read_csv(RAW / "associates.csv")
    sites = pd.read_csv(RAW / "sites.csv")
    sop = pd.read_csv(RAW / "sop_versions.csv")
    disp = pd.read_csv(RAW / "disposition_values.csv")
    log.append(("returns_units", "raw rows", len(units)))

    before = len(units)
    units = units.drop_duplicates(subset="unit_id", keep="first")
    log.append(("returns_units", "duplicate unit rows removed", before - len(units)))

    canon = {c.lower(): c for c in CANON_CATS}
    cleaned = units.category.str.strip().str.lower().map(canon)
    log.append(("returns_units", "category variants standardized", int((cleaned != units.category).sum())))
    units["category"] = cleaned

    units["item_price_usd"] = pd.to_numeric(units.item_price_usd, errors="coerce")
    neg = units.item_price_usd < 0
    log.append(("returns_units", "negative prices corrected (abs)", int(neg.sum())))
    units.loc[neg, "item_price_usd"] = units.loc[neg, "item_price_usd"].abs()
    miss = units.item_price_usd.isna()
    units["price_imputed_flag"] = miss.astype(int)
    units.loc[miss, "item_price_usd"] = units.loc[miss, "category"].map(units.groupby("category").item_price_usd.median())
    log.append(("returns_units", "missing prices imputed (category median)", int(miss.sum())))

    hr = pd.to_datetime(units.received_ts).dt.hour
    derived = np.where((hr >= 6) & (hr < 14), "Day", np.where((hr >= 14) & (hr < 22), "Swing", "Night"))
    ms = units["shift"].isna()
    units.loc[ms, "shift"] = derived[ms.to_numpy()]
    log.append(("returns_units", "missing shift derived from received hour", int(ms.sum())))
    log.append(("returns_units", "clean rows", len(units)))

    bad = (stages[STAGES] < 0).any(axis=1)
    stages.loc[bad, STAGES + ["dock_to_disposition_hrs"]] = np.nan
    log.append(("unit_cycle_stages", "rows with negative stage time set to NULL", int(bad.sum())))

    before = len(audits)
    audits = audits.drop_duplicates(subset="audit_id")
    log.append(("audits", "duplicate audit rows removed", before - len(audits)))
    before = len(audits)
    audits = audits[audits.unit_id.isin(units.unit_id)]
    log.append(("audits", "orphan audits removed (no matching unit)", before - len(audits)))
    audits["defect_cause"] = audits.defect_cause.fillna("")
    log.append(("audits", "clean rows", len(audits)))

    # Sigma lookup (short-term sigma incl. the conventional 1.5-sigma shift), 0.01 steps
    lv = np.round(np.arange(0.0, 6.51, 0.01), 2)
    sigma = pd.DataFrame({"sigma_level": lv, "dpmo": (1 - norm.cdf(lv - 1.5)) * 1e6})

    if DB.exists():
        DB.unlink()
    con = sqlite3.connect(DB)
    units.to_sql("units", con, index=False)
    stages.to_sql("cycle_stages", con, index=False)
    audits.to_sql("audits", con, index=False)
    associates.to_sql("associates", con, index=False)
    sites.to_sql("sites", con, index=False)
    sop.to_sql("sop_versions", con, index=False)
    disp.to_sql("disposition_values", con, index=False)
    sigma.to_sql("sigma_lookup", con, index=False)
    con.executescript("""
        CREATE UNIQUE INDEX ix_units ON units(unit_id);
        CREATE UNIQUE INDEX ix_stages ON cycle_stages(unit_id);
        CREATE INDEX ix_audits ON audits(unit_id);
        CREATE UNIQUE INDEX ix_assoc ON associates(associate_id);
    """)
    con.executescript(VIEWS)
    con.commit()
    con.close()

    pd.DataFrame(log, columns=["table", "check", "rows"]).to_csv(PROC / "data_quality_log.csv", index=False)
    for t, c, r in log:
        print(f"{t:18s} {c:45s} {r:>8,}")


if __name__ == "__main__":
    main()
