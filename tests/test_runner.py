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

"""Tests for runner."""

import signal

import pytest

from openarm_online_runner import runner
from openarm_online_runner.config import settings


def test_next_job_polls_tasks_in_order(monkeypatch):
    """_next_job() polls each task in order until a job is claimed."""
    monkeypatch.setattr(settings, "OPENARM_ONLINE_TASK_IDS", [1, 2, 3])
    polled = []

    def fetch_next(task_id):
        polled.append(task_id)
        return {"job_id": 10, "task_id": task_id} if task_id == 2 else None

    monkeypatch.setattr(runner.job_client, "fetch_next", fetch_next)

    assert runner._next_job() == {"job_id": 10, "task_id": 2}
    assert polled == [1, 2]


def test_next_job_returns_none(monkeypatch):
    """_next_job() returns None when no task has a queued job."""
    monkeypatch.setattr(settings, "OPENARM_ONLINE_TASK_IDS", [1, 2])
    polled = []

    def fetch_next(task_id):
        polled.append(task_id)

    monkeypatch.setattr(runner.job_client, "fetch_next", fetch_next)

    assert runner._next_job() is None
    assert polled == [1, 2]


def test_next_offer_polls_tasks_in_order(monkeypatch):
    """_next_offer() polls each task in order until an offer is found."""
    monkeypatch.setattr(settings, "OPENARM_ONLINE_TASK_IDS", [1, 2, 3])
    polled = []

    def fetch_pending_offers(task_id):
        polled.append(task_id)
        if task_id == 2:
            return [{"id": 5}, {"id": 6}]
        return []

    monkeypatch.setattr(
        runner.teleoperation_client, "fetch_pending_offers", fetch_pending_offers
    )

    assert runner._next_offer() == {"id": 5}
    assert polled == [1, 2]


def test_next_offer_returns_none(monkeypatch):
    """_next_offer() returns None when no task has a pending offer."""
    monkeypatch.setattr(settings, "OPENARM_ONLINE_TASK_IDS", [1, 2])
    monkeypatch.setattr(
        runner.teleoperation_client, "fetch_pending_offers", lambda task_id: []
    )

    assert runner._next_offer() is None


def test_terminate():
    """_terminate() exits cleanly, leaving further SIGTERMs fatal."""
    original = signal.getsignal(signal.SIGTERM)
    try:
        with pytest.raises(SystemExit) as excinfo:
            runner._terminate(signal.SIGTERM, None)
        assert excinfo.value.code is None
        assert signal.getsignal(signal.SIGTERM) is signal.SIG_DFL
    finally:
        signal.signal(signal.SIGTERM, original)


@pytest.mark.parametrize("interrupt", [KeyboardInterrupt, SystemExit])
def test_run_job_interrupted(monkeypatch, interrupt):
    """run_job() reports the job as failed when interrupted."""
    failed = []
    monkeypatch.setattr(
        runner.job_client,
        "fail_job",
        lambda job_id, reason: failed.append((job_id, reason)),
    )

    def evaluate(job):
        raise interrupt

    monkeypatch.setattr(runner.evaluator, "evaluate", evaluate)

    job = {"job_id": 5, "runtime": "MuJoCo"}
    with pytest.raises(interrupt):
        runner.run_job(job)
    assert failed == [(5, "runner terminated")]


def _fake_teleoperation(monkeypatch):
    stopped_arms = []
    monkeypatch.setattr(runner, "_stop_arms", lambda: stopped_arms.append(True))
    monkeypatch.setattr(
        runner.teleoperator, "teleoperate", lambda offer, send_answer: True
    )
    return stopped_arms


def test_run_teleoperation_stops_arms(monkeypatch):
    """run_teleoperation() stops the arms for an OpenArm Cell session."""
    stopped_arms = _fake_teleoperation(monkeypatch)
    runner.run_teleoperation({"id": 1, "runtime": "OpenArm Cell"})
    assert stopped_arms == [True]


def test_run_teleoperation_mujoco(monkeypatch):
    """run_teleoperation() doesn't stop the arms for a MuJoCo session."""
    stopped_arms = _fake_teleoperation(monkeypatch)
    runner.run_teleoperation({"id": 1, "runtime": "MuJoCo"})
    assert stopped_arms == []
