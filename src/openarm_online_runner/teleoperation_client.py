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

"""Teleoperation signaling client: fetch WebRTC offers and post answers."""

import requests

from .config import settings

API_TIMEOUT = 10
HEADERS = {
    "X-API-KEY": settings.OPENARM_ONLINE_API_KEY,
}


def fetch_pending_offers():
    """Fetch unanswered WebRTC offers queued for the task, oldest first."""
    url = (
        f"{settings.OPENARM_ONLINE_API_URL}"
        f"/api/v1/tasks/{settings.OPENARM_ONLINE_TASK_ID}/teleoperation/offers"
    )
    response = requests.get(url, headers=HEADERS, timeout=API_TIMEOUT)
    response.raise_for_status()
    return response.json()


def answer_offer(offer_id, sdp):
    """Post the WebRTC answer for an offer to the signaling server."""
    url = (
        f"{settings.OPENARM_ONLINE_API_URL}"
        f"/api/v1/teleoperation/offers/{offer_id}/answer"
    )
    response = requests.post(
        url, json={"sdp": sdp}, headers=HEADERS, timeout=API_TIMEOUT
    )
    response.raise_for_status()
    return response.json()
