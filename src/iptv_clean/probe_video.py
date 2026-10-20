import json
from pathlib import Path
import subprocess
import tempfile

from .models import Rejected


def media_format(body):
    # MPEG-TS sync bytes (allow an ID3 prefix); ISO BMFF boxes for fMP4.
    for offset in range(min(1024, max(0, len(body) - 376))):
        if body[offset] == 0x47 and body[offset + 188] == 0x47 and body[offset + 376] == 0x47:
            return "mpegts"
    if len(body) >= 16 and body[4:8] in (b"ftyp", b"styp", b"moof"):
        return "mov"
    raise Rejected("invalid_segment_media")


def probe_video(body, timeout=12):
    fmt = media_format(body)
    with tempfile.TemporaryDirectory(prefix="iptv-probe-") as directory:
        path = Path(directory) / ("sample.ts" if fmt == "mpegts" else "sample.mp4")
        path.write_bytes(body)
        try:
            process = subprocess.run([
                "ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe", "-f", fmt,
                "-probesize", "12000000", "-analyzeduration", "8000000", "-select_streams", "v:0",
                "-show_entries", "stream=width,height,codec_name", "-of", "json", str(path)
            ], capture_output=True, timeout=timeout, check=False)
        except FileNotFoundError:
            raise Rejected("ffprobe_missing") from None
        except subprocess.TimeoutExpired:
            raise Rejected("ffprobe_timeout") from None
        try:
            streams = json.loads(process.stdout).get("streams", [])
            if process.returncode or not streams:
                raise ValueError()
            stream = streams[0]
            width, height = int(stream.get("width", 0)), int(stream.get("height", 0))
            if width <= 0 or height <= 0:
                raise ValueError()
            return {"width": width, "height": height, "codec": stream.get("codec_name", "unknown")}
        except (ValueError, KeyError, TypeError):
            raise Rejected("resolution_unknown") from None
