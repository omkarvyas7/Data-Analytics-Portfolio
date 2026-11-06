"""Clean raw CSVs and load them into a SQLite database (data/returns_wbr.db).

Cleaning rules (logged to data/processed/data_quality_log.csv):
  1. Exact duplicate rows from double loads are removed.
  2. Marketplace codes are trimmed and upper-cased ("us " -> "US").
  3. Channel labels are mapped to the canonical list ("MAIL-IN" -> "Mail-in").
  4. Rows with negative return_units (sign errors) are excluded.
  5. Rows with missing transit/processing scans keep their volume, cost and disposition
     measures, but are excluded from the refund-cycle numerator AND denominator (cycle_units = 0).
Then runs sql/00_create_views.sql to create the reporting views.
"""
import sqlite3

import pandas as pd

from config import RAW, PROCESSED, DB_PATH, SQL_DIR

CANON_CHANNELS = {"MAIL-IN": "Mail-in", "DROP-OFF": "Drop-off", "CARRIER PICKUP": "Carrier Pickup", "RETURNLESS": "Returnless"}


def clean_returns(df):
    log = []
    n0 = len(df)
    df = df.drop_duplicates().copy()
    log.append(("returns_daily", "exact duplicate rows removed", n0 - len(df)))
    bad_m = (~df["marketplace"].isin(["US", "UK", "DE", "CA"])).sum()
    df["marketplace"] = df["marketplace"].str.strip().str.upper()
    log.append(("returns_daily", "marketplace codes trimmed/upper-cased", int(bad_m)))
    bad_c = (~df["channel"].isin(CANON_CHANNELS.values())).sum()
    df["channel"] = df["channel"].str.upper().map(CANON_CHANNELS)
    log.append(("returns_daily", "channel labels mapped to canonical names", int(bad_c)))
    # duplicates can re-appear once keys are normalised (dirty copy of a clean row)
    n1 = len(df)
    df = df.drop_duplicates()
    log.append(("returns_daily", "duplicates removed after key normalisation", n1 - len(df)))
    neg = df["return_units"] < 0
    log.append(("returns_daily", "rows with negative return_units excluded", int(neg.sum())))
    df = df[~neg].copy()
    miss = df["transit_hours"].isna() | df["processing_hours"].isna()
    log.append(("returns_daily", "rows with missing cycle scans excluded from cycle-time calc only", int(miss.sum())))
    df["cycle_units"] = df["return_units"].where(~miss, 0)
    df[["transit_hours", "processing_hours"]] = df[["transit_hours", "processing_hours"]].fillna(0.0)
    df["refund_cycle_hours"] = df["transit_hours"] + df["processing_hours"]
    # duplicate grain check after cleaning
    keys = ["date", "marketplace", "category", "channel"]
    dup_keys = df.duplicated(keys, keep=False).sum()
    log.append(("returns_daily", "remaining duplicate keys at daily grain (expect 0)", int(dup_keys)))
    return df, log


def main():
    PROCESSED.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    ret = pd.read_csv(RAW / "returns_daily.csv")
    ship = pd.read_csv(RAW / "shipments_daily.csv")
    ret, log = clean_returns(ret)
    con = sqlite3.connect(DB_PATH)
    ship.to_sql("shipments_daily", con, index=False)
    ret.to_sql("returns_daily", con, index=False)
    for name in ["kpi_targets", "initiatives", "milestones", "risks", "issues"]:
        t = pd.read_csv(RAW / f"{name}.csv", keep_default_na=False)
        # empty strings -> NULL for date / optional columns
        t = t.replace({"": None})
        t.to_sql(name, con, index=False)
        log.append((name, "rows loaded", len(t)))
    log.append(("returns_daily", "rows loaded after cleaning", len(ret)))
    log.append(("shipments_daily", "rows loaded", len(ship)))
    con.executescript((SQL_DIR / "00_create_views.sql").read_text(encoding="utf-8"))
    con.execute("CREATE INDEX ix_ret_date ON returns_daily(date)")
    con.execute("CREATE INDEX ix_ship_date ON shipments_daily(date)")
    con.commit()
    con.close()
    pd.DataFrame(log, columns=["table", "check", "rows"]).to_csv(PROCESSED / "data_quality_log.csv", index=False)
    print(f"build_db: {DB_PATH.name} built; {len(ret):,} clean return rows")


if __name__ == "__main__":
    main()
