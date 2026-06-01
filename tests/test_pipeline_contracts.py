from pathlib import Path


def test_project_contract_files_exist():
    required = [
        "README.md",
        "dvc.yaml",
        "requirements.txt",
        "environment.yml",
        ".github/workflows/ci.yml",
        "infra/docker/Dockerfile",
        "infra/docker/monitoring/docker-compose.yml",
    ]
    missing = [item for item in required if not Path(item).exists()]
    assert missing == []
