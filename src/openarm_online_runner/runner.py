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

"""Evaluates queued jobs and teleoperation offers in an OpenArm Cell as a daemon."""

import signal
import sys
import time
import shutil

from pathlib import Path

import openarm_driver

from . import converter, evaluator, job_client, teleoperation_client, teleoperator
from .config import logger, settings


def _not_ready_path():
    return Path(settings.STATE_DIRECTORY) / "not_ready"


def _mark_not_ready(job, reason):
    path = _not_ready_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    logger.warning(
        "[job=%s] cell not ready: %s; polling paused",
        job["job_id"],
        reason,
    )


def _remove_directory(job, directory):
    if not directory.exists():
        return
    logger.debug("[job=%s] removing %s", job["job_id"], directory)
    try:
        shutil.rmtree(directory)
    except Exception:
        logger.exception("[job=%s] cleanup failed %s", job["job_id"], directory)


def _cleanup_recording(job):
    _remove_directory(job, evaluator.recording_directory(job, evaluator.EVALUATE_PHASE))
    _remove_directory(job, evaluator.recording_directory(job, evaluator.RESET_PHASE))


def _stop_arms():
    for side in ("left_arm", "right_arm"):
        try:
            openarm_driver.SingleArmDriver(side).stop()
        except Exception:
            logger.exception("[arm=%s] stop failed", side)


def _run_on_cell(job):
    try:
        evaluator.evaluate(job)
        evaluator.reset(job)
    finally:
        _stop_arms()
    reset_ok = evaluator.succeeded(evaluator.RESET_PHASE, job)
    if not reset_ok:
        _mark_not_ready(job, "reset failed")
    return evaluator.succeeded(evaluator.EVALUATE_PHASE, job)


def _run_on_mujoco(job):
    evaluator.evaluate(job)
    return evaluator.succeeded(evaluator.EVALUATE_PHASE, job)


def run_job(job):
    """Execute a single job."""
    logger.debug("[job=%s] started", job["job_id"])

    try:
        if job["runtime"] == "OpenArm Cell":
            success = _run_on_cell(job)
        elif job["runtime"] == "MuJoCo":
            success = _run_on_mujoco(job)
        else:
            raise ValueError(f"unknown runtime: {job['runtime']}")

        rrd_path = converter.convert(job)
        s3_key = job_client.upload_rrd(rrd_path)
        job_client.complete_job(job["job_id"], success, s3_key)
        logger.debug("[job=%s] completed", job["job_id"])
    except (KeyboardInterrupt, SystemExit):
        logger.warning("[job=%s] interrupted", job["job_id"])
        job_client.fail_job(job["job_id"], "runner terminated")
        raise
    except Exception as err:
        logger.exception("[job=%s] failed", job["job_id"])
        job_client.fail_job(job["job_id"], str(err))
    finally:
        _cleanup_recording(job)


def run_teleoperation(offer):
    """Execute a single teleoperation session."""
    logger.debug("[offer=%s] teleoperation started", offer["id"])

    try:
        teleoperator.teleoperate(
            offer,
            lambda sdp: teleoperation_client.answer_offer(offer["id"], sdp),
        )
        logger.debug("[offer=%s] teleoperation ended", offer["id"])
    except Exception:
        logger.exception("[offer=%s] teleoperation failed", offer["id"])
    finally:
        # Real arms move only on OpenArm Cell.
        if offer["runtime"] == "OpenArm Cell":
            _stop_arms()


def _next_offer():
    """Return the oldest pending teleoperation offer across all tasks."""
    for task_id in settings.OPENARM_ONLINE_TASK_IDS:
        offers = teleoperation_client.fetch_pending_offers(task_id)
        if offers:
            return offers[0]
    return None


def _next_job():
    """Claim the next queued job across all tasks."""
    for task_id in settings.OPENARM_ONLINE_TASK_IDS:
        job = job_client.fetch_next(task_id)
        if job is not None:
            return job
    return None


def _terminate(signum, frame):
    """Raise SystemExit so that in-flight finally blocks run."""
    # A second SIGTERM aborts the cleanup and kills us the default
    # way, so a stuck cleanup can't block termination forever.
    signal.signal(signum, signal.SIG_DFL)
    sys.exit()


def main():
    """Poll for teleoperation offers and jobs and execute them."""
    signal.signal(signal.SIGTERM, _terminate)
    logger.info("started (poll_interval=%ds)", settings.POLL_INTERVAL)
    paused = False
    while True:
        if _not_ready_path().exists():
            if not paused:
                logger.warning(
                    "paused: cell is not ready; remove %s to resume", _not_ready_path()
                )
                paused = True
            time.sleep(settings.POLL_INTERVAL)
            continue
        if not settings.is_active_time():
            if not paused:
                logger.warning("outside active time")
                paused = True
            time.sleep(settings.POLL_INTERVAL)
            continue

        if paused:
            logger.info("resumed polling")
            paused = False

        # A browser user is waiting for a teleoperation session, so
        # offers take priority over queued jobs.
        offer = _next_offer()
        if offer is not None:
            run_teleoperation(offer)
            continue

        job = _next_job()
        if job is None:
            time.sleep(settings.POLL_INTERVAL)
            continue
        run_job(job)


if __name__ == "__main__":
    main()
