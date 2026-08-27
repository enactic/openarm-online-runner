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
import shutil
import signal
import subprocess
import time
from pathlib import Path

from dotenv import dotenv_values

from .config import logger

# Wait time for all nodes in the dataflow to start. The
# dora-openarm-docker-policy-server node can be especially slow to
# start. We use 60 seconds for now, but a better value may exist.
START_WAIT = 60

# Wait time from when dora starts stopping the dataflow until all of
# its nodes actually exit. Stopping the
# dora-openarm-docker-policy-server node's container may take some
# time. We use 30 seconds for now, but a better value may exist.
STOP_WAIT = 30


def base_env(env_file):
    """Build the base environment for a dataflow.

    The dataflow's .env file, if any, wins over the inherited
    environment.
    """
    env = os.environ.copy()
    if env_file is not None:
        env |= {
            name: value
            for name, value in dotenv_values(env_file).items()
            if value is not None
        }
    return env


def start(dataflow_file, env, stop_after):
    """Start `dora run` for the dataflow in its own process group.

    dora gracefully stops the dataflow by itself after stop_after
    seconds.
    """
    cmd = ["dora", "run", dataflow_file, "--uv", "--stop-after", f"{stop_after}s"]
    logger.info("starting dataflow: %s", " ".join(cmd))
    return subprocess.Popen(cmd, env=env, start_new_session=True)


def _kill_group(pgid, sig):
    """os.killpg() but return False if the group no longer exists."""
    try:
        os.killpg(pgid, sig)
        return True
    except ProcessLookupError:
        return False
    except OSError as err:
        logger.debug("killpg(%d, %d) failed: %s", pgid, sig, err)
        return False


def _group_exists(pgid):
    """Whether any process in the group is still alive."""
    return _kill_group(pgid, 0)


def _wait_group(proc, pgid, timeout):
    """Wait until the process group is empty; return False on timeout."""
    deadline = time.monotonic() + timeout
    while True:
        # Reap dora itself so that only live node workers keep the
        # group alive.
        proc.poll()
        if not _group_exists(pgid):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.1)


def remove_logs(dataflow_file):
    """Remove the out/ directory `dora run` leaves next to the dataflow file."""
    out_directory = Path(dataflow_file).parent / "out"
    if not out_directory.exists():
        return
    logger.debug("removing dataflow logs: %s", out_directory)
    try:
        shutil.rmtree(out_directory)
    except OSError:
        logger.exception("failed to remove dataflow logs: %s", out_directory)


def shutdown(proc):
    """Stop the dataflow via dora, killing dora as the last resort.

    start() runs dora in its own session, so signaling the process
    group whose ID is dora's PID doesn't touch unrelated processes.

    dora treats SIGINT like Ctrl-C: the first one stops the dataflow
    gracefully and the second one exits early but still reaps the
    nodes. We don't use SIGTERM because dora 0.5.0 doesn't handle it:
    it just dies, orphaning its nodes, which are process group leaders
    of their own. dora 1.0.0 should handle SIGTERM like Ctrl-C in
    `dora run` (dora-rs/dora#2949), but SIGINT works with both.
    SIGKILL orphans the nodes, so it's the last resort.
    """
    pgid = proc.pid
    for sig, timeout in [
        (signal.SIGINT, STOP_WAIT),
        (signal.SIGINT, 5),
        (signal.SIGKILL, 3),
    ]:
        if not _kill_group(pgid, sig):
            return
        logger.info("sent %s to dataflow process group (pgid=%d)", sig.name, pgid)
        if _wait_group(proc, pgid, timeout):
            return
        logger.warning("shutdown: dataflow did not exit after %s", sig.name)
