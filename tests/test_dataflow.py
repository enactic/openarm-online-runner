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
import sys

from openarm_online_runner import dataflow

# Stand-ins for dora and a node worker. Plain Python processes so that
# they exit on shutdown()'s first SIGINT; `bash -c "... &"` children
# would start with SIGINT ignored (POSIX) and wait for SIGKILL.
WORKER_SCRIPT = "import time; time.sleep(60)"
SPAWN_WORKER_SCRIPT = f"import subprocess, sys; subprocess.Popen([sys.executable, '-c', {WORKER_SCRIPT!r}])"


def _group_exists(pgid):
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False


def test_start_stop_after(monkeypatch):
    """start() tells dora to stop the dataflow after stop_after seconds."""
    commands = []

    def fake_popen(cmd, env, start_new_session):
        commands.append(cmd)

    monkeypatch.setattr(dataflow.subprocess, "Popen", fake_popen)
    dataflow.start("dataflow.yaml", {}, 180)
    assert commands == [
        ["dora", "run", "dataflow.yaml", "--uv", "--stop-after", "180s"]
    ]


def test_shutdown_kills_process_group():
    """shutdown() kills the running leader and its workers."""
    proc = subprocess.Popen(
        [sys.executable, "-c", f"{SPAWN_WORKER_SCRIPT}; {WORKER_SCRIPT}"],
        start_new_session=True,
    )
    dataflow.shutdown(proc)
    assert proc.poll() is not None
    assert not _group_exists(proc.pid)


def test_shutdown_kills_orphaned_workers():
    """shutdown() kills workers left behind after the leader exited."""
    proc = subprocess.Popen(
        [sys.executable, "-c", SPAWN_WORKER_SCRIPT], start_new_session=True
    )
    proc.wait()
    dataflow.shutdown(proc)
    assert not _group_exists(proc.pid)


def test_remove_logs(tmp_path):
    """remove_logs() removes the out/ directory next to the dataflow file."""
    dataflow_file = tmp_path / "dataflow.yaml"
    out = tmp_path / "out"
    run_directory = out / "01a01ceb-c97f-70e9-91e5-853944997bf2"
    run_directory.mkdir(parents=True)
    (run_directory / "log_ik.txt").write_text("log")
    (out / "dataflow.dora-session.yaml").write_text("session")

    dataflow.remove_logs(dataflow_file)

    assert not out.exists()


def test_remove_logs_without_out_directory(tmp_path):
    """remove_logs() does nothing without an out/ directory."""
    dataflow.remove_logs(tmp_path / "dataflow.yaml")


def test_shutdown_after_exit():
    """shutdown() is a no-op when everything already exited."""
    proc = subprocess.Popen(["true"], start_new_session=True)
    proc.wait()
    dataflow.shutdown(proc)
    assert not _group_exists(proc.pid)
