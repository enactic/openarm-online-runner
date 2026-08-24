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

"""Tests for evaluator."""

from pathlib import Path

from openarm_online_runner.config import settings
from openarm_online_runner.evaluator import EVALUATE_PHASE, evaluate, succeeded

TESTS_DIR = Path(__file__).parent


def test_run(capfd, tmp_path, monkeypatch):
    """evaluate() completes successfully."""
    monkeypatch.setattr(
        settings, "DEFAULT_DATAFLOW_FILE", str(TESTS_DIR / "dataflow.yaml")
    )
    monkeypatch.setattr(settings, "RECORDER_BASE_DIRECTORY", str(tmp_path))

    job = {"job_id": 1, "task_id": 1, "docker_tag": "dummy"}
    assert evaluate(job)


def test_succeeded_true(monkeypatch):
    """succeeded() is True on success."""
    monkeypatch.setattr(
        settings, "RECORDER_BASE_DIRECTORY", str(TESTS_DIR / "fixtures" / "dataset")
    )
    job = {"job_id": 1, "docker_tag": "dummy"}
    assert succeeded(EVALUATE_PHASE, job)


def test_succeeded_false(monkeypatch):
    """succeeded() is False on failure."""
    monkeypatch.setattr(
        settings, "RECORDER_BASE_DIRECTORY", str(TESTS_DIR / "fixtures" / "dataset")
    )
    job = {"job_id": 2, "docker_tag": "dummy"}
    assert not succeeded(EVALUATE_PHASE, job)


def test_succeeded_no_episode(monkeypatch):
    """succeeded() is False with no episode."""
    monkeypatch.setattr(
        settings, "RECORDER_BASE_DIRECTORY", str(TESTS_DIR / "fixtures" / "dataset")
    )
    job = {"job_id": 3, "docker_tag": "dummy"}
    assert not succeeded(EVALUATE_PHASE, job)


def test_succeeded_no_metadata_yaml(monkeypatch):
    """succeeded() is False when metadata.yaml is empty."""
    monkeypatch.setattr(
        settings, "RECORDER_BASE_DIRECTORY", str(TESTS_DIR / "fixtures" / "dataset")
    )
    job = {"job_id": 4, "docker_tag": "dummy"}
    assert not succeeded(EVALUATE_PHASE, job)


def test_succeeded_no_dataset_directory(monkeypatch):
    """succeeded() is False when the recording directory does not exist."""
    monkeypatch.setattr(
        settings, "RECORDER_BASE_DIRECTORY", str(TESTS_DIR / "fixtures" / "dataset")
    )
    job = {"job_id": 999, "docker_tag": "dummy"}
    assert not succeeded(EVALUATE_PHASE, job)
