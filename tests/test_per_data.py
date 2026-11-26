import sys, unittest
from unittest.mock import patch
import pandas as pd
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from per_data import build, valid_pe, previous_history
def offline_build(**kwargs):
 return build(fetch_prices=lambda _:pd.DataFrame(),fetch_index_pe=lambda:({},{}),fetch_pbr=lambda _:None,**kwargs)
class PERTests(unittest.TestCase):
 def test_validation(self):
  self.assertIsNone(valid_pe(-1));self.assertIsNone(valid_pe(float("nan")))
  self.assertEqual(valid_pe("14.123"),14.12)
 def test_missing_is_not_fabricated(self):
  d=offline_build(fetch=lambda t:None,prior={},asof="2026-11-13")
  self.assertEqual(d["etfs"]["SOXX"]["history"],[])
  self.assertIsNone(d["etfs"]["SOXX"]["pe"])
  self.assertEqual(d["etfs"]["USO"]["status"],"not_applicable")
  self.assertEqual(d['etfs']['091160.KS']['reference_per']['date'],'2026-10-01')
  self.assertEqual(d['etfs']['091160.KS']['reference_per']['pe'],8.57)
  self.assertEqual(d['etfs']['091160.KS']['per_weekly_history'],[])
  self.assertIsNone(d['etfs']['091160.KS']['pe'],'older portfolio reference must not become current quote P/E')
 def test_historical_observation_preserved(self):
  prior={"SOXX":{"history":[{"date":"2026-11-12","pe":20.0}]}}
  d=offline_build(fetch=lambda t:21.0,prior=prior,asof="2026-11-13")
  self.assertEqual(len(d["etfs"]["SOXX"]["history"]),2)
  self.assertEqual(len(d['etfs']['SOXX']['per_slope_history']),2)
 def test_saved_observations_survive_failed_remote_history_read(self):
  saved={'SOXX':{'history':[{'date':'2026-11-13','pe':20.}]}}
  with patch('per_data.load_history_cache',return_value=saved),patch('per_data.urlopen',side_effect=OSError('offline')):
   history,error=previous_history()
  self.assertEqual(history,saved)
  self.assertIn('offline',error)
 def test_remote_history_merges_without_erasing_saved_dates(self):
  import io,json
  saved={'SOXX':{'history':[{'date':'2026-11-13','pe':20.}]}}
  remote={'etfs':{'SOXX':{'history':[{'date':'2026-11-16','pe':21.}]}}}
  with patch('per_data.load_history_cache',return_value=saved),patch('per_data.urlopen',return_value=io.BytesIO(json.dumps(remote).encode())):
   history,error=previous_history()
  self.assertIsNone(error)
  self.assertEqual([p['date'] for p in history['SOXX']['history']],['2026-11-13','2026-11-16'])
if __name__=="__main__":unittest.main()
