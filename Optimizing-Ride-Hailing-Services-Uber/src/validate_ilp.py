"""Check that linear_sum_assignment matches the notebook's cvxpy 0-1 integer program.

Re-draws the first K windows with the same seed, solves the batched protocols both ways and
asserts the same match count and total ETA / contribution. Skipped if cvxpy is missing.
"""
import numpy as np

import simulate as sim

K = 25


def ilp(score, feasible, maximize):
    import cvxpy as cp
    n_r, n_d = score.shape
    x = cp.Variable((n_r, n_d), boolean=True)
    m = 1_000.0  # big weight so the solver maximises match count first
    obj = cp.sum(cp.multiply(x, score))
    objective = cp.Maximize(obj + m * cp.sum(x)) if maximize else cp.Minimize(obj - m * cp.sum(x))
    cons = [cp.sum(x, axis=1) <= 1, cp.sum(x, axis=0) <= 1, x[~feasible] == 0] if (~feasible).any() \
        else [cp.sum(x, axis=1) <= 1, cp.sum(x, axis=0) <= 1]
    cp.Problem(objective, cons).solve()
    sel = np.round(x.value).astype(bool)
    return int(sel.sum()), float(score[sel].sum())


def main():
    try:
        import cvxpy  # noqa: F401
    except ImportError:
        print("cvxpy not installed, skipping the ILP cross-check")
        return
    rng = np.random.default_rng(sim.SEED)
    for wid in range(1, K + 1):
        w = sim.make_window(rng, wid)
        ok = np.ones_like(w["dist"], dtype=bool)
        in_mdr = w["dist"] <= w["mdr_miles"]
        cases = [(w["eta"], ok, False), (w["eta"], in_mdr, False),
                 (w["contrib"], in_mdr & (w["contrib"] > 0), True)]
        for score, feas, mx in cases:
            pairs = sim.batched(score, feas, mx)
            lsa = (len(pairs), float(sum(score[r, c] for r, c in pairs)))
            ip = ilp(score, feas, mx)
            assert lsa[0] == ip[0] and abs(lsa[1] - ip[1]) < 1e-4, (wid, lsa, ip)
    print(f"ILP cross-check passed: {K} windows x 3 batched protocols identical to cvxpy")


if __name__ == "__main__":
    main()
