import hashlib
import math
import time
from urllib.parse import urlsplit

from .hls import get_media, parse_hls
from .models import Rejected
from .probe_video import probe_video
from .security import redact_url


class Validator:
    def __init__(self, client, settings, sleep=time.sleep, clock=time.monotonic, probe=probe_video):
        self.client, self.settings = client, settings
        self.sleep, self.clock, self.probe = sleep, clock, probe

    def precheck(self, candidate):
        return get_media(self.client, candidate.url, self.settings)

    def validate(self, candidate):
        started = self.clock()
        result = {"channel": candidate.channel, "url": redact_url(candidate.url), "sources": candidate.sources,
                  "reachable": False, "live_progress_ok": False, "segment_ok": False,
                  "resolution_verified": False, "final_status": "rejected", "snapshots": [],
                  "segments": [], "phase": "deep"}
        consumed = 0
        def download(segment):
            nonlocal consumed
            response = self.client.get(segment.url, self.settings["max_segment_bytes"], byte_range=segment.byte_range)
            body = response.body
            consumed += len(body)
            if segment.init:
                init = self.client.get(segment.init[0], self.settings["max_playlist_bytes"], byte_range=segment.init[1])
                consumed += len(init.body)
                body = init.body + body
            if consumed > self.settings["max_candidate_bytes"]:
                raise Rejected("download_budget_exceeded")
            video = self.probe(body, self.settings["probe_timeout"])
            result["segments"].append({"url": redact_url(response.url), "sequence": segment.sequence,
                "duration": segment.duration, "bytes": len(response.body), "elapsed_seconds": round(response.elapsed, 3),
                "throughput_mbps": round(len(response.body) * 8 / max(response.elapsed, 0.001) / 1e6, 3),
                "sha256": hashlib.sha256(response.body).hexdigest(), "ips": response.ips, **video})
            if video["height"] < self.settings["min_height"]:
                raise Rejected("resolution_below_minimum")
            if response.elapsed >= segment.duration:
                raise Rejected("segment_too_slow")
            return video, hashlib.sha256(response.body).hexdigest()

        try:
            # Always refresh after a queued precheck: never reuse stale initial state.
            playlist, response = self.precheck(candidate)
            result.update(reachable=True, http_status=response.status, ttfb_seconds=round(response.ttfb, 3),
                          resolved_url=redact_url(response.url), resolved_host=urlsplit(response.url).hostname,
                          resolved_ips=response.ips, target_duration=playlist.target)
            def snapshot(p):
                result["snapshots"].append({"at_seconds": round(self.clock() - observation_start, 3),
                    "media_sequence": p.sequence, "last_sequence": p.segments[-1].sequence,
                    "last_segment": redact_url(p.segments[-1].url), "segment_count": len(p.segments)})
            first = playlist.segments[-1]
            first_video, first_hash = download(first)
            observation_start = self.clock()
            snapshot(playlist)
            window = max(self.settings["min_observation_seconds"], min(self.settings["max_observation_seconds"], playlist.target * 3))
            intervals = max(self.settings["min_poll_intervals"], math.ceil(window / max(2, min(playlist.target, 15))))
            previous = playlist
            advances = 0
            latest_advance = -1
            for i in range(intervals):
                self.sleep(max(0, observation_start + (i + 1) * window / intervals - self.clock()))
                polled = self.client.get(playlist.url, self.settings["max_playlist_bytes"])
                current = parse_hls(polled.body, polled.url)
                if current.variants:
                    raise Rejected("media_became_master")
                snapshot(current)
                if current.sequence < previous.sequence:
                    raise Rejected("sequence_regression")
                # A sequence counter or a rotating signature alone is insufficient.
                old = {s.identity() for s in previous.segments}
                if current.segments[-1].identity() not in old:
                    advances += 1
                    latest_advance = i
                previous = current
            result["observation_seconds"] = round(self.clock() - observation_start, 3)
            if advances < 2 or latest_advance < intervals - 2 or previous.segments[-1].identity() == first.identity():
                raise Rejected("frozen_playlist")
            result["live_progress_ok"] = True
            second_video, second_hash = download(previous.segments[-1])
            if first_hash == second_hash:
                raise Rejected("repeated_segment")
            result.update(segment_ok=True, resolution_verified=True, final_status="passed", reason="ok",
                          width=min(first_video["width"], second_video["width"]),
                          height=min(first_video["height"], second_video["height"]), advances=advances)
        except Rejected as e:
            result["reason"] = e.code
        result["elapsed_seconds"] = round(self.clock() - started, 3)
        result["download_bytes"] = consumed
        return result
