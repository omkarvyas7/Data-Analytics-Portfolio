"""Run every numbered query in sql/ in order against data/returns.db.

Each file may contain setup statements (CREATE TABLE / INDEX) followed by a
final SELECT. Setup statements are executed; the final SELECT is saved to
data/processed/<file_stem>.csv.
"""
import sqlite3

import pandas as pd

import config as C
from config import DB_PATH, SQL_DIR, PROCESSED


def split_statements(sql: str):
    """Split a script into complete statements using sqlite3.complete_statement."""
    lines = [ln for ln in sql.splitlines() if not ln.strip().startswith("--")]
    stmts, buf = [], ""
    for ln in lines:
        buf += ln + "\n"
        if sqlite3.complete_statement(buf):
            if buf.strip().strip(";"):
                stmts.append(buf.strip())
            buf = ""
    if buf.strip():
        stmts.append(buf.strip())
    return stmts


def run_file(con, path):
    stmts = split_statements(path.read_text(encoding="utf-8"))
    *setup, final = stmts
    for s in setup:
        con.execute(s)
    con.commit()
    df = pd.read_sql_query(final, con)
    df.to_csv(PROCESSED / f"{path.stem}.csv", index=False)
    return df


def write_params(con):
    """One-row parameter table so every query reads the same assumptions as config.py."""
    params = pd.DataFrame([{
        "scoring_cutoff": C.SCORING_CUTOFF,
        "extract_date": C.EXTRACT_DATE,
        "bad_debt_days": C.BAD_DEBT_DAYS,
        "high_value_threshold": C.HIGH_VALUE_THRESHOLD,
        "restock_fee_rate": C.RESTOCK_FEE_RATE,
        "repeat_returns_90d": C.REPEAT_RETURNS_90D,
        "inr_deny_rate": C.INR_DENY_RATE,
        "tier_high_cutoff": C.TIER_HIGH_CUTOFF,
        "tier_med_cutoff": C.TIER_MED_CUTOFF,
    }])
    params.to_sql("params", con, if_exists="replace", index=False)


def main():
    PROCESSED.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    write_params(con)
    for path in sorted(SQL_DIR.glob("[0-9][0-9]_*.sql")):
        df = run_file(con, path)
        print(f"{path.name}: {len(df):,} rows -> data/processed/{path.stem}.csv")
    con.close()


if __name__ == "__main__":
    main()
