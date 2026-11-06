"""Generate seeded synthetic returns data into data/raw/
(customers, orders, returns, refunds, carrier_scans).

Most customers are normal. Mixed in are serial returners, wardrobers,
empty-box / wrong-item returners, item-not-received (INR) rings that share
addresses, and instant refunds where the item never ships back. A few dirty
rows (duplicates, null reason codes, negative prices) are added on purpose so
the SQL cleaning step has something to fix.

All synthetic. None of it comes from Amazon or any employer.
"""
import numpy as np
import pandas as pd

from config import RAW, SEED, N_CUSTOMERS, ORDER_START, ORDER_END

rng = np.random.default_rng(SEED)
START = pd.Timestamp(ORDER_START)
END = pd.Timestamp(ORDER_END)
N_DAYS = (END - START).days + 1

SEGMENTS = ["normal", "serial_returner", "wardrober", "empty_box", "inr_ring", "no_ship"]
SEG_P = [0.935, 0.030, 0.015, 0.006, 0.006, 0.008]

CATS = ["Apparel", "Shoes", "Electronics", "Home & Kitchen", "Beauty", "Toys", "Books", "Sports"]
CAT_MEDIAN = dict(zip(CATS, [38, 68, 150, 42, 22, 30, 15, 48]))
CAT_SIGMA = dict(zip(CATS, [0.6, 0.5, 0.9, 0.7, 0.5, 0.6, 0.4, 0.7]))
CAT_RETURN_BASE = dict(zip(CATS, [0.22, 0.18, 0.10, 0.07, 0.035, 0.065, 0.025, 0.08]))
SEG_CAT_P = {
    "normal":          [0.22, 0.08, 0.12, 0.18, 0.10, 0.08, 0.10, 0.12],
    "serial_returner": [0.40, 0.15, 0.12, 0.10, 0.06, 0.05, 0.04, 0.08],
    "wardrober":       [0.42, 0.12, 0.30, 0.05, 0.03, 0.02, 0.02, 0.04],
    "empty_box":       [0.10, 0.05, 0.55, 0.12, 0.06, 0.05, 0.02, 0.05],
    "inr_ring":        [0.20, 0.10, 0.30, 0.15, 0.08, 0.07, 0.03, 0.07],
    "no_ship":         [0.25, 0.10, 0.30, 0.12, 0.06, 0.06, 0.04, 0.07],
}
SEG_ORDERS = {"normal": 11.7, "serial_returner": 30, "wardrober": 20,
              "empty_box": 15, "inr_ring": 15, "no_ship": 15}
# Monthly demand index Jan..Dec (Q4 peak, mid-year sales event)
MONTH_W = np.array([0.85, 0.80, 0.90, 0.92, 0.95, 0.98, 1.15, 0.97, 0.95, 1.02, 1.55, 1.75])
REGIONS = ["West", "Southwest", "Midwest", "Northeast", "Southeast"]


def make_customers():
    seg = rng.choice(SEGMENTS, N_CUSTOMERS, p=SEG_P)
    abuser = seg != "normal"
    in_window = rng.random(N_CUSTOMERS) < np.where(abuser, 0.45, 0.17)
    pre_days = np.minimum(rng.gamma(2.0, 520, N_CUSTOMERS), 3650).astype(int) + 1
    win_days = rng.integers(0, 640, N_CUSTOMERS)
    signup = np.where(in_window, START.value + win_days * 86400 * 10**9,
                      START.value - pre_days * 86400 * 10**9)
    signup = pd.to_datetime(signup).normalize()
    member_p = np.where(abuser, 0.72, 0.55)
    is_member = (rng.random(N_CUSTOMERS) < member_p).astype(int)
    pay = np.where(
        abuser,
        rng.choice(["credit_card", "debit_card", "gift_card", "bnpl"], N_CUSTOMERS, p=[0.35, 0.20, 0.25, 0.20]),
        rng.choice(["credit_card", "debit_card", "gift_card", "bnpl"], N_CUSTOMERS, p=[0.57, 0.26, 0.06, 0.11]),
    )
    cust_ids = np.array([f"C{i:05d}" for i in range(1, N_CUSTOMERS + 1)])
    address = np.array([f"AD{i:06d}" for i in range(1, N_CUSTOMERS + 1)], dtype=object)
    normal_idx = np.where(seg == "normal")[0]
    # ~4% of good customers share a household address with another good customer
    share = rng.choice(normal_idx, int(len(normal_idx) * 0.04), replace=False)
    address[share] = address[rng.choice(normal_idx, len(share))]
    # INR ring accounts concentrate on a small pool of drop addresses
    ring_idx = np.where(seg == "inr_ring")[0]
    pool = [f"AD9{i:05d}" for i in range(1, 31)]
    address[ring_idx] = rng.choice(pool, len(ring_idx))
    region = rng.choice(REGIONS, N_CUSTOMERS, p=[0.24, 0.14, 0.20, 0.20, 0.22])
    cust = pd.DataFrame({
        "customer_id": cust_ids,
        "signup_date": signup.strftime("%Y-%m-%d"),
        "region": region,
        "is_member": is_member,
        "payment_type": pay,
        "address_id": address,
    })
    return cust, seg


