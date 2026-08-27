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

"""Configuration globals and logging setup."""

import logging
import os
import re
from datetime import datetime, time
from typing import Annotated

from dotenv import dotenv_values
from pydantic import Field, PrivateAttr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_DATAFLOW_FILE_PATTERN = re.compile(r"DATAFLOW_FILE_(\d+)")
_DATAFLOW_ENV_FILE_PATTERN = re.compile(r"DATAFLOW_ENV_FILE_(\d+)")

# The kinds of teleoperation clients. They must match the API server's
# TeleoperationKind values reported in offers' "kind".
TELEOPERATION_KINDS = ("keyboard", "webxr")

_TELEOPERATION_DATAFLOW_FILE_PATTERNS = {
    kind: re.compile(rf"{kind.upper()}_TELEOPERATION_DATAFLOW_FILE_(\d+)")
    for kind in TELEOPERATION_KINDS
}
_TELEOPERATION_DATAFLOW_ENV_FILE_PATTERNS = {
    kind: re.compile(rf"{kind.upper()}_TELEOPERATION_DATAFLOW_ENV_FILE_(\d+)")
    for kind in TELEOPERATION_KINDS
}


def _read_env(env_file):
    """Read the .env file and os.environ as one dict.

    pydantic-settings can't declare fields with dynamic names and
    doesn't export .env values to os.environ, so we merge the .env
    file and os.environ ourselves. Like other settings, real
    environment variables win over the .env file.
    """
    return dict(dotenv_values(env_file)) | dict(os.environ)


def _collect_task_values(pattern, env):
    """Collect per-task ${PREFIX}_${TASK_ID} values matching pattern."""
    values = {}
    for name, value in env.items():
        match = pattern.fullmatch(name)
        if match and value:
            values[int(match.group(1))] = value
    return values


class Settings(BaseSettings):
    """Runner settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    def __init__(self, **kwargs):
        """Read settings from the file named by ENV_FILE instead of .env."""
        kwargs.setdefault("_env_file", os.environ.get("ENV_FILE", ".env"))
        super().__init__(**kwargs)
        env = _read_env(kwargs["_env_file"])
        self._dataflow_files = _collect_task_values(_DATAFLOW_FILE_PATTERN, env)
        self._dataflow_env_files = _collect_task_values(_DATAFLOW_ENV_FILE_PATTERN, env)
        self._teleoperation_dataflow_files = {
            kind: _collect_task_values(pattern, env)
            for kind, pattern in _TELEOPERATION_DATAFLOW_FILE_PATTERNS.items()
        }
        self._teleoperation_dataflow_env_files = {
            kind: _collect_task_values(pattern, env)
            for kind, pattern in _TELEOPERATION_DATAFLOW_ENV_FILE_PATTERNS.items()
        }

    LOG_LEVEL: str = "DEBUG"

    @field_validator("LOG_LEVEL")
    @classmethod
    def _validate_log_level(cls, value):
        """Accept standard logging level names, case-insensitively."""
        level = value.upper()
        if level not in logging.getLevelNamesMapping():
            raise ValueError(f"invalid log level: {value}")
        return level

    POLL_INTERVAL: int = 3
    EVALUATE_TIMEOUT: int = Field(default=180, gt=0)
    RESET_TIMEOUT: int = Field(default=120, gt=0)
    TELEOPERATE_TIMEOUT: int = Field(default=300, gt=0)

    RECORDER_BASE_DIRECTORY: str = "tmp"
    STATE_DIRECTORY: str = "state"
    DEFAULT_DATAFLOW_FILE: str = "dataflow.yaml"
    # Without a dataflow file (these or the per-task
    # ${KIND}_TELEOPERATION_DATAFLOW_FILE_${TASK_ID} ones),
    # teleoperation of the kind is disabled for the task.
    DEFAULT_KEYBOARD_TELEOPERATION_DATAFLOW_FILE: str | None = None
    DEFAULT_WEBXR_TELEOPERATION_DATAFLOW_FILE: str | None = None
    RRD_FPS: int = Field(default=30, gt=0)

    _dataflow_files: dict[int, str] = PrivateAttr(default_factory=dict)
    _dataflow_env_files: dict[int, str] = PrivateAttr(default_factory=dict)
    _teleoperation_dataflow_files: dict[str, dict[int, str]] = PrivateAttr(
        default_factory=dict
    )
    _teleoperation_dataflow_env_files: dict[str, dict[int, str]] = PrivateAttr(
        default_factory=dict
    )

    def dataflow_file(self, task_id) -> str:
        """Dataflow file for the task.

        DATAFLOW_FILE_${TASK_ID} takes precedence over
        DEFAULT_DATAFLOW_FILE.
        """
        return self._dataflow_files.get(task_id, self.DEFAULT_DATAFLOW_FILE)

    def dataflow_env_file(self, task_id) -> str | None:
        """.env file for the task's dataflow: DATAFLOW_ENV_FILE_${TASK_ID}."""
        return self._dataflow_env_files.get(task_id)

    def teleoperation_dataflow_file(self, kind, task_id) -> str | None:
        """Teleoperation dataflow file for the offer's kind and the task.

        ${KIND}_TELEOPERATION_DATAFLOW_FILE_${TASK_ID} takes precedence
        over DEFAULT_${KIND}_TELEOPERATION_DATAFLOW_FILE. None means
        that teleoperation of the kind is disabled for the task.
        """
        default = getattr(
            self, f"DEFAULT_{kind.upper()}_TELEOPERATION_DATAFLOW_FILE", None
        )
        return self._teleoperation_dataflow_files.get(kind, {}).get(task_id, default)

    def teleoperation_dataflow_env_file(self, kind, task_id) -> str | None:
        """.env file for the task's teleoperation dataflow of the kind.

        ${KIND}_TELEOPERATION_DATAFLOW_ENV_FILE_${TASK_ID}, if any.
        """
        return self._teleoperation_dataflow_env_files.get(kind, {}).get(task_id)

    OPENARM_ONLINE_API_URL: str = "http://localhost:8000"
    OPENARM_ONLINE_API_KEY: str
    OPENARM_ONLINE_TASK_IDS: Annotated[list[int], NoDecode] = Field(min_length=1)

    @field_validator("OPENARM_ONLINE_TASK_IDS", mode="before")
    @classmethod
    def _split_task_ids(cls, value):
        """Parse a comma-separated task ID list such as "1,2,3"."""
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    ACTIVE_TIME_START: time | None = None
    ACTIVE_TIME_END: time | None = None

    def is_active_time(self) -> bool:
        """Whether or not it is a period of activity."""
        start = self.ACTIVE_TIME_START
        end = self.ACTIVE_TIME_END
        if start is None or end is None:
            return True
        # Naive datetime is intended: ACTIVE_TIME_START/ACTIVE_TIME_END
        # are local wall-clock times.
        now = datetime.now().time()  # noqa: DTZ005
        if start <= end:
            # Example:
            # start=08:00
            # end=17:00
            return now >= start and now <= end
        # Example:
        # start=22:00
        # end=06:00
        return now >= start or now <= end


settings = Settings()


# --------------------------------------------------
# Logging
# --------------------------------------------------

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("openarm_online.runner")
