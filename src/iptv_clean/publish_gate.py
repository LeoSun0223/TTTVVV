import json
from pathlib import Path

from .models import Rejected


def load_previous(directory):
    directory = Path(directory)
    report = directory / 'report.json'
    if not directory.exists() or not any(directory.iterdir()):
        return None
    try:
        previous = json.loads(report.read_text())
        count = previous['qualified_channels']
        if not isinstance(count,int) or count <= 0 or not previous.get('generated_at'):
            raise ValueError()
        for name in ['live.m3u','backup.m3u']:
            if not (directory / name).read_text().startswith('#EXTM3U\n'):
                raise ValueError()
        deployment = directory / '_deployment.json'
        if deployment.exists():
            previous['published_at'] = json.loads(deployment.read_text())['published_at']
        return previous
    except (OSError, ValueError, KeyError, TypeError):
        raise Rejected('baseline_invalid') from None


def publish_gate(selected, channels, settings, previous=None):
    count = len(selected)
    groups = {channels.rows[c]['group'] for c in selected}
    reason = 'ok'
    if count < settings['publish_min_channels']:
        reason = 'below_minimum_channels'
    elif not {'央视','卫视'}.issubset(groups):
        reason = 'missing_required_category'
    elif previous and count < previous['qualified_channels'] * settings['publish_min_ratio']:
        reason = 'channel_count_regression'
    return {'allowed': reason == 'ok', 'reason': reason, 'current_count': count,
            'minimum_channels': settings['publish_min_channels'], 'minimum_ratio': settings['publish_min_ratio'],
            'previous_count': previous['qualified_channels'] if previous else None,
            'previous_success_generated_at': previous['generated_at'] if previous else None,
            'previous_published_at': previous.get('published_at') if previous else None}
