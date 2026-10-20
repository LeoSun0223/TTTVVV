"""Run only AFTER deploy-pages and exact public content verification succeeded."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil


def main():
    source, target = Path('tmp/site'), Path('output')
    report = json.loads((source/'report.json').read_text())
    if not report['publish_gate']['allowed']:
        raise SystemExit('不允许归档未通过发布门槛的版本')
    target.mkdir(exist_ok=True)
    for name in ['live.m3u','backup.m3u','report.json','index.html','.nojekyll']:
        shutil.copyfile(source/name,target/name)
    metadata = {'published_at':datetime.now(timezone.utc).isoformat(),
                'page_url':os.environ['PAGE_URL'],'actions_run':os.environ['RUN_URL'],
                'validation_generated_at':report['generated_at']}
    (target/'_deployment.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')


if __name__ == '__main__':
    main()
