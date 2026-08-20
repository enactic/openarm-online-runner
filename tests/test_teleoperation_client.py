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

"""Tests for teleoperation_client."""

import json

import responses

from openarm_online_runner import teleoperation_client
from openarm_online_runner.config import settings

API_URL = settings.OPENARM_ONLINE_API_URL
TASK_ID = settings.OPENARM_ONLINE_TASK_ID


@responses.activate
def test_fetch_pending_offers_returns_offers():
    """fetch_pending_offers() returns the offer dicts."""
    offers = [
        {"id": 1, "task_id": TASK_ID, "sdp": "offer-sdp-1"},
        {"id": 2, "task_id": TASK_ID, "sdp": "offer-sdp-2"},
    ]
    responses.add(
        responses.GET,
        f"{API_URL}/api/v1/tasks/{TASK_ID}/teleoperation/offers",
        json=offers,
    )

    assert teleoperation_client.fetch_pending_offers() == offers


@responses.activate
def test_fetch_pending_offers_returns_empty():
    """fetch_pending_offers() returns an empty list without offers."""
    responses.add(
        responses.GET,
        f"{API_URL}/api/v1/tasks/{TASK_ID}/teleoperation/offers",
        json=[],
    )

    assert teleoperation_client.fetch_pending_offers() == []


@responses.activate
def test_answer_offer():
    """answer_offer() posts the answer SDP to the server."""
    answer = {"id": 1, "offer_id": 1, "sdp": "answer-sdp"}
    responses.add(
        responses.POST, f"{API_URL}/api/v1/teleoperation/offers/1/answer", json=answer
    )

    assert teleoperation_client.answer_offer(1, "answer-sdp") == answer
    assert json.loads(responses.calls[0].request.body) == {"sdp": "answer-sdp"}
