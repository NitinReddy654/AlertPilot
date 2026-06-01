from __future__ import annotations

import json
from pathlib import Path

import joblib
import mlflow
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


def main() -> None:
    df = pd.read_csv("data/validated/alerts.csv")
    df["text"] = df["title"] + " " + df["metric_name"]
    features = df[["text", "service", "environment", "tier", "metric_value", "threshold"]]
    target = df["severity"]
    x_train, x_test, y_train, y_test = train_test_split(
        features, target, test_size=0.2, random_state=7, stratify=target
    )
    preprocessor = ColumnTransformer(
        transformers=[
            ("text", TfidfVectorizer(ngram_range=(1, 2), min_df=3), "text"),
            ("cat", OneHotEncoder(handle_unknown="ignore"), ["service", "environment"]),
            ("num", StandardScaler(), ["tier", "metric_value", "threshold"]),
        ]
    )
    model = Pipeline(
        steps=[
            ("features", preprocessor),
            ("classifier", LogisticRegression(max_iter=600, class_weight="balanced")),
        ]
    )
    mlflow.set_tracking_uri("./.mlflow")
    mlflow.set_experiment("alertpilot-triage")
    with mlflow.start_run(run_name="severity-classifier"):
        model.fit(x_train, y_train)
        preds = model.predict(x_test)
        metrics = {
            "accuracy": float(accuracy_score(y_test, preds)),
            "macro_f1": float(f1_score(y_test, preds, average="macro")),
            "weighted_f1": float(f1_score(y_test, preds, average="weighted")),
            "train_rows": int(len(x_train)),
            "test_rows": int(len(x_test)),
        }
        mlflow.log_metrics({k: v for k, v in metrics.items() if isinstance(v, float)})
        mlflow.log_param("model", "tfidf_onehot_logistic_regression")
        Path("artifacts/models").mkdir(parents=True, exist_ok=True)
        Path("artifacts/reports").mkdir(parents=True, exist_ok=True)
        joblib.dump(model, "artifacts/models/severity_classifier.joblib")
        report = classification_report(y_test, preds, output_dict=True)
        Path("artifacts/reports/training_metrics.json").write_text(json.dumps({"metrics": metrics, "report": report}, indent=2))
        mlflow.log_artifact("artifacts/models/severity_classifier.joblib")
        mlflow.log_artifact("artifacts/reports/training_metrics.json")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
