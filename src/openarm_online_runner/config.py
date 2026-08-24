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
from datetime import datetime, time
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


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

    POLL_INTERVAL: int = 3
    EVALUATE_TIMEOUT: int = Field(default=180, gt=0)
    RESET_TIMEOUT: int = Field(default=120, gt=0)
    TELEOPERATE_TIMEOUT: int = Field(default=300, gt=0)

    RECORDER_BASE_DIRECTORY: str = "tmp"
    STATE_DIRECTORY: str = "state"
    DATAFLOW_FILE: str = "dataflow.yaml"
    TELEOPERATION_DATAFLOW_FILE: str = "dataflow-teleoperation.yaml"
    RRD_FPS: int = Field(default=30, gt=0)

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
        now = datetime.now().time()
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
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("openarm_online.runner")
