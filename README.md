# OpenArm Online Runner

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
git clone https://github.com/enactic/openarm-online-runner.git
```

### 4. Install Python dependencies

```bash
cd openarm-online-runner
UV_PROJECT_ENVIRONMENT=.venv-runner uv sync
```

### 5. Configure

The runner reads settings from a `.env` file in the working directory.
Copy [`.env.example`](.env.example) and edit it:

```bash
cp .env.example .env
editor .env
```

### 6. Build the dataflow

```bash
UV_PROJECT_ENVIRONMENT=.venv-runner uv run dora build dataflow.yaml --uv
```

## Run

```bash
UV_PROJECT_ENVIRONMENT=.venv-runner uv run python -m openarm_online_runner.runner
```

## Teleoperation

Besides evaluation jobs, the runner polls the OpenArm Online API for
WebRTC offers queued by Web browsers and serves each one with the
dataflow configured by `TELEOPERATION_DATAFLOW_FILE` (default:
`dataflow-teleoperation.yaml`).

The dataflow must contain a
[`dora-openarm-keyboard`](https://github.com/enactic/dora-openarm-keyboard)
node running in WebRTC-only mode: the runner hands the browser's offer
SDP to the dataflow via the `OFFER` environment variable and listens on
`ANSWER_HOST`/`ANSWER_PORT` for the answer SDP the node writes back. The
answer is posted to the API server, the browser applies it to establish
the WebRTC connection, and teleoperation starts. The session ends when
the dataflow exits (e.g. via a quitter node honoring the `TIMEOUT`
environment variable) or after `TELEOPERATE_TIMEOUT` seconds.

Build the teleoperation dataflow like the evaluation one:

```bash
UV_PROJECT_ENVIRONMENT=.venv-runner uv run dora build dataflow-teleoperation.yaml --uv
```

## Run as a systemd service

```bash
systemd/openarm-online-runner-generate-service.sh \
  | sudo tee /etc/systemd/system/openarm-online-runner.service
sudo systemctl daemon-reload
sudo systemctl enable --now openarm-online-runner
```

Check logs:

```bash
journalctl -u openarm-online-runner
```

## License

Licensed under the Apache License 2.0. See [LICENSE](LICENSE) for details.

Copyright 2026 Enactic, Inc.

## Code of Conduct

All participation in the OpenArm project is governed by our [Code of Conduct](CODE_OF_CONDUCT.md).
