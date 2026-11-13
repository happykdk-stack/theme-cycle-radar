import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from per_data import parse_multpl,build
class HistoricalPERTests(unittest.TestCase):
 def test_parse_real_only(self):
  html='<table><tr><td>Nov 1, 2026</td><td>† (Estimate) 25.73</td></tr><tr><td>Jun 1, 2026</td><td>25.22</td></tr></table>'
  self.assertEqual(parse_multpl(html),[{"date":"2026-06-01","pe":25.22}])
 def test_index_source_and_missing_not_fabricated(self):
  def f():return {"^GSPC":{"history":[{"date":"2025-01-01","pe":20.0}],"source":"test","frequency":"monthly"}},{}
  d=build(fetch=lambda t:None,fetch_prices=lambda t:__import__("pandas").DataFrame(),prior={},asof="2026-11-13",fetch_index_pe=f)
  self.assertEqual(d["indices"]["^GSPC"]["pe"],20.)
  self.assertIsNone(d["indices"]["^KS11"]["pe"])
if __name__=="__main__":unittest.main()
