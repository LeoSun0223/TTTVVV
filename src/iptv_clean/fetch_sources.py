from .models import Rejected
from .parse_m3u import deduplicate, parse_m3u
from .security import redact_url


def fetch_sources(sources, client, channels, settings):
    candidates, reports = [], []
    for source in sources:
        if not source.get("enabled", True):
            continue
        report = {"source": source["name"], "url": redact_url(source["url"])}
        try:
            response = client.get(source["url"], settings["max_source_bytes"])
            rows, rejected = parse_m3u(response.body.decode("utf-8-sig"), source["name"], channels)
            candidates.extend(rows)
            report.update(status="ok", candidates=len(rows), rejected=rejected, bytes=len(response.body))
        except Rejected as e:
            report.update(status="failed", reason=e.code, candidates=0)
        except UnicodeError:
            report.update(status="failed", reason="invalid_encoding", candidates=0)
        reports.append(report)
    return deduplicate(candidates), reports
