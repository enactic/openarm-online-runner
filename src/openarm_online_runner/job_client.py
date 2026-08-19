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

"""Job server client: fetch job and upload `.rrd` file."""

import requests

from .config import settings

API_TIMEOUT = 10
HEADERS = {
    "X-API-KEY": settings.OPENARM_ONLINE_API_KEY,
}


def fetch_next():
    """Fetch job from the job server."""
    url = f"{settings.OPENARM_ONLINE_API_URL}/api/v1/tasks/{settings.OPENARM_ONLINE_TASK_ID}/jobs/claim"
    response = requests.post(url, headers=HEADERS, timeout=API_TIMEOUT)
    response.raise_for_status()
    return response.json()


def complete_job(job_id, success, s3_key):
    """Report job completion to the job server."""
    url = f"{settings.OPENARM_ONLINE_API_URL}/api/v1/jobs/{job_id}/complete"
    response = requests.post(
        url,
        json={"success": success, "s3_key": s3_key},
        headers=HEADERS,
        timeout=API_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def fail_job(job_id, reason):
    """Report job failure to the job server."""
    url = f"{settings.OPENARM_ONLINE_API_URL}/api/v1/jobs/{job_id}/fail"
    response = requests.post(
        url, json={"reason": reason}, headers=HEADERS, timeout=API_TIMEOUT
    )
    response.raise_for_status()
    return response.json()


def upload_rrd(path):
    """Upload `.rrd` file to the job server."""
    url = f"{settings.OPENARM_ONLINE_API_URL}/api/v1/rrd/upload-url"
    response = requests.get(url, headers=HEADERS, timeout=API_TIMEOUT)
    response.raise_for_status()
    upload_info = response.json()

    with open(path, "rb") as f:
        requests.put(upload_info["url"], data=f, timeout=300).raise_for_status()

    return upload_info["s3_key"]
