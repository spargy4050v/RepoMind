"""
MPLAD Synthetic Dataset Generator
==================================
Generates a realistic MPLAD (Member of Parliament Local Area Development)
project dataset with DELIBERATELY EMBEDDED fraud/anomaly patterns, so the
detection engine has real signal to find (not just noise).

IMPORTANT: This is clearly-labeled synthetic data, calibrated to plausible
real-world distributions, used because granular public MPLAD data isn't
available at this detail level. Say this explicitly in the pitch.

Embedded anomaly patterns (each project has a hidden ground-truth label
`is_anomalous` + `anomaly_type`, used later ONLY for evaluating the model,
never fed into the detector itself):
  1. cost_inflation      - cost far above regional baseline for that work type
  2. ghost_project       - completion certified but timeline is implausibly short
  3. contractor_collusion- one contractor wins a suspicious share of projects
                            in one constituency
  4. payment_timing      - funds released before plausible completion
  5. geo_clustering      - many projects clustered at near-identical coordinates
"""

import random
import uuid
import json
import csv
from datetime import date, timedelta
from pathlib import Path

random.seed(42)

WORK_CATEGORIES = {
    "Road Construction":      {"base_cost_per_unit": 850000, "unit": "km",     "base_days": 90},
    "Community Hall":         {"base_cost_per_unit": 2500000, "unit": "unit",  "base_days": 150},
    "Drinking Water Supply":  {"base_cost_per_unit": 1200000, "unit": "unit",  "base_days": 60},
    "School Building Repair": {"base_cost_per_unit": 900000, "unit": "unit",   "base_days": 75},
    "Street Lighting":        {"base_cost_per_unit": 450000, "unit": "unit",   "base_days": 30},
    "Drainage System":        {"base_cost_per_unit": 1100000, "unit": "km",    "base_days": 100},
    "Health Sub-Centre":      {"base_cost_per_unit": 3200000, "unit": "unit",  "base_days": 180},
}

CONSTITUENCIES = [
    ("Nalgonda", "Telangana"), ("Warangal", "Telangana"), ("Secunderabad", "Telangana"),
    ("Kanpur", "Uttar Pradesh"), ("Varanasi", "Uttar Pradesh"), ("Patna Sahib", "Bihar"),
    ("Gaya", "Bihar"), ("Jaipur Rural", "Rajasthan"), ("Kota", "Rajasthan"),
    ("Nagpur", "Maharashtra"), ("Pune", "Maharashtra"), ("Coimbatore", "Tamil Nadu"),
    ("Madurai", "Tamil Nadu"), ("Bhubaneswar", "Odisha"), ("Cuttack", "Odisha"),
]

CONTRACTOR_POOL_SIZE = 220  # realistic-ish number of empanelled contractors nationally

def gen_contractors():
    return [f"CTR-{i:04d}" for i in range(1, CONTRACTOR_POOL_SIZE + 1)]

def random_date(start_year=2022, end_year=2025):
    start = date(start_year, 1, 1)
    end = date(end_year, 12, 31)
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))