def make_orders(cust, seg):
    signup = pd.to_datetime(cust["signup_date"]).values
    first_day = np.maximum((signup - np.datetime64(START)).astype("timedelta64[D]").astype(int), 0)
    active_frac = (N_DAYS - first_day) / N_DAYS
    lam = np.array([SEG_ORDERS[s] for s in seg]) * active_frac * rng.lognormal(0, 0.45, len(seg))
    n_orders = rng.poisson(lam)
    n_orders = np.maximum(n_orders, (active_frac > 0.05).astype(int))  # every active customer orders once
    cust_idx = np.repeat(np.arange(len(cust)), n_orders)

    # Day-level demand weights over the 24-month window (seasonality + 1%/month growth)
    days = pd.date_range(START, END, freq="D")
    mon = np.asarray(days.month)
    mi = (np.asarray(days.year) - START.year) * 12 + mon - 1
    dw = MONTH_W[mon - 1] * (1 + 0.01 * mi)
    dw = dw * np.where(np.asarray(days.dayofweek) >= 5, 1.08, 1.0)
    cdf = np.cumsum(dw) / dw.sum()
    fd = first_day[cust_idx]
    lo = np.where(fd > 0, cdf[np.maximum(fd - 1, 0)], 0.0)  # orders start after signup
    u = lo + rng.random(len(cust_idx)) * (1 - lo)
    day_idx = np.minimum(np.searchsorted(cdf, u), N_DAYS - 1)
    order_date = days[day_idx]

    oseg = seg[cust_idx]
    cat = np.empty(len(cust_idx), dtype=object)
    for s in SEGMENTS:
        m = oseg == s
        cat[m] = rng.choice(CATS, m.sum(), p=SEG_CAT_P[s])
    med = np.array([CAT_MEDIAN[c] for c in cat])
    sig = np.array([CAT_SIGMA[c] for c in cat])
    price = rng.lognormal(np.log(med), sig)
    hv = (oseg == "wardrober") & np.isin(cat, ["Apparel", "Shoes", "Electronics"])
    price = np.where(hv, price * 1.8, price)
    price = np.round(np.clip(price, 3, 2500), 2)
    delivered = order_date + pd.to_timedelta(rng.integers(2, 7, len(cust_idx)), unit="D")

    orders = pd.DataFrame({
        "customer_id": cust["customer_id"].values[cust_idx],
        "order_date": order_date,
        "delivered_date": delivered,
        "category": cat,
        "item_price": price,
    }).sort_values(["order_date", "customer_id"]).reset_index(drop=True)
    order_seg = pd.Series(seg, index=cust["customer_id"]).loc[orders["customer_id"]].values
    orders.insert(0, "order_id", [f"O{i:07d}" for i in range(1, len(orders) + 1)])
    return orders, order_seg


def pick(options, probs, n):
    return rng.choice(options, n, p=probs)


