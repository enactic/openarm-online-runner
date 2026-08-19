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

"""Evaluate a policy server."""

import os
import signal
import subprocess
import time
from pathlib import Path

from openarm_dataset import Dataset

from .config import logger, settings

NODE_NAME_PATTERN = "dora-openarm|opencv-video-capture"

# The dora-openarm-docker-policy-server node can be especially slow to start,
# so we add this as overhead to the timeout.
# We use 60 seconds for now, but a better value may exist.
DORA_OVERHEAD_WAIT = 60

EVALUATE_PHASE = "evaluate"
RESET_PHASE = "reset"


def _recording_name(job, phase):
    return f"{phase}-{job['job_id']}"


def recording_directory(job, phase):
    """Path of the dataset the recorder writes while evaluating/resetting a job."""
    return Path(settings.RECORDER_BASE_DIRECTORY) / _recording_name(job, phase)


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


def _run(phase, job, env, timeout):
    cmd = ["dora", "run", settings.DATAFLOW_FILE, "--uv"]
    logger.info("[job=%s] %s: %s", job["job_id"], phase, " ".join(cmd))

    proc = None
    wait_timeout = timeout + DORA_OVERHEAD_WAIT
    try:
        proc = subprocess.Popen(cmd, env=env, start_new_session=True)
        returncode = proc.wait(timeout=wait_timeout)
    except subprocess.TimeoutExpired:
        logger.warning(
            "[job=%s] %s timed out after %ds (timeout=%ds + overhead=%ds)",
            job["job_id"],
            phase,
            wait_timeout,
            timeout,
            DORA_OVERHEAD_WAIT,
        )
        return False
    except (OSError, subprocess.SubprocessError):
        logger.exception("[job=%s] %s: failed to run dora", job["job_id"], phase)
        return False
    finally:
        if proc is not None:
            _kill_process(proc)
        _kill_orphaned_workers()

    logger.info("[job=%s] %s finished: returncode=%d", job["job_id"], phase, returncode)
    return returncode == 0


def evaluate(job):
    """Evaluate a policy server."""
    timeout = settings.EVALUATE_TIMEOUT
    env = os.environ.copy() | {
        "IMAGE": job["docker_tag"],
        "DIRECTORY": settings.RECORDER_BASE_DIRECTORY,
        "NAME": _recording_name(job, EVALUATE_PHASE),
        "TIMEOUT": str(timeout),
    }
    return _run(EVALUATE_PHASE, job, env, timeout=timeout)


def reset(job):
    """Reset the evaluation environment."""
    timeout = settings.RESET_TIMEOUT
    env = os.environ.copy() | {
        "IMAGE": job["reset_docker_tag"],
        "DIRECTORY": settings.RECORDER_BASE_DIRECTORY,
        "NAME": _recording_name(job, RESET_PHASE),
        "TIMEOUT": str(timeout),
    }
    return _run(RESET_PHASE, job, env, timeout=timeout)


def succeeded(phase, job):
    """Whether the recorded task episode succeeded (per dataset metadata)."""
    dataset_directory = recording_directory(job, phase)
    if not dataset_directory.exists():
        return False
    try:
        dataset = Dataset(dataset_directory)
        if dataset.meta.num_episodes == 0:
            return False
        return bool(dataset.meta.episodes[0].get("success", False))
    except Exception:
        logger.exception("[job=%s] failed to read %s dataset", job["job_id"], phase)
        return False
