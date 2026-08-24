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

"""Tests for job_client."""

import json

import responses

from openarm_online_runner import job_client
from openarm_online_runner.config import settings

API_URL = settings.OPENARM_ONLINE_API_URL
TASK_ID = settings.OPENARM_ONLINE_TASK_IDS[0]


@responses.activate
def test_fetch_next_returns_job():
    """fetch_next() returns the job dict."""
    job = {
        "job_id": 1,
        "docker_tag": "image:latest",
        "reset_docker_tag": "reset:latest",
    }
    responses.add(
        responses.POST, f"{API_URL}/api/v1/tasks/{TASK_ID}/jobs/claim", json=job
    )

    assert job_client.fetch_next(TASK_ID) == job


@responses.activate
def test_fetch_next_returns_none():
    """fetch_next() returns None."""
    responses.add(
        responses.POST,
        f"{API_URL}/api/v1/tasks/{TASK_ID}/jobs/claim",
        body="null",
        content_type="application/json",
    )

    assert job_client.fetch_next(TASK_ID) is None


@responses.activate
def test_complete_job():
    """complete_job() posts success and s3_key to the server."""
    rollout = {"id": 1, "submission_id": 1, "success": True, "s3_key": "rrd/abc.rrd"}
    responses.add(responses.POST, f"{API_URL}/api/v1/jobs/1/complete", json=rollout)

    assert job_client.complete_job(1, True, "rrd/abc.rrd") == rollout
    assert json.loads(responses.calls[0].request.body) == {
        "success": True,
        "s3_key": "rrd/abc.rrd",
    }


@responses.activate
def test_fail_job():
    """fail_job() posts the failure reason to the server."""
    failure = {"id": 1, "submission_id": 1, "reason": "timeout"}
    responses.add(responses.POST, f"{API_URL}/api/v1/jobs/1/fail", json=failure)

    assert job_client.fail_job(1, "timeout") == failure
    assert json.loads(responses.calls[0].request.body) == {"reason": "timeout"}


@responses.activate
def test_upload_rrd(tmp_path):
    """upload_rrd() fetches a presigned URL and uploads the file."""
    rrd_file = tmp_path / "dummy.rrd"
    rrd_file.write_bytes(b"dummy")

    upload_info = {
        "url": "http://s3:9000/openarm-online/rrd/abc.rrd?presigned",
        "s3_key": "rrd/upload.rrd",
    }
    responses.add(responses.GET, f"{API_URL}/api/v1/rrd/upload-url", json=upload_info)
    responses.add(responses.PUT, upload_info["url"])

    assert job_client.upload_rrd(rrd_file) == "rrd/upload.rrd"
