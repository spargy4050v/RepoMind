"""Feature engineering for the calibrated synthetic MPLAD project dataset.

The feature matrix deliberately excludes every ``_ground_truth_*`` column.
Those labels are retained in the source CSV solely for later evaluation.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Final

import numpy as np
import pandas as pd


DATASET_PATH: Final[Path] = Path(__file__).resolve().parents[2] / "data" / "mplad_projects.csv"
FEATURE_COLUMNS: Final[tuple[str, ...]] = (
    "cost_ratio",
    "completion_speed_ratio",
    "payment_gap_days",
    "contractor_project_count",
    "contractor_constituency_share",
    "geo_cluster_density",
    "sanction_lag_days",
)
EARTH_RADIUS_METRES: Final[float] = 6_371_008.8


def load_project_data(csv_path: str | Path = DATASET_PATH) -> pd.DataFrame:
    """Load the synthetic Tier 2 project CSV without treating labels as features."""
    return pd.read_csv(csv_path)


def cost_ratio(frame: pd.DataFrame) -> pd.Series:
    """Measure cost against its regional baseline; an unusually high ratio can indicate inflation."""
    sanctioned = pd.to_numeric(frame["sanctioned_cost_inr"], errors="coerce")
    baseline = pd.to_numeric(frame["regional_baseline_cost_inr"], errors="coerce")
    return sanctioned.div(baseline.where(baseline > 0))


def completion_speed_ratio(frame: pd.DataFrame) -> pd.Series:
    """Compare actual to planned duration; unusually small values can indicate implausibly rapid certification."""
    started = pd.to_datetime(frame["start_date"], errors="coerce")
    completed = pd.to_datetime(frame["completion_certified_date"], errors="coerce")
    planned = pd.to_numeric(frame["planned_duration_days"], errors="coerce")
    actual_duration = (completed - started).dt.days
    return actual_duration.div(planned.where(planned > 0))


def payment_gap_days(frame: pd.DataFrame) -> pd.Series:
    """Measure release minus certified-completion days; negative values indicate payment before completion."""
    released = pd.to_datetime(frame["fund_release_date"], errors="coerce")
    completed = pd.to_datetime(frame["completion_certified_date"], errors="coerce")
    return (released - completed).dt.days


def contractor_project_count(frame: pd.DataFrame) -> pd.Series:
    """Count a contractor's national projects; unusually high volume can reveal concentration of awards."""
    contractor = frame["contractor_id"].astype("string").str.strip()
    valid = contractor.notna() & contractor.ne("")
    counts = contractor.where(valid).groupby(contractor.where(valid), dropna=True).transform("size")
    return counts.where(valid, 0)


def contractor_constituency_share(frame: pd.DataFrame) -> pd.Series:
    """Compute a contractor's constituency project share; dominance may indicate collusive award concentration."""
    contractor = frame["contractor_id"].astype("string").str.strip()
    constituency = frame["mp_constituency"].astype("string").str.strip()
    valid = contractor.notna() & contractor.ne("") & constituency.notna() & constituency.ne("")
    pairs = pd.DataFrame({"contractor": contractor.where(valid), "constituency": constituency.where(valid)})
    numerator = pairs.groupby(["contractor", "constituency"], dropna=True)["contractor"].transform("size")
    denominator = constituency.where(constituency.notna() & constituency.ne("")).groupby(constituency).transform("size")
    return numerator.div(denominator).where(valid, 0)


