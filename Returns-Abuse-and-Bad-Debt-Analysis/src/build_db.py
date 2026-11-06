"""Load raw CSVs into a local SQLite database (data/returns.db)."""
import sqlite3

import pandas as pd

from config import RAW, DB_PATH

TABLES = ["customers", "orders", "returns", "refunds", "carrier_scans"]


def main():
    if DB_PATH.exists():
        DB_PATH.unlink()
    con = sqlite3.connect(DB_PATH)
    for t in TABLES:
        df = pd.read_csv(RAW / f"{t}.csv")
        df.to_sql(t, con, index=False)
        print(f"loaded {t}: {len(df):,} rows")
    # Lookup indexes on raw keys (raw tables keep duplicates, so no unique keys)
    con.executescript("""
        CREATE INDEX ix_orders_id ON orders(order_id);
        CREATE INDEX ix_returns_id ON returns(return_id);
        CREATE INDEX ix_returns_order ON returns(order_id);
        CREATE INDEX ix_refunds_return ON refunds(return_id);
        CREATE INDEX ix_customers_id ON customers(customer_id);
        CREATE INDEX ix_scans_return ON carrier_scans(return_id);
    """)
    con.close()


if __name__ == "__main__":
    main()
