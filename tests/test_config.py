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

from openarm_online_runner.config import Settings
from openarm_online_runner import config


def test_env_file(tmp_path, monkeypatch):
    """Settings reads the .env file named by ENV_FILE."""
    env_file = tmp_path / "custom.env"
    env_file.write_text("POLL_INTERVAL=42\n")
    monkeypatch.delenv("POLL_INTERVAL", raising=False)
    monkeypatch.setenv("ENV_FILE", str(env_file))
    assert Settings().POLL_INTERVAL == 42


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