def generate_projects(n=3000, contractors=None):
    contractors = contractors or gen_contractors()
    projects = []

    # Pick a small set of "collusion contractors" who will be over-represented
    # in specific constituencies -- this is the pattern the graph/frequency
    # features should catch.
    collusion_pairs = []
    for _ in range(6):
        c = random.choice(contractors)
        constituency = random.choice(CONSTITUENCIES)
        collusion_pairs.append((c, constituency))

    for i in range(n):
        category = random.choice(list(WORK_CATEGORIES.keys()))
        spec = WORK_CATEGORIES[category]
        constituency, state = random.choice(CONSTITUENCIES)

        # Decide if this project uses a "collusion" contractor/constituency pair
        forced_pair = next((cp for cp in collusion_pairs if cp[1] == (constituency, state)), None)
        use_collusion = forced_pair is not None and random.random() < 0.35

        contractor = forced_pair[0] if use_collusion else random.choice(contractors)

        units = round(random.uniform(0.5, 3.0), 2)
        base_cost = spec["base_cost_per_unit"] * units
        base_days = int(spec["base_days"] * units)

        # Normal noise around baseline
        cost = base_cost * random.uniform(0.85, 1.15)
        planned_days = int(base_days * random.uniform(0.9, 1.2))

        recommended_date = random_date(2022, 2024)
        sanction_date = recommended_date + timedelta(days=random.randint(15, 90))
        start_date = sanction_date + timedelta(days=random.randint(5, 45))
        completion_date = start_date + timedelta(days=max(5, int(planned_days * random.uniform(0.9, 1.3))))
        fund_release_date = completion_date + timedelta(days=random.randint(-5, 30))

        lat_base = {"Telangana": 17.4, "Uttar Pradesh": 26.8, "Bihar": 25.6,
                    "Rajasthan": 26.9, "Maharashtra": 19.1, "Tamil Nadu": 11.0,
                    "Odisha": 20.3}[state]
        lon_base = {"Telangana": 78.5, "Uttar Pradesh": 80.9, "Bihar": 85.1,
                    "Rajasthan": 75.8, "Maharashtra": 72.9, "Tamil Nadu": 78.1,
                    "Odisha": 85.8}[state]
        lat = lat_base + random.uniform(-0.5, 0.5)
        lon = lon_base + random.uniform(-0.5, 0.5)

        anomaly_type = None
        is_anomalous = False

        # --- Inject anomaly patterns on a minority of projects ---
        r = random.random()
        if r < 0.06:
            # 1. Cost inflation
            cost = base_cost * random.uniform(1.8, 3.2)
            anomaly_type = "cost_inflation"
            is_anomalous = True
        elif r < 0.10:
            # 2. Ghost / implausibly fast completion
            completion_date = start_date + timedelta(days=max(2, int(planned_days * random.uniform(0.1, 0.3))))
            fund_release_date = completion_date + timedelta(days=random.randint(0, 5))
            anomaly_type = "ghost_project"
            is_anomalous = True
        elif r < 0.13:
            # 3. Payment before completion
            fund_release_date = completion_date - timedelta(days=random.randint(10, 60))
            anomaly_type = "payment_timing"
            is_anomalous = True
        elif use_collusion and random.random() < 0.5:
            anomaly_type = "contractor_collusion"
            is_anomalous = True
        elif r < 0.16:
            # 5. Geo clustering - snap to a tight cluster point
            lat = lat_base + 0.02
            lon = lon_base + 0.02
            anomaly_type = "geo_clustering"
            is_anomalous = True

        projects.append({
            "project_id": f"MPLAD-{i+1:05d}",
            "mp_constituency": constituency,
            "state": state,
            "work_category": category,
            "units": units,
            "unit_type": spec["unit"],
            "contractor_id": contractor,
            "sanctioned_cost_inr": round(cost, 2),
            "regional_baseline_cost_inr": round(base_cost, 2),
            "recommended_date": recommended_date.isoformat(),
            "sanction_date": sanction_date.isoformat(),
            "start_date": start_date.isoformat(),
            "completion_certified_date": completion_date.isoformat(),
            "fund_release_date": fund_release_date.isoformat(),
            "planned_duration_days": planned_days,
            "latitude": round(lat, 4),
            "longitude": round(lon, 4),
            # Ground truth - NOT used by the detector, only for evaluation
            "_ground_truth_is_anomalous": is_anomalous,
            "_ground_truth_anomaly_type": anomaly_type,
        })

    return projects


if __name__ == "__main__":
    projects = generate_projects(n=3000)
    output_path = Path(__file__).with_name("mplad_projects.csv")

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=projects[0].keys())
        writer.writeheader()
        writer.writerows(projects)

    n_anom = sum(1 for p in projects if p["_ground_truth_is_anomalous"])
    print(f"Generated {len(projects)} projects, {n_anom} ({n_anom/len(projects)*100:.1f}%) flagged as anomalous in ground truth")
    from collections import Counter
    print(Counter(p["_ground_truth_anomaly_type"] for p in projects if p["_ground_truth_is_anomalous"]))
