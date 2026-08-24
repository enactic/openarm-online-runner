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

# Wait time for all nodes in the dataflow to start. The
# dora-openarm-docker-policy-server node can be especially slow to
# start. We use 60 seconds for now, but a better value may exist.
START_WAIT = 60

# Wait time from when dora starts stopping the dataflow until all of
# its nodes actually exit. Stopping the
# dora-openarm-docker-policy-server node's container may take some
# time. We use 30 seconds for now, but a better value may exist.
STOP_WAIT = 30


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


def shutdown(proc):
    """Kill the dataflow process group.

    start() runs dora in its own session, so dora and all of its node
    workers share the process group whose ID is dora's PID. Signaling
    the group reaches node workers even after dora itself has exited,
    without touching unrelated processes.
    """
    pgid = proc.pid
    for sig, timeout in [(signal.SIGTERM, 5), (signal.SIGKILL, 3)]:
        if not _kill_group(pgid, sig):
            return
        logger.info("sent %s to dataflow process group (pgid=%d)", sig.name, pgid)
        if _wait_group(proc, pgid, timeout):
            return
        logger.warning("shutdown: dataflow did not exit after %s", sig.name)
