import html
import json
import os
from pathlib import Path
import shutil
import tempfile

from .models import Rejected
from .security import canonical_url


def safe_attr(value):
    return str(value).replace('"', '').replace('\n', '').replace('\r', '').replace('<','').replace('>','')


def render_m3u(selected, channels, candidates, backup=False):
    lines = ['#EXTM3U']
    # Keep group blocks contiguous so TV players show clear primary/backup sections.
    for group in ['央视','卫视']:
        for route in range(2 if backup else 1):
            for name, row in channels.rows.items():
                choices = selected.get(name, [])
                if row['group'] != group or route >= len(choices):
                    continue
                result = choices[route]
                candidate = candidates[result['candidate_id']]
                url = canonical_url(candidate.url)
                group_title = group + ('-备用' if route else '-主线') if backup else group
                title = name + (' (备用)' if route else '')
                # Canonical tvg-id avoids a wrong upstream identifier merging channels.
                attrs = ['tvg-id="{}"'.format(safe_attr(name)), 'tvg-name="{}"'.format(safe_attr(name))]
                logo = candidate.attrs.get('tvg-logo', '')
                if logo:
                    try:
                        logo = canonical_url(logo)
                        from .security import has_credentials
                        if not has_credentials(logo):
                            attrs.append('tvg-logo="{}"'.format(safe_attr(logo)))
                    except Rejected:
                        pass
                attrs.append('group-title="{}"'.format(group_title))
                lines.extend(['#EXTINF:-1 ' + ' '.join(attrs) + ',' + title, url])
    return '\n'.join(lines) + '\n'


def write_site(directory, selected, channels, candidates, report):
    """Stage a whole version, then swap directories; rollback on a failed swap.

    The CLI must pass the quality gate before calling this function. Pages receives
    a completed immutable artifact, never this in-progress directory.
    """
    if not report['publish_gate']['allowed']:
        raise Rejected('publish_gate_denied')
    target = Path(directory).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    staged = Path(tempfile.mkdtemp(prefix='.iptv-stage-', dir=target.parent))
    old = None
    try:
        for name, backup in [('live.m3u',False),('backup.m3u',True)]:
            (staged / name).write_text(render_m3u(selected, channels, candidates, backup), encoding='utf-8')
        (staged / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        status = html.escape(report['generated_at'])
        env = html.escape(report['environment']['location'])
        (staged / 'index.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>IPTV 检测状态</title><body><h1>IPTV 检测状态</h1><p>本版本检测时间：'+status+'</p><p>合格频道：'+str(len(selected))+'</p><p>测试环境：'+env+'；仍需杭州电信 Redmi X65 人工验收。</p><p><a href="live.m3u">主线订阅</a> · <a href="backup.m3u">双线路订阅</a> · <a href="report.json">完整报告</a></p><p>此时间代表本版本检测时间；最新运行失败时本站继续保留旧版本，请查看 Actions。</p></body></html>\n', encoding='utf-8')
        (staged / '.nojekyll').touch()
        # mkdtemp defaults to 0700; normalize public artifact permissions.
        staged.chmod(0o755)
        for child in staged.iterdir():
            child.chmod(0o644)
        if target.exists():
            old = Path(tempfile.mkdtemp(prefix='.iptv-old-', dir=target.parent))
            old.rmdir()
            os.replace(target, old)
        try:
            os.replace(staged, target)
        except BaseException:
            if old is not None:
                os.replace(old, target)
            raise
    finally:
        if staged.exists():
            shutil.rmtree(staged)
        if old is not None and old.exists():
            shutil.rmtree(old)
