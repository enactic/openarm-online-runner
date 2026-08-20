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

"""Run dora dataflows as supervised subprocesses."""

import os
import signal
import subprocess
import time

from .config import logger

NODE_NAME_PATTERN = "dora-openarm|opencv-video-capture"

# The dora-openarm-docker-policy-server node can be especially slow to start,
# so we add this as overhead to the timeout.
# We use 60 seconds for now, but a better value may exist.
OVERHEAD_WAIT = 60


def start(dataflow_file, env):
    """Start `dora run` for the dataflow in its own process group."""
    cmd = ["dora", "run", dataflow_file, "--uv"]
    logger.info("starting dataflow: %s", " ".join(cmd))
    return subprocess.Popen(cmd, env=env, start_new_session=True)


def _kill(pgid, sig, fallback):
    try:
        os.killpg(pgid, sig)
    except (ProcessLookupError, OSError):
        try:
            fallback()
        except OSError as err:
            logger.debug("kill failed: %s", err)


def _kill_process(proc):
    if proc.poll() is not None:
        return

    pid = proc.pid
    logger.info("Killing dora process (pid=%d)", pid)

    for sig, fallback, timeout in [
        (signal.SIGTERM, proc.terminate, 5),
        (signal.SIGKILL, proc.kill, 3),
    ]:
        _kill(pid, sig, fallback)
        try:
            proc.wait(timeout=timeout)
            return
        except subprocess.TimeoutExpired:
            logger.warning("kill_process: dora did not exit after %s", sig.name)


def _pgrep():
    try:
        subprocess.run(
            ["pgrep", "-f", NODE_NAME_PATTERN], check=True, capture_output=True
        )
        return True
    except subprocess.CalledProcessError as err:
        logger.debug("pgrep failed: %s", err)
        return False


def _pkill(sig):
    cmd = ["pkill", f"-{sig.value}", "-f", NODE_NAME_PATTERN]
    try:
        subprocess.run(cmd, timeout=5, check=True, capture_output=True)
    except subprocess.CalledProcessError as err:
        logger.debug("pkill failed: %s", err)


def _kill_orphaned_workers():
    if not _pgrep():
        return
    _pkill(signal.SIGTERM)
    if not _pgrep():
        return
    time.sleep(2)
    _pkill(signal.SIGKILL)


def shutdown(proc):
    """Kill the dataflow process, if any, and any orphaned node workers."""
    if proc is not None:
        _kill_process(proc)
    _kill_orphaned_workers()
