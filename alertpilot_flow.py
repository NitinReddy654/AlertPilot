from __future__ import annotations

import subprocess

from prefect import flow, task


@task
def run_step(command: list[str]) -> None:
    subprocess.run(command, check=True)


@flow(name="alertpilot-nightly-triage-pipeline")
def triage_pipeline() -> None:
    run_step(["python", "scripts/generate_alerts.py"])
    run_step(["python", "scripts/validate_alerts.py"])
    run_step(["python", "scripts/train_triage_model.py"])
    run_step(["python", "scripts/benchmark_api.py"])


if __name__ == "__main__":
    triage_pipeline()
