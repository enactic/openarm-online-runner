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

"""Tests for converter."""

from pathlib import Path

from openarm_online_runner import converter
from openarm_online_runner.config import settings
from openarm_online_runner.evaluator import evaluate

TESTS_DIR = Path(__file__).parent


def test_convert_generates_rrd(capfd, tmp_path, monkeypatch):
    """convert() writes it out as an .rrd file."""
    monkeypatch.setattr(settings, "DATAFLOW_FILE", str(TESTS_DIR / "dataflow.yaml"))
    monkeypatch.setattr(settings, "RECORDER_BASE_DIRECTORY", str(tmp_path))

    job = {"job_id": 1, "docker_tag": "dummy"}
    assert evaluate(job)

    rrd_path = converter.convert(job)
    assert rrd_path == tmp_path / "evaluate-1" / "output.rrd"
    assert rrd_path.is_file()
