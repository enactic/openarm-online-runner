# OpenEval Runner

## Install

These instructions assume Ubuntu.

### 1. Install system dependencies

```bash
sudo apt-get update
sudo apt-get install -y -V \
  build-essential \
  ffmpeg \
  git \
  python3-dev \
  software-properties-common

sudo add-apt-repository -y ppa:openarm/main
sudo apt-get update
sudo apt-get install -y -V libopenarm-can-dev
```

### 2. Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 3. Clone the code

```bash
git clone https://github.com/enactic/openeval-runner.git
```

### 4. Install Python dependencies

```bash
cd openeval-runner
UV_PROJECT_ENVIRONMENT=.venv-runner uv sync
```

### 5. Configure

The runner reads settings from a `.env` file in the working directory.

```bash
OPENEVAL_API_URL=https://example.com
OPENEVAL_API_KEY=xxx
OPENEVAL_TASK_ID=1

DATAFLOW_FILE=dataflow.yaml
RECORDER_BASE_DIRECTORY=/path/to
```

### 6. Build the dataflow

```bash
UV_PROJECT_ENVIRONMENT=.venv-runner uv run dora build dataflow.yaml --uv
```

## Run

```bash
UV_PROJECT_ENVIRONMENT=.venv-runner uv run python -m openeval_runner.runner
```

## Run as a systemd service

```bash
systemd/openeval-runner-generate-service.sh \
  | sudo tee /etc/systemd/system/openeval-runner.service
sudo systemctl daemon-reload
sudo systemctl enable --now openeval-runner
```

Check logs:

```bash
journalctl -u openeval-runner
```

## License

Licensed under the Apache License 2.0. See [LICENSE](LICENSE) for details.

Copyright 2026 Enactic, Inc.

## Code of Conduct

All participation in the OpenArm project is governed by our [Code of Conduct](CODE_OF_CONDUCT.md).
