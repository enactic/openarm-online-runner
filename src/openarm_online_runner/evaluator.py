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

import subprocess
from pathlib import Path

from openarm_dataset import Dataset

from . import dataflow
from .config import logger, settings

EVALUATE_PHASE = "evaluate"
RESET_PHASE = "reset"


def _recording_name(job, phase):
    return f"{phase}-{job['job_id']}"


def recording_directory(job, phase):
    """Path of the dataset the recorder writes while evaluating/resetting a job."""
    return Path(settings.RECORDER_BASE_DIRECTORY) / _recording_name(job, phase)


def _run(phase, job, env, timeout):
    dataflow_file = settings.dataflow_file(job["task_id"])
    logger.info("[job=%s] %s: %s", job["job_id"], phase, dataflow_file)

    # dora stops the dataflow by itself after stop_after seconds, so
    # hitting wait_timeout means that dora failed to do so.
    stop_after = timeout + dataflow.START_WAIT
    wait_timeout = stop_after + dataflow.STOP_WAIT
    try:
        proc = dataflow.start(dataflow_file, env, stop_after)
    except (OSError, subprocess.SubprocessError):
        logger.exception("[job=%s] %s: failed to run dora", job["job_id"], phase)
        return False
    try:
        returncode = proc.wait(timeout=wait_timeout)
    except subprocess.TimeoutExpired:
        logger.warning(
            "[job=%s] %s: dora didn't stop the dataflow by itself after %ds "
            "(stop_after=%ds)",
            job["job_id"],
            phase,
            wait_timeout,
            stop_after,
        )
        return False
    finally:
        dataflow.shutdown(proc)
        dataflow.remove_logs(dataflow_file)

    logger.info("[job=%s] %s finished: returncode=%d", job["job_id"], phase, returncode)
    return returncode == 0


def _base_env(job):
    """Environment for the job's dataflow."""
    return dataflow.base_env(settings.dataflow_env_file(job["task_id"]))


def evaluate(job):
    """Evaluate a policy server."""
    timeout = settings.EVALUATE_TIMEOUT
    env = _base_env(job) | {
        "IMAGE": job["docker_tag"],
        "DIRECTORY": settings.RECORDER_BASE_DIRECTORY,
        "NAME": _recording_name(job, EVALUATE_PHASE),
        "TIMEOUT": str(timeout),
    }
    return _run(EVALUATE_PHASE, job, env, timeout=timeout)


def reset(job):
    """Reset the evaluation environment."""
    timeout = settings.RESET_TIMEOUT
    env = _base_env(job) | {
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
    except Exception:  # noqa: BLE001
        logger.exception("[job=%s] failed to read %s dataset", job["job_id"], phase)
        return False
