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

"""Convert recorder output to rerun.io `.rrd` format."""

from openarm_dataset import Dataset

from . import evaluator
from .config import logger, settings


def convert(job):
    """Convert recorder output to rerun.io `.rrd` format."""
    dataset_dir = evaluator.recording_directory(job, evaluator.EVALUATE_PHASE)
    if not dataset_dir.is_dir():
        raise FileNotFoundError(f"Recording directory not found: {dataset_dir}")

    rrd_path = dataset_dir / "output.rrd"
    logger.debug("[job=%s] converting %s -> %s", job["job_id"], dataset_dir, rrd_path)
    Dataset(dataset_dir).write(rrd_path, "rrd", fps=settings.RRD_FPS)

    return rrd_path
