import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from per_data import parse_multpl
class PublicPERTests(unittest.TestCase):
 def test_excludes_estimates_and_keeps_real_monthly_observations(self):
  html='<table><tr><td>Nov 1, 2026</td><td>† (Estimate) 25.73</td></tr><tr><td>Jun 1, 2026</td><td>25.22</td></tr><tr><td>May 1, 2026</td><td>26.09</td></tr></table>'
  self.assertEqual(parse_multpl(html),[{"date":"2026-05-01","pe":26.09},{"date":"2026-06-01","pe":25.22}])
if __name__=="__main__":unittest.main()
