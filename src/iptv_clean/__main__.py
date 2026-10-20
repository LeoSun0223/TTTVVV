import argparse
from collections import Counter
import json
from pathlib import Path

from .fetch_sources import fetch_sources
from .http_client import SafeHTTP
from .normalize_channels import Channels
from .security import redact_url


def load_config(directory):
    root = Path(directory)
    sources, channels, settings = tuple(json.loads((root / name).read_text()) for name in ("sources.json", "channels.json", "settings.json"))
    if settings['min_height'] < 720:
        raise ValueError('V3 禁止低于 720P 的最低画质')
    if not 1 <= settings['workers'] <= 8 or not 1 <= settings['per_host_concurrency'] <= 2:
        raise ValueError('并发范围：全局 1～8，单主机 1～2')
    if not 0 < settings['publish_min_ratio'] <= 1 or settings['publish_min_channels'] < 1:
        raise ValueError('发布阈值无效')
    return sources, channels, settings


def main(argv=None):
    parser = argparse.ArgumentParser(description="V3 IPTV：真实检测、质量门禁；不调用 GitHub API")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--list-candidates", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--publish-local", action="store_true")
    parser.add_argument("--config-dir", default="config")
    parser.add_argument("--report-dir", default="tmp/check")
    parser.add_argument("--output-dir", default="tmp/site")
    parser.add_argument("--previous-dir", default="output")
    parser.add_argument("--channels", help="仅检测指定频道，逗号分隔；不降低发布门槛")
    parser.add_argument("--dns", choices=["system", "alidns"], default="system", help="应用内解析；不修改系统网络")
    parser.add_argument("--history-report", help="用旧报告中合格候选调整本次检测顺序；仍须全部重新验证")
    args = parser.parse_args(argv)
    try:
        sources, rows, settings = load_config(args.config_dir)
    except (OSError, ValueError, KeyError, TypeError) as e:
        print('无法加载配置：'+str(e))
        return 2
    channels = Channels(rows)
    client = SafeHTTP(settings, args.dns)
    candidates, source_reports = fetch_sources(sources, client, channels, settings)
    if args.list_candidates:
        result = {"sources": source_reports, "channel_count": len({c.channel for c in candidates}),
                  "candidate_count": len(candidates), "counts": dict(Counter(c.channel for c in candidates)),
                  "candidates": [{"channel": c.channel, "url": redact_url(c.url), "sources": c.sources} for c in candidates]}
        path = Path(args.report_dir)
        path.mkdir(parents=True, exist_ok=True)
        (path / "candidates.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({k: v for k, v in result.items() if k != "candidates"}, ensure_ascii=False, indent=2))
        return 0 if candidates else 2
    from .pipeline import run
    return run(args, candidates, source_reports, channels, settings, client)


if __name__ == "__main__":
    raise SystemExit(main())
