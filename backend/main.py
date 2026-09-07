from fastapi import FastAPI
import pandas as pd
import sys
import os

# Allow Python to find the ML folder
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "ml"))

from detector import data


app = FastAPI(
    title="MPLAD Trace API",
    description="AI-powered anomaly and fraud detection system for MPLAD projects",
    version="1.0.0"
)


@app.get("/")
def home():
    return {
        "message": "MPLAD Trace API is running!",
        "status": "success"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.get("/projects")
def get_projects():

    projects = data[
        [
            "project_id",
            "state",
            "district",
            "project_type",
            "sanction_amount",
            "estimated_cost",
            "actual_cost",
            "completion_days",
            "payment_days",
            "contractor_projects",
            "risk_score",
            "risk_reasons"
        ]
    ].copy()

    projects = projects.fillna("")

    return projects.to_dict(orient="records")


@app.get("/projects/high-risk")
def get_high_risk_projects():

    high_risk = data[data["risk_score"] >= 50]

    high_risk = high_risk[
        [
            "project_id",
            "state",
            "district",
            "project_type",
            "actual_cost",
            "risk_score",
            "risk_reasons"
        ]
    ]

    high_risk = high_risk.fillna("")

    return high_risk.to_dict(orient="records")