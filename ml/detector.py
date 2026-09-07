import pandas as pd
from sklearn.ensemble import IsolationForest


# Load project data
data = pd.read_csv("../data/projects.csv")


# Calculate useful features
data["cost_ratio"] = data["actual_cost"] / data["estimated_cost"]

data["payment_gap"] = data["payment_days"]

data["contractor_concentration"] = data["contractor_projects"]


# Features used by AI
features = [
    "cost_ratio",
    "completion_days",
    "payment_gap",
    "contractor_concentration"
]

X = data[features]


# AI anomaly detection model
model = IsolationForest(
    contamination=0.25,
    random_state=42
)

data["ai_prediction"] = model.fit_predict(X)


# Convert AI result
data["ai_anomaly"] = data["ai_prediction"].apply(
    lambda x: 1 if x == -1 else 0
)


# Rule-based risk score
def calculate_risk(row):

    score = 0
    reasons = []

    # High cost
    if row["cost_ratio"] > 1.20:
        score += 30
        reasons.append("Actual cost is much higher than estimated cost")

    # Slow completion
    if row["completion_days"] > 250:
        score += 25
        reasons.append("Project completion took unusually long")

    # Large payment gap
    if row["payment_gap"] > 60:
        score += 20
        reasons.append("Large payment delay detected")

    # Contractor concentration
    if row["contractor_concentration"] > 8:
        score += 15
        reasons.append("High contractor concentration")

    # AI anomaly
    if row["ai_anomaly"] == 1:
        score += 10
        reasons.append("AI detected an unusual project pattern")

    return pd.Series([min(score, 100), ", ".join(reasons)])


# Calculate risk
data[["risk_score", "risk_reasons"]] = data.apply(
    calculate_risk,
    axis=1
)


# Sort highest risk first
data = data.sort_values(
    by="risk_score",
    ascending=False
)


# Display results
print("\n===== MPLAD TRACE AI RESULTS =====\n")

print(
    data[
        [
            "project_id",
            "project_type",
            "actual_cost",
            "risk_score",
            "risk_reasons"
        ]
    ].to_string(index=False)
)