def make_returns(cust, orders, oseg):
    n = len(orders)
    cat = orders["category"].values
    month = orders["order_date"].dt.month.values
    member = pd.Series(cust["is_member"].values, index=cust["customer_id"]).loc[orders["customer_id"]].values
    base = np.array([CAT_RETURN_BASE[c] for c in cat])
    season = np.select([month == 11, month == 12, month == 1], [1.15, 1.30, 1.10], 1.0)
    hv_cat = np.isin(cat, ["Apparel", "Shoes", "Electronics"])
    seg_mult = np.select(
        [oseg == "serial_returner", (oseg == "wardrober") & hv_cat, oseg == "wardrober",
         oseg == "empty_box", oseg == "no_ship"],
        [3.2, 2.6, 1.2, 1.6, 2.2], 1.0)
    p_ret = np.minimum(base * season * seg_mult * np.where(member == 1, 1.05, 1.0), 0.9)
    returned = rng.random(n) < p_ret

    # Item-not-received claims (no physical return), rings claim far more often
    p_inr = np.select([oseg == "inr_ring"], [0.20], 0.0035)
    inr = (~returned) & (rng.random(n) < p_inr)

    idx = np.where(returned | inr)[0]
    r = pd.DataFrame({
        "order_id": orders["order_id"].values[idx],
        "customer_id": orders["customer_id"].values[idx],
        "category": cat[idx],
        "item_price": orders["item_price"].values[idx],
        "delivered_date": orders["delivered_date"].values[idx],
        "seg": oseg[idx],
        "is_inr": inr[idx],
        "member": member[idx],
        "order_month": month[idx],
    }).reset_index(drop=True)
    m = len(r)
    apparel = r["category"].isin(["Apparel", "Shoes"]).values
    hv = r["category"].isin(["Apparel", "Shoes", "Electronics"]).values

    # Abuse flags at return level
    wardrobe_abuse = (r["seg"].values == "wardrober") & hv & (rng.random(m) < 0.75)
    emptybox_abuse = (r["seg"].values == "empty_box") & (rng.random(m) < 0.60)
    noship_abuse = (r["seg"].values == "no_ship") & (rng.random(m) < 0.60)

    # Reason codes
    reason = np.empty(m, dtype=object)
    norm_app = ["size_fit", "no_longer_needed", "defective", "damaged", "wrong_item"]
    norm_oth = ["no_longer_needed", "defective", "damaged", "wrong_item"]
    a = ~r["is_inr"].values & apparel
    reason[a] = pick(norm_app, [0.40, 0.30, 0.12, 0.10, 0.08], a.sum())
    b = ~r["is_inr"].values & ~apparel
    reason[b] = pick(norm_oth, [0.42, 0.26, 0.17, 0.15], b.sum())
    w = wardrobe_abuse
    reason[w & apparel] = pick(["size_fit", "no_longer_needed", "defective"], [0.35, 0.45, 0.20], (w & apparel).sum())
    reason[w & ~apparel] = pick(["no_longer_needed", "defective"], [0.55, 0.45], (w & ~apparel).sum())
    reason[emptybox_abuse] = pick(["defective", "damaged", "wrong_item"], [0.55, 0.30, 0.15], emptybox_abuse.sum())
    reason[r["is_inr"].values] = "item_not_received"

    # Request date
    gap = np.clip(rng.gamma(2.0, 5.0, m), 1, 30).round()
    gap = np.where(wardrobe_abuse, rng.integers(3, 15, m), gap)
    gap = np.where(r["is_inr"].values, rng.integers(1, 8, m), gap)
    request = pd.to_datetime(r["delivered_date"]) + pd.to_timedelta(gap, unit="D")

    # Instant refund (refund before receipt) under the current program
    p_inst = np.where(r["member"].values == 1, 0.70, 0.30)
    p_inst = np.where(noship_abuse, np.where(r["member"].values == 1, 0.97, 0.65), p_inst)
    p_inst = np.where(emptybox_abuse, 0.88, p_inst)
    instant = (rng.random(m) < p_inst) & ~r["is_inr"].values

    # Physical shipment outcome
    shipped = ~r["is_inr"].values & ~(noship_abuse & instant) & ~(noship_abuse & (rng.random(m) < 0.2))
    q4 = np.isin(pd.DatetimeIndex(request).month, [11, 12, 1])
    lost = shipped & (rng.random(m) < np.where(q4, 0.020, 0.012))
    accept_gap = rng.integers(0, 3, m)
    transit = np.round(rng.gamma(2.0, 2.5, m) + 2 + np.where(q4, 2, 0))
    received = shipped & ~lost
    received_date = pd.Series(request + pd.to_timedelta(accept_gap + transit, unit="D")).where(received)

    # Condition at grading
    cond = np.full(m, None, dtype=object)
    conds = ["new", "open_box", "used", "damaged", "empty_box", "wrong_item_returned"]
    dd = np.isin(reason, ["defective", "damaged"])
    serial = r["seg"].values == "serial_returner"
    g = received & dd
    cond[g] = pick(conds, [0.20, 0.35, 0.05, 0.398, 0.001, 0.001], g.sum())
    g = received & ~dd & ~serial
    cond[g] = pick(conds, [0.60, 0.32, 0.055, 0.022, 0.001, 0.002], g.sum())
    g = received & ~dd & serial
    cond[g] = pick(conds, [0.45, 0.46, 0.065, 0.022, 0.001, 0.002], g.sum())
    g = received & wardrobe_abuse
    cond[g] = pick(["used", "damaged", "open_box"], [0.80, 0.05, 0.15], g.sum())
    g = received & emptybox_abuse
    cond[g] = pick(["empty_box", "wrong_item_returned"], [0.55, 0.45], g.sum())

    # Refunds
    price = r["item_price"].values
    req = pd.Series(request)
    refund_date = pd.Series(pd.NaT, index=r.index, dtype="datetime64[ns]")
    refund_date[instant] = (req + pd.to_timedelta(rng.integers(0, 2, m), unit="D"))[instant]
    std_ok = ~instant & received & ~np.isin(cond, ["empty_box", "wrong_item_returned"])
    refund_date[std_ok] = (received_date + pd.to_timedelta(rng.integers(1, 4, m), unit="D"))[std_ok]
    carrier_claim = ~instant & lost
    refund_date[carrier_claim] = (req + pd.Timedelta(days=21))[carrier_claim]
    inr_mask = r["is_inr"].values
    inr_grant = inr_mask & (rng.random(m) < np.where(r["seg"].values == "inr_ring", 0.90, 0.95))
    refund_date[inr_grant] = (req + pd.to_timedelta(rng.integers(0, 3, m), unit="D"))[inr_grant]

    method = np.where(inr_mask, "none", pick(["drop_off", "carrier_pickup", "locker"], [0.62, 0.23, 0.15], m))

    returns = pd.DataFrame({
        "return_id": [f"R{i:06d}" for i in range(1, m + 1)],
        "order_id": r["order_id"],
        "customer_id": r["customer_id"],
        "return_request_date": pd.Series(request).dt.strftime("%Y-%m-%d").values,
        "reason_code": reason,
        "return_method": method,
    })
    has_refund = refund_date.notna().values
    refunds = pd.DataFrame({
        "return_id": returns["return_id"].values[has_refund],
        "refund_amount": price[has_refund],
        "refund_issued_date": refund_date[has_refund].dt.strftime("%Y-%m-%d").values,
        "instant_refund_flag": instant[has_refund].astype(int),
        "return_received_date": received_date[has_refund].dt.strftime("%Y-%m-%d").values,
        "condition_grade": cond[has_refund],
    })
    refunds.insert(0, "refund_id", [f"F{i:06d}" for i in range(1, len(refunds) + 1)])

    # Carrier scans for return shipments
    scans = []
    rid = returns["return_id"].values
    lbl = ~inr_mask
    scans.append(pd.DataFrame({"return_id": rid[lbl], "scan_event": "label_created",
                               "scan_date": req[lbl].values}))
    scans.append(pd.DataFrame({"return_id": rid[shipped], "scan_event": "carrier_accepted",
                               "scan_date": (req + pd.to_timedelta(accept_gap, unit="D"))[shipped].values}))
    mid = np.maximum(np.round(transit / 2), 1)
    scans.append(pd.DataFrame({"return_id": rid[shipped], "scan_event": "in_transit",
                               "scan_date": (req + pd.to_timedelta(accept_gap + mid, unit="D"))[shipped].values}))
    scans.append(pd.DataFrame({"return_id": rid[received], "scan_event": "delivered_to_warehouse",
                               "scan_date": received_date[received].values}))
    scans = pd.concat(scans).sort_values(["scan_date", "return_id"]).reset_index(drop=True)
    scans["scan_date"] = pd.to_datetime(scans["scan_date"]).dt.strftime("%Y-%m-%d")
    scans.insert(0, "scan_id", [f"S{i:07d}" for i in range(1, len(scans) + 1)])
    return returns, refunds, scans


