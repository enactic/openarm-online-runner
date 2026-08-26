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

"""Tests for config."""

from datetime import datetime, time
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from openarm_online_runner.config import Settings
from openarm_online_runner import config


def test_task_ids_comma_separated(monkeypatch):
    """OPENARM_ONLINE_TASK_IDS accepts a comma-separated list."""
    monkeypatch.setenv("OPENARM_ONLINE_TASK_IDS", "1, 2,3")
    assert Settings().OPENARM_ONLINE_TASK_IDS == [1, 2, 3]


def test_task_ids_empty(monkeypatch):
    """OPENARM_ONLINE_TASK_IDS rejects an empty list."""
    monkeypatch.setenv("OPENARM_ONLINE_TASK_IDS", "")
    with pytest.raises(ValidationError):
        Settings()


def test_log_level_case_insensitive(monkeypatch):
    """LOG_LEVEL is normalized to upper case."""
    monkeypatch.setenv("LOG_LEVEL", "info")
    assert Settings().LOG_LEVEL == "INFO"


def test_log_level_invalid(monkeypatch):
    """LOG_LEVEL rejects unknown level names."""
    monkeypatch.setenv("LOG_LEVEL", "noisy")
    with pytest.raises(ValidationError):
        Settings()


def test_env_file(tmp_path, monkeypatch):
    """Settings reads the .env file named by ENV_FILE."""
    env_file = tmp_path / "custom.env"
    env_file.write_text("POLL_INTERVAL=42\n")
    monkeypatch.delenv("POLL_INTERVAL", raising=False)
    monkeypatch.setenv("ENV_FILE", str(env_file))
    assert Settings().POLL_INTERVAL == 42


def test_dataflow_file_per_task(monkeypatch):
    """dataflow_file() prefers DATAFLOW_FILE_${TASK_ID} for the task."""
    monkeypatch.setenv("DATAFLOW_FILE_2", "dataflow-task2.yaml")
    settings = Settings()
    assert settings.dataflow_file(2) == "dataflow-task2.yaml"
    assert settings.dataflow_file(1) == "dataflow.yaml"


def test_dataflow_file_per_task_env_file(tmp_path, monkeypatch):
    """dataflow_file() reads DATAFLOW_FILE_${TASK_ID} from the .env file too."""
    env_file = tmp_path / "custom.env"
    env_file.write_text("""\
DATAFLOW_FILE_2=dataflow-env-file.yaml
DATAFLOW_FILE_3=dataflow-task3.yaml
""")
    monkeypatch.setenv("ENV_FILE", str(env_file))
    monkeypatch.setenv("DATAFLOW_FILE_2", "dataflow-environment.yaml")
    settings = Settings()
    # A real environment variable wins over the .env file.
    assert settings.dataflow_file(2) == "dataflow-environment.yaml"
    assert settings.dataflow_file(3) == "dataflow-task3.yaml"


def test_dataflow_env_file_per_task(monkeypatch):
    """dataflow_env_file() returns DATAFLOW_ENV_FILE_${TASK_ID}, if any."""
    monkeypatch.setenv("DATAFLOW_ENV_FILE_2", "dataflows/task-2/.env")
    settings = Settings()
    assert settings.dataflow_env_file(2) == "dataflows/task-2/.env"
    assert settings.dataflow_env_file(1) is None


def test_teleoperation_dataflow_file_per_task(monkeypatch):
    """teleoperation_dataflow_file() prefers the task's file."""
    monkeypatch.setenv(
        "TELEOPERATION_DATAFLOW_FILE_2", "dataflow-teleoperation-task2.yaml"
    )
    settings = Settings()
    assert (
        settings.teleoperation_dataflow_file(2) == "dataflow-teleoperation-task2.yaml"
    )
    assert settings.teleoperation_dataflow_file(1) == "dataflow-teleoperation.yaml"
    # TELEOPERATION_DATAFLOW_FILE_${TASK_ID} isn't confused with
    # DATAFLOW_FILE_${TASK_ID}.
    assert settings.dataflow_file(2) == "dataflow.yaml"


def test_teleoperation_dataflow_env_file_per_task(monkeypatch):
    """teleoperation_dataflow_env_file() returns the task's .env file, if any."""
    monkeypatch.setenv(
        "TELEOPERATION_DATAFLOW_ENV_FILE_2", "dataflows/task-2/.env-teleoperation"
    )
    settings = Settings()
    assert (
        settings.teleoperation_dataflow_env_file(2)
        == "dataflows/task-2/.env-teleoperation"
    )
    assert settings.teleoperation_dataflow_env_file(1) is None
    assert settings.dataflow_env_file(2) is None


def _datetime_mock(monkeypatch, hour, minute):
    datetime_mock = MagicMock(wraps=datetime)
    datetime_mock.now.return_value = datetime(2026, 1, 1, hour, minute)
    monkeypatch.setattr(config, "datetime", datetime_mock)


@pytest.mark.parametrize(
    "start, end",
    [
        (None, None),
        (time(8, 0), None),
        (None, time(17, 0)),
    ],
)
def test_is_active_time_unset(monkeypatch, start, end):
    """is_active_time() is always active when unset."""
    settings = Settings(ACTIVE_TIME_START=start, ACTIVE_TIME_END=end)
    _datetime_mock(monkeypatch, 22, 0)
    assert settings.is_active_time()


@pytest.mark.parametrize(
    "now_hour, now_minute, expected",
    [
        (3, 0, False),
        (7, 59, False),
        (8, 0, True),
        (12, 0, True),
        (17, 0, True),
        (17, 1, False),
        (22, 0, False),
    ],
)
def test_is_active_time_same_day(monkeypatch, now_hour, now_minute, expected):
    """is_active_time() is active within a same-day range."""
    settings = Settings(ACTIVE_TIME_START=time(8, 0), ACTIVE_TIME_END=time(17, 0))
    _datetime_mock(monkeypatch, now_hour, now_minute)
    assert settings.is_active_time() is expected


@pytest.mark.parametrize(
    "now_hour, now_minute, expected",
    [
        (18, 0, False),
        (21, 59, False),
        (22, 0, True),
        (0, 0, True),
        (6, 0, True),
        (6, 1, False),
        (12, 0, False),
    ],
)
def test_is_active_time_cross_day(monkeypatch, now_hour, now_minute, expected):
    """is_active_time() is active within a cross-day range."""
    settings = Settings(ACTIVE_TIME_START=time(22, 0), ACTIVE_TIME_END=time(6, 0))
    _datetime_mock(monkeypatch, now_hour, now_minute)
    assert settings.is_active_time() is expected
