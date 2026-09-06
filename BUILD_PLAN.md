# MPLAD Trace — Full Build Plan
### SIH26102: AI-Powered Fraud/Anomaly Detection for MPLAD Scheme Implementation

This document is the team's build bible. Each module has: what it does, why it exists,
exactly what to prompt Antigravity for, what files come out of it, and a test checklist
that must pass before moving to the next module. Don't skip the test checklist — a module
that "looks done" but isn't tested is technical debt that breaks the module built on top of it.

---

## 0. Tech Stack (locked — don't deviate mid-build)

| Layer | Choice | Why |
|---|---|---|
| Data generation & ML | Python (pandas, scikit-learn) | Isolation Forest, feature engineering — standard, well-documented, Antigravity handles this pattern reliably |
| Backend API | FastAPI (Python) | Same language as the ML layer, no context-switch, auto-generates OpenAPI docs for free |
| Frontend | React + Vite + Tailwind | Fast dev loop, component ecosystem for tables/charts/maps |
| Charts/Maps | Recharts (charts), Leaflet (geo map) | Free, no API keys needed, works offline |
| Database | SQLite → Postgres later if needed | Zero setup for now; 3000 rows doesn't need more |

**Repo structure:**
```
mplad-trace/
  data/              # Module 1
  backend/
    ml/              # Module 2 (scoring engine)
    api/             # Module 3 (FastAPI app)
  frontend/          # Module 4
  tests/             # cross-cutting test scripts
  BUILD_PLAN.md      # this file
```

---

## Phase 1 — Data & Intelligence Core
*Goal: prove the detection logic actually works before building anything around it.*

### Module 1: Synthetic Dataset — ✅ DONE
**Output:** `data/generate_dataset.py`, `mplad_projects.csv/json` (3000 projects, 5 embedded fraud patterns: cost_inflation, ghost_project, contractor_collusion, payment_timing, geo_clustering)

**Test checklist:**
- [x] Script runs without error, produces exactly `n` rows
- [x] Ground-truth anomaly rate is 15-20% (tunable down later)
- [x] Spot-check 3 anomalous rows manually — does the injected pattern actually look wrong to a human? (e.g. cost_inflation row should be visibly 2-3x baseline)
- [x] Spot-check 3 normal rows — do they look plausible with no red flags?

*(If your team regenerates this file, always keep `_ground_truth_*` fields — they're needed for Module 2's evaluation, and must be dropped before the detector ever sees the data as input.)*

---

### Module 2: Feature Engineering
**Goal:** turn raw project rows into the numeric signals the detector actually reasons over.

**What to build:** `backend/ml/features.py`

Features per project (compute all of these):
1. `cost_ratio` = sanctioned_cost / regional_baseline_cost
2. `completion_speed_ratio` = actual_duration_days / planned_duration_days
3. `payment_gap_days` = (fund_release_date − completion_certified_date).days — **negative = paid before completion, the strongest single red flag**
4. `contractor_project_count` = how many projects this contractor holds nationally
5. `contractor_constituency_share` = this contractor's % share of projects within this specific constituency (collusion signal)
6. `geo_cluster_density` = count of other projects within ~2km of this one (rounded lat/lon bucket is fine for v1)
7. `sanction_lag_days` = (sanction_date − recommended_date).days

**Antigravity prompt guidance:**
> "Write a Python module `features.py` that loads `mplad_projects.csv`, computes the 7 features listed [paste list], and returns a pandas DataFrame with `project_id` + all engineered features. Drop any `_ground_truth_*` columns from the feature set — keep them in a separate DataFrame for evaluation only. Add docstrings explaining what each feature detects."

**Test checklist:**
- [ ] Run on the full dataset, no NaNs/infs in output (watch division-by-zero on `cost_ratio` if baseline is ever 0)
- [ ] Manually verify feature values on the same anomalous rows you spot-checked in Module 1 — do the numbers actually look extreme for those rows? (e.g. `cost_ratio` should be >1.8 for cost_inflation rows)
- [ ] Manually verify a few normal rows have unremarkable feature values

---

### Module 3: Anomaly Scoring Engine
**Goal:** the actual detector — Isolation Forest + rules layer, producing a 0-100 risk score and a list of plain-English reasons per project.

**What to build:** `backend/ml/scorer.py`