def add_dirty_rows(orders, returns, refunds):
    returned_orders = set(returns["order_id"])
    clean_candidates = orders.index[~orders["order_id"].isin(returned_orders)]
    neg = rng.choice(clean_candidates, 45, replace=False)
    orders.loc[neg, "item_price"] = -orders.loc[neg, "item_price"]
    orders = pd.concat([orders, orders.sample(150, random_state=SEED)]).sort_values("order_id")
    null_idx = rng.choice(returns.index[returns["reason_code"] != "item_not_received"], 260, replace=False)
    returns.loc[null_idx, "reason_code"] = None
    returns = pd.concat([returns, returns.sample(60, random_state=SEED)]).sort_values("return_id")
    refunds = pd.concat([refunds, refunds.sample(40, random_state=SEED)]).sort_values("refund_id")
    return orders, returns, refunds


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    cust, seg = make_customers()
    orders, oseg = make_orders(cust, seg)
    returns, refunds, scans = make_returns(cust, orders, oseg)
    orders, returns, refunds = add_dirty_rows(orders, returns, refunds)
    for col in ["order_date", "delivered_date"]:
        orders[col] = pd.to_datetime(orders[col]).dt.strftime("%Y-%m-%d")
    cust.to_csv(RAW / "customers.csv", index=False)
    orders.to_csv(RAW / "orders.csv", index=False)
    returns.to_csv(RAW / "returns.csv", index=False)
    refunds.to_csv(RAW / "refunds.csv", index=False)
    scans.to_csv(RAW / "carrier_scans.csv", index=False)
    print(f"customers={len(cust):,} orders={len(orders):,} returns={len(returns):,} "
          f"refunds={len(refunds):,} scans={len(scans):,}")


if __name__ == "__main__":
    main()
