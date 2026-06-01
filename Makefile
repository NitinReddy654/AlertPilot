.PHONY: run test benchmark docker pipeline validate train

run:
	uvicorn alertpilot.main:app --reload --host 127.0.0.1 --port 8000

test:
	python -m pytest -q

pipeline:
	dvc repro

validate:
	python scripts/validate_alerts.py

train:
	python scripts/train_triage_model.py

benchmark:
	python scripts/benchmark_api.py

docker:
	docker build -t alertpilot:latest -f infra/docker/Dockerfile .
