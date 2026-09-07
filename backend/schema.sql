-- MPLAD Trace — Postgres + PostGIS Schema
-- Two-tier design: Tier 1 = real public aggregate data, Tier 2 = synthetic transaction-level data

CREATE EXTENSION IF NOT EXISTS postgis;

-- ============================================================
-- TIER 1: Real public aggregate data (from data.gov.in / dataful.in)
-- Source: state-wise / MP-wise / district-wise / year-wise fund totals
-- ============================================================

CREATE TABLE mp_fund_summary (
    id SERIAL PRIMARY KEY,
    lok_sabha_term INT NOT NULL,          -- e.g. 17
    financial_year VARCHAR(9) NOT NULL,    -- e.g. '2023-24'
    state VARCHAR(100) NOT NULL,
    district VARCHAR(100),
    constituency VARCHAR(150) NOT NULL,
    mp_name VARCHAR(200),
    entitled_amount_inr NUMERIC(15, 2) NOT NULL,
    released_amount_inr NUMERIC(15, 2) NOT NULL,
    sanctioned_amount_inr NUMERIC(15, 2) NOT NULL,
    expended_amount_inr NUMERIC(15, 2) NOT NULL,
    unspent_amount_inr NUMERIC(15, 2) NOT NULL,
    works_recommended_count INT,
    works_sanctioned_count INT,
    works_completed_count INT,
    source_dataset VARCHAR(200),           -- track provenance, e.g. 'dataful.in/datasets/18533'
    ingested_at TIMESTAMP DEFAULT NOW()
);

-- Macro anomaly signals computed FROM Tier 1 (real data) at query/batch time:
--   utilization_ratio = expended / sanctioned  (unusually low = red flag)
--   unspent_ratio = unspent / entitled          (unusually high = red flag)
--   completion_ratio = completed / sanctioned works count
-- These are VIEWS, not injected labels -- they're derived from real numbers.

CREATE VIEW mp_utilization_anomalies AS
SELECT
    *,
    ROUND(expended_amount_inr / NULLIF(sanctioned_amount_inr, 0), 3) AS utilization_ratio,
    ROUND(unspent_amount_inr / NULLIF(entitled_amount_inr, 0), 3) AS unspent_ratio,
    ROUND(works_completed_count::NUMERIC / NULLIF(works_sanctioned_count, 0), 3) AS completion_ratio
FROM mp_fund_summary;

-- ============================================================
-- TIER 2: Synthetic transaction-level data (calibrated to Tier 1 stats)
-- ============================================================

CREATE TABLE contractors (
    contractor_id VARCHAR(20) PRIMARY KEY,
    name VARCHAR(200),                     -- synthetic
    registered_state VARCHAR(100)
);

CREATE TABLE projects (
    project_id VARCHAR(20) PRIMARY KEY,
    mp_constituency VARCHAR(150) NOT NULL,
    state VARCHAR(100) NOT NULL,
    work_category VARCHAR(100) NOT NULL,
    units NUMERIC(6, 2),
    unit_type VARCHAR(20),
    contractor_id VARCHAR(20) REFERENCES contractors(contractor_id),
    sanctioned_cost_inr NUMERIC(15, 2) NOT NULL,
    regional_baseline_cost_inr NUMERIC(15, 2) NOT NULL,
    recommended_date DATE,
    sanction_date DATE,
    start_date DATE,
    completion_certified_date DATE,
    fund_release_date DATE,
    planned_duration_days INT,
    location GEOGRAPHY(POINT, 4326),        -- PostGIS point, replaces raw lat/lon columns
    -- Ground truth (evaluation only -- NEVER fed to the detector as a feature)
    gt_is_anomalous BOOLEAN,
    gt_anomaly_type VARCHAR(30)
);

CREATE INDEX idx_projects_location ON projects USING GIST (location);
CREATE INDEX idx_projects_contractor ON projects (contractor_id);
CREATE INDEX idx_projects_constituency ON projects (mp_constituency);

CREATE TABLE project_scores (
    project_id VARCHAR(20) PRIMARY KEY REFERENCES projects(project_id),
    risk_score NUMERIC(5, 2) NOT NULL,
    top_anomaly_type VARCHAR(30),
    scored_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE project_score_reasons (
    id SERIAL PRIMARY KEY,
    project_id VARCHAR(20) REFERENCES projects(project_id),
    reason_code VARCHAR(50) NOT NULL,
    reason_text TEXT NOT NULL
);

-- Example PostGIS geo-clustering query (replaces the pandas lat/lon-bucket hack):
-- Find projects within 2km of each other -- real spatial clustering, not approximation.
--
-- SELECT p1.project_id, COUNT(p2.project_id) AS nearby_count
-- FROM projects p1
-- JOIN projects p2 ON ST_DWithin(p1.location, p2.location, 2000) AND p1.project_id != p2.project_id
-- GROUP BY p1.project_id;
