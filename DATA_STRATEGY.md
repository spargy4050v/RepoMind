# Data Strategy — MPLAD Trace

## What real MPLAD data looks like today

MPLAD funds now flow through the **eSAKSHI portal** (live since April 1, 2023).
MPs, District Authorities (NDA/IDA), State Nodal Authorities, and Implementing
Agencies interact with it directly. This matters for us:

- **Individual work-level records** (exact contractor, exact GPS location, exact
  per-project cost, exact dates) are **behind login**, tied to the specific MP/
  district/agency involved. Not publicly scrapeable.
- **Aggregate/rollup statistics** ARE public, via data.gov.in and dataful.in:
  state-wise, district-wise, MP-wise, year-wise totals for funds entitled,
  released, sanctioned, expended, and unspent, plus counts of works recommended/
  sanctioned/completed.

## Why this shapes our architecture (two-tier)

**Tier 1 — Real data, macro-level.** We ingest the actual public aggregate
datasets (state/MP/district/year fund totals) and compute derived ratios —
utilization ratio (expended/sanctioned), unspent ratio (unspent/entitled),
completion ratio — directly from real numbers. An MP or district whose ratios
sit far outside their state peer group is a genuine, defensible anomaly signal
built entirely on real government data. **This is not synthetic — say so
explicitly when presenting.**

**Tier 2 — Synthetic data, transaction-level.** The detailed fraud story
(cost inflation, ghost projects, contractor collusion, payment timing,
geo-clustering) needs work-level granularity that isn't publicly available.
We generate synthetic project records **calibrated against Tier 1's real
statistics** (realistic cost ranges, realistic timelines, realistic fund flow
patterns) to demonstrate the transaction-level detection engine.

## How to frame this to judges (be upfront, not defensive)
"Our platform has two layers: a macro layer running on real, live government
data today, and a transaction-level detection engine demonstrated on a
synthetic dataset calibrated to match real statistical patterns — because
individual work records require implementer-level portal access we don't have
as students. If deployed by MoSPI/a district authority, the transaction engine
plugs directly into eSAKSHI's actual work-level records with no architecture
change." This is honest, and it's also literally correct: government pilots
work exactly this way (build/validate on synthetic or sandboxed data, deploy
against production once access is granted).

## Why Postgres + PostGIS (not SQLite)
1. Real MPLAD data is genuinely hierarchical/relational (state → district →
   constituency → MP → work → implementing agency → contractor) — a proper
   relational schema, not flat files.
2. Two data tiers (aggregate real + synthetic transactional) are naturally
   related table sets, not two disconnected CSVs.
3. PostGIS gives real spatial indexing (`ST_DWithin`, `ST_ClusterDBSCAN`) for
   the geo-clustering anomaly feature — genuine geographic analysis instead
   of a lat/lon-rounding approximation in pandas. This is a materially
   stronger technical answer if a judge asks how the geo-clustering detection
   actually works.

See `backend/schema.sql` for the full schema.

## Data sources to actually pull for Tier 1
- data.gov.in — search "MPLADS"
- dataful.in — MPLADS collection (state-wise fund summaries, 16th/17th Lok
  Sabha work-recommendation datasets, year/state/district/MP-wise entitled-
  released-sanctioned-unspent data)
- MPLADS eSAKSHI dashboard (mplads.mospi.gov.in) — public dashboard view,
  useful for cross-checking numbers even where bulk download isn't available
