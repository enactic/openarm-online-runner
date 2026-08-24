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

"""Tests for dataflow."""

import os
import subprocess

from openarm_online_runner import dataflow


def _group_exists(pgid):
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False


def test_shutdown_kills_process_group():
    """shutdown() kills the running leader and its workers."""
    proc = subprocess.Popen(["bash", "-c", "sleep 60 & wait"], start_new_session=True)
    dataflow.shutdown(proc)
    assert proc.poll() is not None
    assert not _group_exists(proc.pid)


def test_shutdown_kills_orphaned_workers():
    """shutdown() kills workers left behind after the leader exited."""
    proc = subprocess.Popen(["bash", "-c", "sleep 60 & disown"], start_new_session=True)
    proc.wait()
    dataflow.shutdown(proc)
    assert not _group_exists(proc.pid)


def test_shutdown_after_exit():
    """shutdown() is a no-op when everything already exited."""
    proc = subprocess.Popen(["true"], start_new_session=True)
    proc.wait()
    dataflow.shutdown(proc)
    assert not _group_exists(proc.pid)
