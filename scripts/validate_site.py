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
    history = trend['green_history']
    if history is not None:
        assert history['asof'] == trend['asof']
        assert history['window_start'] <= history['asof']
        assert isinstance(history['complete'], bool)
        runs = history['runs']
        assert history['latest_run'] == (runs[-1] if runs else None)
        assert history['latest_date'] == (runs[-1]['end_date'] if runs else None)
        for i, run in enumerate(runs):
            assert run['start_date'] <= run['end_date'] <= history['asof']
            assert run['end_date'] >= history['window_start']
            assert isinstance(run['active'], bool)
            assert run['active'] == (run['end_date'] == history['asof'] and trend['signal'] == 'green')
            if i:
                assert runs[i-1]['end_date'] < run['start_date']
        assert bool(runs and runs[-1]['active']) == (trend['signal'] == 'green')
assert not any(e['message'].startswith('ETF trend calculation:') for e in data['errors']), data['errors']
(site / 'build.json').write_text(json.dumps({
    'commit': os.environ.get('BUILD_SHA', 'local'),
    'generated_at_utc': data['generated_at_utc'],
    'etf_trend_version': data['etf_trend_version'],
}, indent=2), encoding='utf-8')
print('Validated ETF signals:', len(data['themes']), 'status:', data['status'])