def local_geo_cluster_density(frame: pd.DataFrame, radius_metres: float = 2_000.0) -> pd.Series:
    """Test-only local fallback for ``ST_DWithin`` using exact great-circle distance, never coordinate buckets.

    Production calls PostGIS through :func:`postgis_geo_cluster_density`; this fallback exists so the
    CSV-only Module 2 tests can run without a database service. It has the same inclusive-radius,
    excluding-self meaning as ``ST_DWithin(project.location, other.location, radius_metres)`` on geography.
    """
    latitudes = pd.to_numeric(frame["latitude"], errors="coerce").to_numpy(dtype=float)
    longitudes = pd.to_numeric(frame["longitude"], errors="coerce").to_numpy(dtype=float)
    valid = np.isfinite(latitudes) & np.isfinite(longitudes)
    density = np.zeros(len(frame), dtype=np.int64)
    positions = np.flatnonzero(valid)
    lat = np.radians(latitudes[positions])
    lon = np.radians(longitudes[positions])
    threshold = radius_metres / EARTH_RADIUS_METRES

    for start in range(0, len(positions), 256):
        chunk_lat = lat[start : start + 256, None]
        chunk_lon = lon[start : start + 256, None]
        haversine = np.sin((lat[None, :] - chunk_lat) / 2) ** 2
        haversine += np.cos(chunk_lat) * np.cos(lat[None, :]) * np.sin((lon[None, :] - chunk_lon) / 2) ** 2
        angular_distance = 2 * np.arcsin(np.sqrt(np.clip(haversine, 0, 1)))
        density[positions[start : start + 256]] = (angular_distance <= threshold).sum(axis=1) - 1
    return pd.Series(density, index=frame.index, dtype="float64")


def postgis_geo_cluster_density(project_ids: pd.Series, dsn: str) -> pd.Series:
    """Fetch production geo density using indexed PostGIS ``ST_DWithin`` geography semantics.

    The caller must first load the same synthetic CSV into ``projects`` with its ``location`` geography set.
    Missing database rows are returned as zero so the feature matrix remains finite, while an unavailable
    database deliberately raises its connection error instead of silently claiming production spatial results.
    """
    import psycopg

    query = """
        SELECT p1.project_id, COUNT(p2.project_id)::integer AS geo_cluster_density
        FROM projects AS p1
        LEFT JOIN projects AS p2
          ON p1.project_id <> p2.project_id
         AND ST_DWithin(p1.location, p2.location, 2000)
        GROUP BY p1.project_id
    """
    with psycopg.connect(dsn) as connection, connection.cursor() as cursor:
        cursor.execute(query)
        values: Mapping[str, int] = {project_id: count for project_id, count in cursor.fetchall()}
    return project_ids.map(values).fillna(0).astype("float64")


def build_feature_matrix(csv_path: str | Path = DATASET_PATH, postgis_dsn: str | None = None) -> pd.DataFrame:
    """Return ``project_id`` plus exactly seven finite, unlabeled Module 2 numerical features.

    Passing ``postgis_dsn`` selects the production PostGIS density query. Omitting it selects the documented
    exact-distance local fallback so the checked-in CSV can be validated offline before database ingestion.
    """
    source = load_project_data(csv_path)
    required = {
        "project_id", "sanctioned_cost_inr", "regional_baseline_cost_inr", "start_date",
        "completion_certified_date", "fund_release_date", "planned_duration_days", "contractor_id",
        "mp_constituency", "recommended_date", "sanction_date", "latitude", "longitude",
    }
    missing = sorted(required.difference(source.columns))
    if missing:
        raise ValueError(f"Source CSV is missing required columns: {', '.join(missing)}")

    features = pd.DataFrame({"project_id": source["project_id"].astype("string")}, index=source.index)
    features["cost_ratio"] = cost_ratio(source)
    features["completion_speed_ratio"] = completion_speed_ratio(source)
    features["payment_gap_days"] = payment_gap_days(source)
    features["contractor_project_count"] = contractor_project_count(source)
    features["contractor_constituency_share"] = contractor_constituency_share(source)
    features["geo_cluster_density"] = (
        postgis_geo_cluster_density(features["project_id"], postgis_dsn)
        if postgis_dsn
        else local_geo_cluster_density(source)
    )
    sanctioned = pd.to_datetime(source["sanction_date"], errors="coerce")
    recommended = pd.to_datetime(source["recommended_date"], errors="coerce")
    features["sanction_lag_days"] = (sanctioned - recommended).dt.days
    numeric = list(FEATURE_COLUMNS)
    features[numeric] = features[numeric].replace([np.inf, -np.inf], np.nan).fillna(0.0).astype("float64")
    return features[["project_id", *FEATURE_COLUMNS]]
