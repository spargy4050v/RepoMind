# SIH Presentation and Live Demonstration Plan

## Communication objective

By the end, SIH judges should see MPLAD Trace as a credible, locally runnable
investigation workflow that prioritises MPLAD projects for review with
traceable evidence, while honestly distinguishing real public aggregate context
from the calibrated synthetic work-level demonstration.

## Recommended format

Use an eight-minute presentation followed by a four-minute judge interaction.
If the slot is shorter, preserve slides 1, 2, 4, 6, 8, and 10 and run the
two-minute demonstration only. Never sacrifice the data-provenance disclosure
or the explanation view to fit the time.

## Narrative arc

1. Oversight teams cannot manually connect cost, timeline, contractor, and
   spatial evidence across a large project portfolio.
2. MPLAD Trace converts those signals into a prioritised review queue.
3. The score is useful because it is always accompanied by concrete reasons,
   not because it is labelled AI.
4. The system has been evaluated honestly and is ready for an authorised-data
   pilot path.

## Slide-by-slide plan

| # | Time | Takeaway title | On-slide content | Presenter emphasis |
|---|---:|---|---|---|
| 1 | 0:00-0:25 | **MPLAD Trace makes project-risk review explainable** | Product name, SIH 2026 / SIH26102, one-line value proposition: “Prioritise projects for review with evidence an investigator can act on.” | State that the product produces review signals, never a fraud verdict. |
| 2 | 0:25-1:05 | **Manual oversight misses patterns spread across the portfolio** | A simple project journey: recommendation → sanction → execution → completion → release. Highlight inflated cost, impossible timing, contractor concentration, and location clustering. | Describe the investigator’s practical problem: signals live in separate fields and are hard to compare at portfolio scale. |
| 3 | 1:05-1:35 | **We use real aggregates honestly and demonstrate project intelligence transparently** | Two columns: Tier 1 = real public aggregate MPLAD summaries; Tier 2 = calibrated synthetic project records. Add “evaluation-only labels never enter scoring.” | Granular implementation records need authorised access; the architecture can ingest them later without changing the scoring workflow. |
| 4 | 1:35-2:20 | **Seven evidence signals turn raw records into a review priority** | Project data → seven features → Isolation Forest + explicit rules → 0–100 score + reasons. Group the features into cost/timeline and contractor/geography. | The model finds unusual combinations; rules ensure investigators see why. |
| 5 | 2:20-2:55 | **Every score tells the reviewer what to examine** | One representative project with score, tier, and 2–3 coded reasons: cost exceeds baseline, payment precedes completion, or contractor concentration. | A score without evidence is not operationally useful. Do not call the example an actual fraud case. |
| 6 | 2:55-3:30 | **The project has measurable detection quality and production-aware geography** | Top-20% precision 79.17%; recall 83.33%. Footnote: labels are held out and used only after scoring. Add PostGIS geography / `ST_DWithin`. | Roughly four of five records in the highest-priority review queue are known injected anomalies in the evaluation dataset. |
| 7 | 3:30-4:00 | **The platform supports review, not just detection** | Product overview: prioritised register, project analysis, detection-logic simulator, investigation alerts, and upload-file review. | Transition: “Now I’ll follow one reviewer’s journey.” |
| 8 | 4:00-6:00 | **Live: from portfolio alert to explainable investigation** | Keep the slide minimal: “Live demonstration.” | Run the primary demo below. Avoid reading UI text verbatim. |
| 9 | 6:00-6:45 | **A controlled pilot can connect authorised records without changing the core workflow** | Authorised source → Postgres/PostGIS → same seven-feature scorer → reviewer feedback / audit trail. Include local-first, no paid API dependency. | This is a deployment path, not a claim of current government integration. |
| 10 | 6:45-8:00 | **Fund the review workflow, not a black-box verdict** | Explainable evidence, honest data provenance, local deployability; end with the pilot ask. | Stop after the ask; hold the project-evidence view for questions. |

## Demo script: two-minute primary path

### Before opening the dashboard

1. Start the API and dashboard locally, sign in, and confirm the browser is
   already on the Risk Intelligence overview.
2. Keep one known high-risk project ready in the ranked list and keep the
   browser zoom at 100%.
3. Do not use a project whose reasons are vague or only model-based. Select a
   record with at least two specific rule-backed reasons.

### Spoken flow and screen actions

| Time | Screen action | What to say |
|---|---|---|
| 0:00-0:20 | Open **Overview**. | “A reviewer starts with the portfolio: the queue separates high, review, and low-risk projects. These are calibrated synthetic project records for the demonstration.” |
| 0:20-0:45 | Open **Projects** and select a high-risk record. | “The reviewer does not investigate all projects equally. They open the highest-priority case with the underlying project context.” |
| 0:45-1:20 | Show **Risk Analysis** and pause on reasons. | “This is the decision point. The score is accompanied by specific evidence—such as cost departure from its regional baseline and a payment/timeline inconsistency. It is a review signal, not a finding of fraud.” |
| 1:20-1:40 | Open **Detection Logic** and adjust the cost ratio once. | “The documented seven features power the system. Changing an input runs the live local scoring path and returns reasons, so the model’s behaviour is inspectable.” |
| 1:40-2:00 | Open **Alerts** and change one alert to under review. | “Finally, the reviewer records workflow state. The alert queue turns detection into a trackable investigation process.” |

