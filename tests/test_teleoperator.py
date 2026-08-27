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

"""Tests for teleoperator."""

import subprocess
import sys

import pytest

from openarm_online_runner import dataflow, teleoperator
from openarm_online_runner.config import settings

OFFER = {"id": 1, "task_id": 1, "kind": "keyboard", "sdp": "offer-sdp"}
WEBXR_OFFER = {"id": 2, "task_id": 1, "kind": "webxr", "sdp": "offer-sdp"}


@pytest.fixture(autouse=True)
def teleoperation_dataflow_files(tmp_path, monkeypatch):
    """Point the dataflow files into tmp_path.

    teleoperate() removes the out/ directory next to the dataflow
    file; with the default dataflow files it would remove the
    repository's out/.
    """
    for kind in ("KEYBOARD", "WEBXR"):
        monkeypatch.setattr(
            settings,
            f"DEFAULT_{kind}_TELEOPERATION_DATAFLOW_FILE",
            str(tmp_path / f"dataflow-{kind.lower()}-teleoperation.yaml"),
        )


# Stand-ins for the dataflow's keyboard node in WebRTC-only mode: connect
# to ANSWER_HOST/ANSWER_PORT and write the bare answer SDP.
ANSWER_SCRIPT = """
import os, socket

with socket.create_connection(
    (os.environ["ANSWER_HOST"], int(os.environ["ANSWER_PORT"]))
) as sock:
    sock.sendall(b"answer-sdp")
"""
ANSWER_THEN_FAIL_SCRIPT = (
    ANSWER_SCRIPT
    + """
raise SystemExit(1)
"""
)
ANSWER_THEN_HANG_SCRIPT = (
    ANSWER_SCRIPT
    + """
import time
time.sleep(30)
"""
)
NO_ANSWER_SCRIPT = """
import time
time.sleep(30)
"""


def _fake_dataflow(monkeypatch, script):
    """Replace dataflow.start with one running the fake node script."""
    started = {}

    def start(dataflow_file, env, stop_after):
        started["dataflow_file"] = dataflow_file
        started["env"] = env
        started["stop_after"] = stop_after
        return subprocess.Popen(
            [sys.executable, "-c", script], env=env, start_new_session=True
        )

    monkeypatch.setattr(dataflow, "start", start)
    return started


def test_teleoperate(monkeypatch):
    """teleoperate() relays the answer SDP and succeeds when the dataflow does."""
    started = _fake_dataflow(monkeypatch, ANSWER_SCRIPT)

    answers = []
    assert teleoperator.teleoperate(OFFER, answers.append)

    assert answers == ["answer-sdp"]
    assert (
        started["dataflow_file"]
        == settings.DEFAULT_KEYBOARD_TELEOPERATION_DATAFLOW_FILE
    )
    assert started["env"]["OFFER"] == "offer-sdp"
    assert started["env"]["TIMEOUT"] == str(settings.TELEOPERATE_TIMEOUT)
    assert started["stop_after"] == settings.TELEOPERATE_TIMEOUT + dataflow.START_WAIT


def test_teleoperate_webxr(monkeypatch):
    """teleoperate() uses the WebXR dataflow for a webxr offer."""
    started = _fake_dataflow(monkeypatch, ANSWER_SCRIPT)

    answers = []
    assert teleoperator.teleoperate(WEBXR_OFFER, answers.append)

    assert answers == ["answer-sdp"]
    assert (
        started["dataflow_file"] == settings.DEFAULT_WEBXR_TELEOPERATION_DATAFLOW_FILE
    )


def test_teleoperate_dataflow_env_file(tmp_path, monkeypatch):
    """teleoperate() merges the task's .env file into the dataflow environment."""
    env_file = tmp_path / "task.env"
    env_file.write_text("""\
TELEOPERATION_DATAFLOW_ENV_FILE_ONLY=from-env-file
""")
    monkeypatch.setattr(
        settings,
        "_teleoperation_dataflow_env_files",
        {"keyboard": {1: str(env_file)}, "webxr": {}},
    )
    started = _fake_dataflow(monkeypatch, ANSWER_SCRIPT)

    answers = []
    assert teleoperator.teleoperate(OFFER, answers.append)
    assert started["env"]["TELEOPERATION_DATAFLOW_ENV_FILE_ONLY"] == "from-env-file"


def test_teleoperate_unconfigured(monkeypatch):
    """teleoperate() fails when no dataflow is configured for the kind."""
    monkeypatch.setattr(settings, "DEFAULT_KEYBOARD_TELEOPERATION_DATAFLOW_FILE", None)

    answers = []
    assert not teleoperator.teleoperate(OFFER, answers.append)
    assert answers == []


def test_teleoperate_start_fails(monkeypatch):
    """teleoperate() fails without calling send_answer when dora cannot start."""

    def start(dataflow_file, env, stop_after):
        raise OSError("dora not found")

    monkeypatch.setattr(dataflow, "start", start)

    answers = []
    assert not teleoperator.teleoperate(OFFER, answers.append)
    assert answers == []


def test_teleoperate_dataflow_fails(monkeypatch):
    """teleoperate() fails when the dataflow exits non-zero."""
    _fake_dataflow(monkeypatch, ANSWER_THEN_FAIL_SCRIPT)

    answers = []
    assert not teleoperator.teleoperate(OFFER, answers.append)
    assert answers == ["answer-sdp"]


def test_teleoperate_no_answer(monkeypatch):
    """teleoperate() fails without calling send_answer when no answer arrives."""
    monkeypatch.setattr(dataflow, "START_WAIT", 1)
    _fake_dataflow(monkeypatch, NO_ANSWER_SCRIPT)

    answers = []
    assert not teleoperator.teleoperate(OFFER, answers.append)
    assert answers == []


def test_teleoperate_session_timeout(monkeypatch):
    """teleoperate() fails when the dataflow outlives the session timeout."""
    monkeypatch.setattr(dataflow, "START_WAIT", 1)
    monkeypatch.setattr(dataflow, "STOP_WAIT", 1)
    monkeypatch.setattr(settings, "TELEOPERATE_TIMEOUT", 1)
    _fake_dataflow(monkeypatch, ANSWER_THEN_HANG_SCRIPT)

    answers = []
    assert not teleoperator.teleoperate(OFFER, answers.append)
    assert answers == ["answer-sdp"]
