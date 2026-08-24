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

"""Teleoperate the cell from a Web browser over WebRTC."""

import os
import socket
import subprocess

from . import dataflow
from .config import logger, settings


def _receive_answer(listener, timeout):
    """Accept the keyboard node's TCP connection and read the bare answer SDP."""
    listener.settimeout(timeout)
    conn, _addr = listener.accept()
    chunks = []
    with conn:
        conn.settimeout(timeout)
        while chunk := conn.recv(4096):
            chunks.append(chunk)
    return b"".join(chunks).decode("utf-8")


def teleoperate(offer, send_answer):
    """Run the teleoperation dataflow for a single WebRTC offer.

    The dataflow's dora-openarm-keyboard node runs in WebRTC-only mode: the
    browser's offer SDP goes in through the OFFER environment variable and
    the node writes its answer SDP back over TCP to ANSWER_HOST/ANSWER_PORT.
    The answer is relayed to the signaling server with send_answer(sdp), the
    browser applies it, and the session then runs until the dataflow exits
    or TELEOPERATE_TIMEOUT passes.
    """
    offer_id = offer["id"]
    timeout = settings.TELEOPERATE_TIMEOUT
    with socket.create_server(("127.0.0.1", 0)) as listener:
        env = os.environ.copy() | {
            "OFFER": offer["sdp"],
            "ANSWER_HOST": "127.0.0.1",
            "ANSWER_PORT": str(listener.getsockname()[1]),
            "TIMEOUT": str(timeout),
        }
        try:
            proc = dataflow.start(settings.TELEOPERATION_DATAFLOW_FILE, env)
        except (OSError, subprocess.SubprocessError):
            logger.exception("[offer=%s] failed to run dora", offer_id)
            return False
        try:
            try:
                answer = _receive_answer(listener, dataflow.OVERHEAD_WAIT)
            except TimeoutError:
                logger.warning(
                    "[offer=%s] no answer SDP within %ds",
                    offer_id,
                    dataflow.OVERHEAD_WAIT,
                )
                return False
            send_answer(answer)
            try:
                returncode = proc.wait(timeout=timeout + dataflow.OVERHEAD_WAIT)
            except subprocess.TimeoutExpired:
                logger.warning(
                    "[offer=%s] teleoperation timed out after %ds "
                    "(timeout=%ds + overhead=%ds)",
                    offer_id,
                    timeout + dataflow.OVERHEAD_WAIT,
                    timeout,
                    dataflow.OVERHEAD_WAIT,
                )
                return False
        finally:
            dataflow.shutdown(proc)

    logger.info(
        "[offer=%s] teleoperation finished: returncode=%d", offer_id, returncode
    )
    return returncode == 0