## Optional 8C upload demonstration (60–90 seconds)

Use this only if the API, uploaded file, and local extraction dependencies have
been verified on the presentation machine. From the sidebar, select **Upload
file**, upload a prepared small CSV with labelled raw project fields, correct
one field in the editable review form, then select **Confirm & score**. State:

> “Extraction is never treated as truth. A reviewer confirms the fields before
> the existing local scoring pipeline runs, and the result retains the
> evidence and a deterministic review narrative.”

Do not use OCR, a scanned PDF, or an untested Excel file as the live path.

## Demonstration guardrails

- Call every score a **risk/anomaly likelihood review signal**. Never call a
  synthetic project fraudulent, corrupt, or guilty.
- Say “calibrated synthetic Tier 2 project data” whenever displaying project
  records. Describe Tier 1 separately as real public aggregate data.
- Never reveal or describe `_ground_truth_*` fields during the presentation.
- Do not claim a live government portal connection, real transaction-level
  analysis, or a production deployment.
- Use the validated metric wording exactly: top-20% precision 79.17% and
  recall 83.33%, measured after scoring against held-out synthetic evaluation
  labels.

## Technical runbook

### Day before

1. Run the full backend test suite and frontend production build in the final
   presentation environment; record the commands and results.
2. Confirm the API contract matches the current upload implementation before
   demonstrating upload functionality.
3. Correct visible text-encoding defects and verify the active dashboard
   retains access to promised project and contractor flows.
4. Prepare a local presentation folder containing the deck, an offline screen
   recording of the exact primary demo, two evidence-view screenshots, and one
   prepared CSV.
5. Ensure the local model artifact required by upload scoring exists and is
   loaded successfully. Do not train models on stage.

### On stage

1. Use a power-connected laptop, disable notifications, sleep, and automatic
   updates, and set the browser to full screen.
2. Start services before entering the room; test login, overview, project
   analysis, simulator, alerts, and the prepared upload file once.
3. Have a teammate ready with the offline recording. If a request fails, say:
   “To keep the review focused on the evidence, I’ll switch to the recorded
   local run of the same workflow,” then continue immediately.
4. Keep the deck duplicated locally and on second removable/offline storage.
   Do not depend on venue internet.

## Roles

| Role | Responsibility |
|---|---|
| Lead presenter | Problem framing, architecture, metrics, closing ask, and judge questions. |
| Demo operator | Runs the dashboard, notices UI failures early, and switches to recording if needed. |
| Evidence owner | Knows data provenance, evaluation methodology, scoring reasons, and PostGIS design. |
| Backup presenter | Can deliver the two-minute demo and synthetic-data disclosure if the lead is interrupted. |

For a two-person team, the lead owns evidence questions and the demo operator
owns the fallback recording. Rehearse handovers by name rather than silently
passing the laptop.

## Likely judge questions and concise answers

| Question | Recommended answer |
|---|---|
| Is this real government project data? | “The project-level demonstration is calibrated synthetic Tier 2 data because granular implementation data requires authorised eSAKSHI access. The aggregate Tier 1 context is real public data. The storage and scoring path are designed for authorised records.” |
| How does the AI explain itself? | “Every result includes specific coded reasons tied to observed cost, timing, contractor, and geographic patterns. The rule layer makes hard red flags directly readable; the anomaly model adds unusual combinations.” |
| How accurate is it? | “On held-out synthetic evaluation labels, the top 20% review queue achieved 79.17% precision and 83.33% recall. The labels were not model inputs.” |
| Could this falsely accuse someone? | “It must not. The product produces review priority and evidence, not fraud verdicts. A human investigator validates documents and field conditions.” |
| Why not use a large language model? | “The detection path is local, deterministic, and does not require paid APIs or keys. The optional narrative is deterministic and based only on actual reasons.” |
| How do you detect geographic clustering? | “Production uses PostGIS geography with `ST_DWithin` and `ST_ClusterDBSCAN`, rather than rounded coordinates or manual location buckets.” |
| What happens after a flag? | “A reviewer sees evidence, opens an investigation alert, updates its status, and retains an audit trail of review actions.” |

## Acceptance checklist before presenting

- [ ] Full automated test suite passes in the presentation environment.
- [ ] Frontend production build passes in the presentation environment.
- [ ] API and dashboard start from a cold local launch without internet.
- [ ] Primary demo path has been rehearsed end-to-end three times.
- [ ] Prepared project has clear, specific reasons visible.
- [ ] Offline screen recording plays with readable captions.
- [ ] Synthetic Tier 2 disclosure appears in slides and dashboard narration.
- [ ] No `_ground_truth_*` field, API key, secret, or personal data is visible.
- [ ] Upload demo is included only after extraction and scoring pass.
- [ ] Each team member can answer provenance, explainability, and metric questions.

## Sources inside this repository

- `docs/PROBLEM_STATEMENT.md` for problem framing, architecture, and the
  authorised-data deployment boundary.
- `docs/DATA_STRATEGY.md` for Tier 1/Tier 2 provenance and PostGIS geography.
- `BUILD_PLAN.md` and `CONTEXT.md` for verified scorer metrics and module
  status.
