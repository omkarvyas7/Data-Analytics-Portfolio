# SIPOC: Returns Grading and Disposition

Data is synthetic. The process starts when a unit arrives at the returns center dock and ends when its disposition is assigned and the unit is routed.

| Suppliers | Inputs | Process | Outputs | Customers |
|---|---|---|---|---|
| Customers returning items | Returned unit, return reason | 1. Dock receipt and unload | Unit scanned in, dock timestamp | Returns Operations |
| Carriers / linehaul | Trailer, ASN / return label data | 2. Triage and receive scan | Unit matched to order, category, price | Finance (refund / recovery) |
| Returns associates (graders) | Grading SOP, checklist, photo station | 3. Queue to grading station | Grade (condition) and photos | ReCommerce resale channels (new, open-box, refurbished) |
| QA auditors | Audit sample, defect cause codes | 4. Grade condition and test function | Assigned disposition code | Liquidation and recycling partners |
| Learning & Development | Training curriculum, new-hire onboarding | 5. Assign disposition and route to pallet | Recovery value achieved, waste flag | Resale customers (buyers) |
| Engineering (grading tool / WMS) | Grading UI, disposition rules | 6. QA audit (sample) | Audit result, defect cause | Sustainability / zero-waste program |

## Process steps (high level)

1. Dock receipt and unload
2. Triage and receive scan (value-added)
3. Queue to grading (waiting)
4. Grade condition, test function, capture photos (value-added)
5. Assign disposition and route to resale / refurb / liquidate / recycle / destroy
6. QA audit of a random sample, with a defect cause coded when the disposition is wrong

## Key metrics at each boundary

- Input: units received per day vs site capacity (backlog index), share of units handled by associates with tenure < 30 days
- Process: queue hours, grading hours, photo step completion, checklist completion (new field)
- Output: disposition defect rate, DPMO, first-pass yield, recovery rate, waste units, complaint rate
