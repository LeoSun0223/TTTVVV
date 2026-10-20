import json
import shutil
import subprocess
from pathlib import Path

import pytest

from iptv_clean.normalize_channels import Channels

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def settings():
    return json.loads((ROOT / "config/settings.json").read_text())


@pytest.fixture
def channels():
    return Channels(json.loads((ROOT / "config/channels.json").read_text()))


@pytest.fixture(scope="session")
def media_samples(tmp_path_factory):
    # Real encoded samples for ffprobe; never downloaded from a live source.
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.fail("M2 tests require ffmpeg and ffprobe installed")
    directory = tmp_path_factory.mktemp("samples")
    result = {}
    for name, size, color in [("hd_a", "1920x1080", "red"), ("hd_b", "1920x1080", "blue"), ("sd", "640x360", "green")]:
        path = directory / (name + ".ts")
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c={}:s={}:r=25".format(color, size),
                        "-t", "0.5", "-c:v", "mpeg2video", "-f", "mpegts", str(path)],
                       check=True, capture_output=True, timeout=15)
        result[name] = path.read_bytes()
    return result