**Design (understand this before prompting — you'll be asked to explain it):**
- **Isolation Forest** on the 7 engineered features → raw anomaly score per project (sklearn gives this natively via `decision_function`)
- **Rules layer** on top — hard flags that don't need ML, e.g.:
  - `payment_gap_days < 0` → flag "Payment released before completion"
  - `cost_ratio > 1.8` → flag "Cost exceeds regional baseline by >80%"
  - `contractor_constituency_share > 0.4` → flag "Single contractor holds >40% of constituency's projects"
- **Combined risk score** = weighted blend of normalized Isolation Forest score + count/severity of triggered rules → scaled to 0-100
- **Reasons list** — for every project, output the specific triggered rules/features in human language, NOT just a number. This is the whole differentiator vs. a black-box score.

**Antigravity prompt guidance:**
> "Write `scorer.py` that: (1) trains an sklearn IsolationForest on the features from `features.py` (contamination=0.15), (2) implements the 3 rules above as separate functions each returning a boolean + a human-readable reason string, (3) combines the IF anomaly score (normalized 0-100) with rule flags into a final `risk_score` (0-100) using [pick a simple weighting: e.g. 60% IF score + up to 40% from rule flags], (4) returns a DataFrame with `project_id, risk_score, reasons (list of strings), top_anomaly_type (best guess label)`. Include a `if __name__ == '__main__'` block that runs it end to end and prints the top 10 highest-risk projects."

**Test checklist — this is the most important test in the whole build:**
- [ ] Run against ground truth: what % of the top 20% highest-scored projects are actually `_ground_truth_is_anomalous == True`? (This is your precision-at-top-K — aim for >70%. If it's near 20% baseline rate, the model isn't finding real signal, debug feature engineering first.)
- [ ] Check recall: of all ground-truth anomalous projects, what % scored above some threshold (e.g. 60)? Aim for >60%.
- [ ] Manually read the `reasons` output for 5 known-anomalous projects — do the reasons make sense and match the injected pattern?
- [ ] Manually read `reasons` for 5 known-normal projects that got a high score anyway (false positives) — are they at least *plausible* false positives, not nonsense?
- [ ] **Team review:** every team member should be able to explain, in their own words, what Isolation Forest does and why each rule exists. If you can't, don't move on — go re-read the sklearn docs / ask Antigravity to explain the code back to you line by line.

*Do not proceed to Module 4 until precision-at-top-20% is comfortably above the 19% baseline rate. This is the core IP of the whole project — get it right before building UI on top of a broken detector.*

---

## Phase 2 — Backend API

### Module 4: FastAPI Service
**Goal:** expose the scored data over HTTP so the frontend can consume it.

**What to build:** `backend/api/main.py` + supporting route files

**Endpoints needed:**
- `GET /projects` — paginated list, sortable by risk_score, filterable by state/constituency/work_category/contractor
- `GET /projects/{project_id}` — full detail: all fields + risk_score + reasons
- `GET /contractors/{contractor_id}` — contractor's full project history + aggregate risk stats (for the collusion-cluster view)
- `GET /stats/summary` — dashboard header numbers: total projects, total flagged, total sanctioned amount, avg risk score
- `POST /projects/rescan` — re-run the scoring pipeline (nice for a live demo moment: "watch it rescore in real time")

**Antigravity prompt guidance:**
> "Build a FastAPI app with these endpoints [paste list]. Load the scored dataset from `scorer.py`'s output at startup into memory (pandas DataFrame is fine for 3000 rows, no need for a real DB yet). Use Pydantic models for response schemas. Enable CORS for `localhost:5173` (Vite's default dev port)."

**Test checklist:**
- [ ] `uvicorn main:app --reload` starts with no errors
- [ ] Hit every endpoint via the auto-generated `/docs` (Swagger UI) — confirm each returns sane JSON
- [ ] Test pagination actually paginates (don't just return everything and ignore the params)
- [ ] Test at least one filter combination (e.g. `?state=Telangana&min_risk=70`)
- [ ] Confirm CORS works by hitting the API from a simple browser fetch() before frontend exists

---

## Phase 3 — Frontend (this is where "proper UI" happens)

### Module 5: Dashboard Shell + Project List
**Goal:** the main screen — sortable, filterable, risk-colored project table.

**What to build:** `frontend/src/` — React app scaffolded with Vite

**UI requirements (be specific with Antigravity, don't let it default to a generic admin template):**
- Top summary bar: total projects, total flagged (risk > 60), total sanctioned amount, avg risk score — 4 stat cards
- Main table: project_id, constituency, work category, contractor, cost, risk score (as a colored badge: green <40, amber 40-70, red >70), click row → detail view
- Filter sidebar/bar: state, work category, risk range slider, contractor search
- Sort by risk score (default: highest first) — this IS the product; a fraud dashboard that doesn't default-sort by risk is a UX failure
- Color system: use risk-tier colors consistently everywhere (not just the table) — this is what makes it feel like a real product, not a spreadsheet with a logo

**Antigravity prompt guidance:**
> "Scaffold a Vite + React + Tailwind app. Build a dashboard page with [paste UI requirements above]. Fetch data from the FastAPI backend at `http://localhost:8000`. Use a clean, high-density data-table style suited for government/analyst tooling — not a consumer app aesthetic. Reference: think Linear/Retool table density, not a marketing landing page."

**Test checklist:**
- [ ] Table loads real data from the backend, not mock data
- [ ] Sorting by risk score actually re-sorts (check network tab or client-side sort logic)
- [ ] All filters actually filter (test each one individually)
- [ ] Color coding is consistent and matches the risk tiers used in Module 3's scoring
- [ ] Test on a smaller screen — does the table degrade gracefully or just break?

---

### Module 6: Project Detail View — the "why" screen
**Goal:** this is the single most important screen for judges. It has to make the risk score feel earned, not arbitrary.

**UI requirements:**
- Header: project ID, constituency, contractor, risk score as a large colored badge
- **Reasons panel** — each triggered reason as its own card/row with an icon (not a wall of text): e.g. "⚠️ Cost 2.8x regional baseline (₹1.12Cr vs ₹40L expected)" — always show the actual numbers, not just the label
- Timeline visualization: recommended → sanctioned → started → completed → fund released, as a horizontal timeline, with the anomalous gap (if any) visually highlighted in red
- Cost comparison bar chart: this project vs. regional baseline vs. average for that work category
- Small map (Leaflet) showing this project's location + any nearby clustered projects
- "Similar flagged projects by this contractor" list at the bottom, linking to their detail pages

**Antigravity prompt guidance:**
> "Build a project detail page at route `/projects/:id`. [paste UI requirements]. The reasons panel is the most important element — make each reason visually scannable in under 2 seconds, with the specific numbers bolded."

**Test checklist:**
- [ ] Open 5 different projects (mix of high and low risk) — does the page make sense for both, or does it look broken for a low-risk project with zero reasons? (Design an empty/good state: "No anomalies detected" clearly shown)
- [ ] Timeline correctly highlights the actual anomalous gap when present
- [ ] Map renders correct coordinates, doesn't crash on load
- [ ] **Show this screen to someone outside the team who hasn't seen the project** — can they understand why a project is flagged within 10 seconds, with zero explanation from you? If not, simplify the reasons panel.

---

### Module 7: Contractor Cluster View
**Goal:** the collusion-detection story — this is what makes judges go "oh, that's clever" instead of "ok, another fraud dashboard."

**UI requirements:**
- Network/cluster graph: contractors as nodes, constituencies as nodes, edges = project relationships, sized/colored by risk concentration
- Simplest viable version: a table of contractors sorted by `constituency_share` + `project_count`, with a "view network" toggle that shows a simple force-directed graph (use a lightweight library — `react-force-graph` or similar)
- Click a contractor → their full project list + aggregate stats

**Antigravity prompt guidance:**
> "Build a contractor cluster page. Start with the simpler table view first, get that tested and working, THEN add the graph visualization as an enhancement — don't build the graph first, it's higher risk and lower priority than the table."

**Test checklist:**
- [ ] Table view works standalone even if the graph view has bugs (build in this order deliberately)
- [ ] Graph renders without crashing on the full dataset (test performance — force-directed graphs can choke on too many nodes; consider limiting to top 30 highest-risk contractors)
- [ ] Clicking a node/row actually navigates to the right contractor detail

---

## Phase 4 — Integration & Demo Prep

### Module 8: End-to-End Test Pass
**Goal:** the whole pipeline, data → scoring → API → UI, works as one system, not four disconnected pieces.

**Test checklist:**
- [ ] Fresh clone/setup from scratch on a teammate's machine — does the README (write one!) actually get someone from zero to running app?
- [ ] Full user journey: land on dashboard → sort by risk → click top project → read reasons → click contractor → see their cluster → back to dashboard. No dead ends, no console errors.
- [ ] Rescan endpoint (if built) actually updates the UI when triggered
- [ ] Load test: does the table/graph stay responsive with all 3000 rows, or do you need pagination tightened?

### Module 9: The "Live Flag" Demo Moment
**Goal:** a scripted, reliable demo moment for judges — don't leave this improvised.

**What to build:** a seeded "new project" you can submit live during the pitch that triggers a specific known anomaly (e.g. an obviously cost-inflated project), showing the system flag it in real time with the reasons panel populating.

**Test checklist:**
- [ ] Run this exact demo sequence 5 times in a row without failure before presenting to judges
- [ ] Have a fallback: a pre-recorded screen capture of this exact flow, in case live demo/wifi fails at the venue

### Module 10: Pitch Deck Alignment
- [ ] Every claim in the deck ("catches contractor collusion", "explainable AI") has a corresponding screen the team can pull up live if a judge asks "show me"
- [ ] Team can answer: why Isolation Forest and not a different method? What's your false positive rate? How would this scale beyond MPLAD to other DBT schemes? What happens with real (not synthetic) data — do you expect performance to change?

---

## Suggested Team Split (adjust to your actual team of 6)
- **2 people:** Modules 2-3 (feature engineering + scoring engine) — needs the most conceptual understanding, keep this pair stable throughout
- **1-2 people:** Module 4 (backend API)
- **2-3 people:** Modules 5-7 (frontend/UI) — can parallelize once Module 4's API contract is defined (agree on the endpoint shapes early so frontend isn't blocked waiting on backend)

## Golden Rule
**Do not start a module until the previous module's test checklist is fully checked off.** A pretty UI on top of a broken detector, or a detector nobody on the team can explain, is what loses at Q&A even with working code.
