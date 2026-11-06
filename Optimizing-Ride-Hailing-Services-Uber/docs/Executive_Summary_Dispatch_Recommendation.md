# Executive Summary: Moving from First-Dispatch to Batched Dispatch

For: Rider Operations leadership, Marketplace Program Manager, Finance partner, Dispatch engineering lead
Basis: Monte Carlo simulation of 1,000 seeded batching windows (14,795 rider requests). All data is synthetic. None of it comes from Uber or any employer.

## Recommendation

Replace greedy first-dispatch with batched assignment that minimizes total rider ETA, cap the dispatch radius at 3 miles, and roll the change out through a zone-level pilot tracked on the Dispatch Performance Dashboard. In the simulation this cuts average rider ETA by 23.7% with no change in match rate. With the radius in place it also serves 3.98 percentage points more riders and adds 5.96% modelled contribution.

## The problem with first-dispatch

- Greedy first-dispatch gives each request the nearest open driver in arrival order. Early requests take drivers that later requests needed, and the tail grows: 10.49% of matched riders wait 12+ minutes, and the average window p90 ETA is 11.72 minutes.
- On the same riders and drivers, greedy dispatch costs 82.12 unpaid en-route minutes per window. Batching costs 62.66.
- Once a dispatch radius is enforced, greedy dispatch strands riders it could have served. Its match rate is 73.33%, against 77.31% for batching.

## Results

| KPI | Greedy first-dispatch | Batched min-ETA | Change |
|---|---|---|---|
| Avg rider ETA (min), no radius | 6.49 | 4.95 | -23.69% |
| Avg window p90 ETA (min), no radius | 11.72 | 7.91 | -32.53% |
| Riders waiting 12+ min, no radius | 10.49% | 2.05% | -8.44 pp |
| Match rate, 1.5-4 mile radius | 73.33% | 77.31% | +3.98 pp |
| Avg rider ETA (min), with radius | 4.85 | 4.52 | -6.72% |
| Contribution per window, with radius | $122.01 | $129.28 | +5.96% |

- The gain is largest when drivers are scarce. In under-supplied windows (fewer than 0.8 drivers per rider, 310 windows) batching cuts ETA by 43.06% (3.81 minutes per rider). In over-supplied windows (360 windows) the gain is 9.60% (0.47 minutes).
- The radius is the main trade-off. At 3 miles batching keeps a 84.54% match rate, close to 86.35% with no radius, at 4.89 minutes average ETA. At 1.5 miles the match rate falls to 64.25%.
- Maximizing contribution instead of minimizing ETA adds 12.01% contribution over greedy (radius enforced), but average ETA rises 3.66% versus greedy. That is why it is not the default.

## Risks and how the dashboard catches them

The gap analysis flags 506 of 1,000 windows where batching looks worse on at least one KPI. None of them (0) is a true ETA regression on the same riders. In 255 windows average ETA is higher only because batching served extra riders who would otherwise go unmatched. 85 have a longer p90 tail with a better average, and 166 earn less contribution because the objective ignores fare. The dashboard labels each flag by cause, so operations can tell these apart from a real regression before deciding to roll back.

## Proposed plan

1. Weeks 1-2: agree KPI definitions and guardrails (avg ETA, p90 ETA, match rate, unmatched riders, share of drivers matched, contribution) with Finance and Dispatch engineering.
2. Weeks 3-6: switch-back pilot in a set of zones, comparing batched min-ETA with a 3-mile radius against current first-dispatch. Review the dashboard daily.
3. Week 7: go or no-go. Go if p90 ETA improves, match rate does not drop, and no zone shows a true regression for 3 consecutive days.
4. After launch: test a contribution-weighted objective, but only in zones where ETA is already within target.

## Assumptions and limits

- 6 x 6 mile zone, 18 mph average speed, lognormal traffic noise, about 15 requests per window, design supply ratios of 0.6 to 1.5 drivers per rider, radius drawn from 1.5, 2, 3 and 4 miles.
- Contribution is fare (base $2.50 + $1.25 per trip mile + $0.30 per trip minute) minus $0.65 per unpaid en-route mile. It is a model input, not a P&L figure.
- Unmatched riders do not carry into the next window, and driver repositioning and cancellations are not modelled. These figures need a field pilot before they are used for planning.
