import copy
import json
import runpy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from heikin_ashi import empty_ha_signal


class DeploymentValidationTests(unittest.TestCase):
    def data(self):
        trend = empty_ha_signal()
        trend.update(signal='green', bullish_score=100, asof='2025-08-29')
        trend['timeframes'] = {key: {'state':'up', 'ha_open':90., 'ha_close':95.,
            'actual_open':100., 'actual_close':98., 'actual_change_pct':-2.}
            for key in ('monthly', 'weekly', 'daily')}
        return {'version':'4.2', 'etf_trend_version':'1.0', 'status':'partial',
            'generated_at_utc':'2025-08-29T21:00:00Z', 'errors':[],
            'themes':[{'ticker':'LIT', 'etf_trend':trend}],
            'securities_etf':{'ticker':'102970.KS', 'etf_trend':empty_ha_signal()}}

    def validate(self, data):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            (root / 'site').mkdir()
            (root / 'scripts').mkdir()
            (root / 'site/data.json').write_text(json.dumps(data), encoding='utf-8')
            script = root / 'scripts/validate_site.py'
            script.write_text((ROOT / 'scripts/validate_site.py').read_text(encoding='utf-8'), encoding='utf-8')
            runpy.run_path(str(script))
            return json.loads((root / 'site/build.json').read_text(encoding='utf-8'))

    def test_ha_and_failed_gray_etf_can_be_published(self):
        self.assertEqual(self.validate(self.data())['etf_trend_version'], '1.0')

    def test_wrong_method_direction_or_actual_change_blocks_publish(self):
        for change in ('method', 'direction', 'actual_change'):
            with self.subTest(change=change):
                data = copy.deepcopy(self.data())
                trend = data['themes'][0]['etf_trend']
                if change == 'method':
                    trend['method'] = 'MA1'
                elif change == 'direction':
                    trend['timeframes']['monthly']['ha_close'] = 85.
                else:
                    trend['timeframes']['monthly']['actual_change_pct'] = 2.
                with self.assertRaises(AssertionError):
                    self.validate(data)
