# Problem Statement & Solution — MPLAD Trace
### SIH 2026 · PS Code: SIH26102 · Theme: Blockchain & Cybersecurity · Sponsor: MoSPI

---

## The Problem

**Official PS title:** "Development of an AI-powered system to detect anomalies,
fraud, and inefficiencies in MPLAD Scheme implementation."

**In plain terms:** Every Member of Parliament in India is entitled to recommend
₹5 crore/year in local development spending — roads, water supply, health
centres, schools — executed through a chain of District Authorities and
Implementing Agencies. That chain has several handoff points where money can
leak: costs inflated above fair regional rates, projects certified complete
that were never properly finished, funds released before work is actually
done, and the same contractors winning suspiciously concentrated shares of
work in a constituency. Oversight today is largely manual — periodic audits,
RTI queries, CAG spot-checks — which is reactive and thin relative to the
volume of projects nationally.

**What's missing:** a system that continuously scores project-level risk,
explains *why* a project looks suspicious in plain language an investigator
can act on, and does this without requiring a human to manually cross-reference
cost baselines, timelines, and contractor histories by hand.

---

## What We're Building

**MPLAD Trace** — a two-layer risk intelligence platform:

1. **A macro layer** that ingests real public MPLAD fund-utilization statistics
   (state/district/MP-wise entitled, released, sanctioned, expended, unspent
   amounts — publicly available via data.gov.in / dataful.in) and flags MPs or
   districts whose utilization pattern deviates sharply from their peers —
   unusually low fund utilization, unusually high unspent balances, stalled
   project completion rates.

2. **A transaction-level detection engine** that scores individual projects
   (cost, timeline, contractor, location) for five specific fraud patterns:
   cost inflation, ghost/incomplete projects, payment-before-completion,
   contractor collusion clustering, and suspicious geographic clustering of
   awards. Because individual work-level records live behind login on the
   government's eSAKSHI portal and aren't publicly accessible to us as
   students, this layer is demonstrated on a synthetic dataset explicitly
   calibrated to match the real aggregate statistics from layer 1 — designed
   so it plugs directly into real eSAKSHI data with no architectural change
   if deployed by an actual implementing authority.

Every risk score ships with **specific, human-readable reasons** — never a
bare number — because an unexplained AI score is not actionable for an
investigator and not defensible in front of judges.

---

## How It Works

### Step 1 — Data ingestion (two tiers)
- Pull real public MPLADS aggregate datasets and load into Postgres.
- Generate/calibrate synthetic project-level records against those real
  statistics (realistic cost distributions per work category, realistic
  timelines, realistic fund-flow patterns) using PostGIS for proper
  geospatial storage.

### Step 2 — Feature engineering
For every project: cost-to-baseline ratio, completion-speed ratio, payment-gap
days (fund release vs. certified completion — negative is a strong red flag),
contractor's project count and constituency market-share, geographic award
density near the project (via PostGIS spatial queries), and sanction lag time.

### Step 3 — Hybrid detection
- **Isolation Forest** (unsupervised anomaly detection) scores each project
  against the engineered features — catches unusual combinations a fixed
  rule might miss.
- **Explicit rules layer** on top — hard-coded red flags (e.g. payment before
  completion, cost >80% over baseline, one contractor holding >40% of a
  constituency's projects) that are inherently explainable.
- **Combined risk score (0–100)**, blending both signals, plus a **reasons
  list** per project stating exactly which patterns triggered and by how much.

### Step 4 — Investigation interface
A dashboard ranks all projects by risk score. Clicking into a flagged project
shows the specific reasons with real numbers, a visual timeline highlighting
the anomalous gap, a cost-comparison chart against the regional baseline, and
a map showing nearby award clustering. A contractor view surfaces collusion
patterns — which contractors are over-represented in which constituencies —
as a browsable network, not just a spreadsheet.

### Step 5 — Validation
We evaluate detection quality against injected ground-truth labels in the
synthetic dataset (never fed to the model itself) — measuring precision at
the top 20% highest-risk projects and recall of known-anomalous projects,
so we can state actual detection performance numbers rather than just
"our AI catches fraud."

---

## Why This Approach

- **Explainability over black-box scoring** — government fraud investigation
  requires an audit trail, not a confidence percentage. This is the core
  differentiator from a generic "AI fraud detector."
- **Real data where real data exists** — the macro layer isn't synthetic
  window-dressing; it runs on actual published government statistics.
- **Honest about the synthetic layer's purpose** — framed as a calibrated
  demonstration of a detection engine designed for direct eSAKSHI integration,
  not a claim that we've analyzed real individual transactions.
- **Scales beyond MPLAD** — the same architecture (cost-baseline deviation +
  timeline anomalies + contractor concentration + geographic clustering)
  applies to any government disbursement scheme with a similar structure —
  PM-KISAN, NREGA works, scholarship disbursement — making this a platform
  pitch, not a single-scheme tool.
