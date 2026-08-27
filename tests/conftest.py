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

"""pytest configuration."""

import os
import subprocess
from pathlib import Path

import pytest

# Keep the developer's local .env out of the tests. Tests that need
# an .env file set ENV_FILE themselves.
os.environ["ENV_FILE"] = os.devnull

os.environ.setdefault("OPENARM_ONLINE_API_KEY", "test-api-key")
os.environ.setdefault("OPENARM_ONLINE_TASK_IDS", "1")

TESTS_DIR = Path(__file__).parent


@pytest.fixture(scope="session", autouse=True)
def build_dataflow():
    """Build the test dataflow before running tests."""
    subprocess.run(
        ["dora", "build", str(TESTS_DIR / "dataflow.yaml"), "--uv"],
        check=True,
    )
