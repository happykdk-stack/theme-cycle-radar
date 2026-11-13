import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from per_data import build, valid_pe
class PERTests(unittest.TestCase):
 def test_validation(self):
  self.assertIsNone(valid_pe(-1));self.assertIsNone(valid_pe(float("nan")))
  self.assertEqual(valid_pe("14.123"),14.12)
 def test_missing_is_not_fabricated(self):
  d=build(fetch=lambda t:None,prior={},asof="2026-11-13")
  self.assertEqual(d["etfs"]["SOXX"]["history"],[])
  self.assertIsNone(d["etfs"]["SOXX"]["pe"])
  self.assertEqual(d["etfs"]["USO"]["status"],"not_applicable")
 def test_historical_observation_preserved(self):
  prior={"SOXX":{"history":[{"date":"2026-11-12","pe":20.0}]}}
  d=build(fetch=lambda t:21.0,prior=prior,asof="2026-11-13")
  self.assertEqual(len(d["etfs"]["SOXX"]["history"]),2)
if __name__=="__main__":unittest.main()
