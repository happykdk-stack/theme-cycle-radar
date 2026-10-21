"""Fail before publishing a malformed dashboard data file."""
import json
import os
from pathlib import Path

site = Path(__file__).resolve().parents[1] / 'site'
data = json.loads((site / 'data.json').read_text(encoding='utf-8'))
assert data['version'] == '4.2'
assert data['etf_trend_version'] == '1.0'
assert data['status'] != 'error'
assert data['themes']
assert data['securities_etf']['ticker'] == '102970.KS'
for theme in [*data['themes'], data['securities_etf']]:
    trend = theme['etf_trend']
    assert trend['signal'] in ('green', 'yellow', 'red', 'gray')
    assert set(trend['timeframes']) == {'monthly', 'weekly', 'daily'}
    for f in trend['timeframes'].values():
        assert f['state'] in ('up', 'down', 'mixed', 'insufficient')
    if trend['last_changed']:
        assert trend['last_changed'] <= trend['asof']
assert not any(e['message'].startswith('ETF trend calculation:') for e in data['errors']), data['errors']
(site / 'build.json').write_text(json.dumps({
    'commit': os.environ.get('BUILD_SHA', 'local'),
    'generated_at_utc': data['generated_at_utc'],
    'etf_trend_version': data['etf_trend_version'],
}, indent=2), encoding='utf-8')
print('Validated ETF signals:', len(data['themes']), 'status:', data['status'])
