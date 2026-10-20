from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import time

from .models import Rejected
from .publish_gate import load_previous, publish_gate
from .render_outputs import write_site
from .security import redact_url
from .select_streams import fair_candidates, independent, select_streams
from .validate_hls import Validator


def candidate_id(candidate):
    return hashlib.sha256((candidate.channel + '\n' + candidate.url).encode()).hexdigest()[:24]


def run(args, candidates, source_reports, channels, settings, client):
    started = time.monotonic()
    wanted = set(args.channels.split(',')) if args.channels else set(channels.rows)
    unknown = wanted - channels.rows.keys()
    if unknown:
        print('未知频道：'+','.join(sorted(unknown)))
        return 2
    try:
        previous = load_previous(args.previous_dir)
    except Rejected as e:
        print(e.code + '：上次成功版本无法读取，停止更新。')
        return 2
    grouped = defaultdict(list)
    candidate_map = {candidate_id(c): c for c in candidates}
    for candidate in candidates:
        if candidate.channel in wanted:
            grouped[candidate.channel].append(candidate)
    priority = settings['priority_channels']
    history = previous
    if getattr(args,'history_report',None):
        try:
            history = json.loads(Path(args.history_report).read_text())
        except (OSError,ValueError):
            print('无法读取历史报告；未开始检测。')
            return 2
    history_ids = {key for ids in (history or {}).get('selected',{}).values() for key in ids}
    order = sorted(wanted, key=lambda c: (priority.index(c) if c in priority else len(priority), list(channels.rows).index(c)))
    deadline = started + settings['run_budget_seconds']
    if client is not None:
        client.deadline = deadline
    def check_channel(channel):
        validator = Validator(client, settings)
        results, deep, passed = [], 0, []
        ordered = sorted(fair_candidates(grouped[channel]),key=lambda c:candidate_id(c) not in history_ids)
        for index, candidate in enumerate(ordered):
            row = {'candidate_id':candidate_id(candidate),'channel':channel,'url':redact_url(candidate.url),
                   'sources':candidate.sources,'final_status':'not_tested','reachable':False,'live_progress_ok':False,
                   'segment_ok':False,'resolution_verified':False}
            if time.monotonic() + settings['max_observation_seconds'] + settings['probe_timeout'] + 3*settings['http_timeout'] > deadline:
                row['reason'] = 'run_budget_exhausted'
            elif index >= settings['max_precheck_per_channel']:
                row['reason'] = 'precheck_limit'
            elif deep >= settings['max_deep_per_channel']:
                row['reason'] = 'deep_limit'
            elif len(passed) >= 2 and independent(passed[0],passed[1]):
                row['reason'] = 'enough_independent_routes'
            else:
                tick = time.monotonic()
                try:
                    validator.precheck(candidate)
                    deep += 1
                    row = {**validator.validate(candidate), 'candidate_id':candidate_id(candidate)}
                    if row['final_status'] == 'passed':
                        passed.append(row)
                except Rejected as e:
                    row.update(final_status='rejected',reason=e.code,phase='precheck',elapsed_seconds=round(time.monotonic()-tick,3))
                print(channel+' '+row['final_status']+' '+row['reason'], flush=True)
            results.append(row)
        return results
    results = []
    with ThreadPoolExecutor(max_workers=settings['workers']) as pool:
        futures = [pool.submit(check_channel, channel) for channel in order]
        for future in as_completed(futures):
            results.extend(future.result())
    selected = select_streams(results)
    gate = publish_gate(selected, channels, settings, previous)
    report = {'schema_version':1,'generated_at':datetime.now(timezone.utc).isoformat(),
              'status':'validation_passed' if gate['allowed'] else 'not_publishable',
              'publication_note':'检测通过不等于已发布；Pages 部署结果及 output/_deployment.json 为发布证据',
              'environment':{'location':'github-actions' if os.environ.get('GITHUB_ACTIONS') == 'true' else 'local-mac' if platform.system() == 'Darwin' else 'local',
                             'dns':args.dns,'platform':platform.system(),'python':platform.python_version(),
                             'network_claim':'仅代表本次设备的实际网络路径；不代表杭州电信电视验收'},
              'elapsed_seconds':round(time.monotonic()-started,3),'sources':source_reports,
              'http_download_bytes':getattr(client,'total_bytes',None),
              'max_run_bytes':settings['max_run_bytes'],
              'history_candidates_prioritized':len(history_ids & candidate_map.keys()),
              'candidate_count':len(candidates),'tested_candidates':sum(r['final_status'] != 'not_tested' for r in results),
              'deep_checked':sum(r.get('phase') == 'deep' for r in results),
              'qualified_channels':len(selected),'qualified_routes':sum(len(v) for v in selected.values()),
              'reason_counts':dict(Counter(r['reason'] for r in results)),
              'selected':{c:[r['candidate_id'] for r in choices] for c,choices in selected.items()},
              'missing_channels':[c for c in channels.rows if c not in selected],
              'out_of_run_scope':[c for c in channels.rows if c not in wanted],
              'publish_gate':gate,'candidates':sorted(results,key=lambda r:(list(channels.rows).index(r['channel']),r['candidate_id']))}
    report_dir = Path(args.report_dir)
    # A diagnostic report must never overwrite the public version's report.json.
    destinations = [Path(args.output_dir).resolve(), Path(args.previous_dir).resolve()]
    if report_dir.resolve() in destinations:
        print('诊断目录不能等于产物目录或旧版目录。')
        return 2
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    (report_dir/'summary.md').write_text('# 真实网络检测\n\n'+str(report['environment'])+'\n\n合格频道：'+str(len(selected))+'；检测候选：'+str(report['tested_candidates'])+'；发布门禁：'+gate['reason']+'\n\n'+ '\n'.join('- '+c+'：'+(', '.join(sorted({r['reason'] for r in results if r['channel']==c})) or 'no_candidates') for c in order)+'\n')
    print(json.dumps({k:report[k] for k in ['qualified_channels','qualified_routes','tested_candidates','deep_checked','reason_counts','publish_gate']},ensure_ascii=False,indent=2))
    if not gate['allowed']:
        print('尚无可订阅的可信新列表；未覆盖上次成功版本。')
        return 2
    if args.publish_local:
        if Path(args.output_dir).resolve() == Path(args.previous_dir).resolve():
            print('产物必须先生成到独立目录；output/ 只归档已发布版本。')
            return 2
        write_site(args.output_dir, selected, channels, candidate_map, report)
        print('本地静态产物已生成；尚未远程发布。')
    return 0
