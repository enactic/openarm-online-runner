#!/bin/bash
#
# Copyright 2026 Enactic, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: openarm-online-runner-generate-service.sh [options]

Print a systemd service file for the OpenArm Online runner to stdout.

Options:
  --user USER              process owner (default: current user)
  --working-directory DIR  runner checkout (default: repo root)
  --uv PATH                uv executable (default: uv in PATH)
  --uv-environment DIR     UV_PROJECT_ENVIRONMENT (default: .venv-runner)
  --help                   show this help and exit

Example:
  openarm-online-runner-generate-service.sh \
    | sudo tee /etc/systemd/system/openarm-online-runner.service
  sudo systemctl daemon-reload
  sudo systemctl enable --now openarm-online-runner
USAGE
}

user_name="$(id -un)"
working_directory="$(cd "$(dirname "$0")/.." && pwd)"
uv=""
uv_environment=".venv-runner"

options="$(
  getopt \
    --options "" \
    --longoptions help,user:,working-directory:,uv:,uv-environment: \
    --name "$0" \
    -- "$@"
)"
eval set -- "${options}"

while true; do
  case "$1" in
  --user)
    user_name="$2"
    shift 2
    ;;
  --working-directory)
    working_directory="$2"
    shift 2
    ;;
  --uv)
    uv="$2"
    shift 2
    ;;
  --uv-environment)
    uv_environment="$2"
    shift 2
    ;;
  --help)
    usage
    exit 0
    ;;
  --)
    shift
    break
    ;;
  *)
    usage
    exit 1
    ;;
  esac
done

if [ -z "${uv}" ]; then
  uv="$(command -v uv)"
fi

cat <<SERVICE
[Unit]
Description=OpenArm Online runner
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${user_name}
WorkingDirectory=${working_directory}
Environment=UV_PROJECT_ENVIRONMENT=${uv_environment}
ExecStart=${uv} run openarm-online-runner
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE
