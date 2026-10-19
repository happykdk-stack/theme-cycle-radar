import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import numpy as np,pandas as pd
from update_v4 import detect
class Tests(unittest.TestCase):
 def test_flat(self):
  i=pd.bdate_range('2025-01-01',periods=120)
  f=pd.DataFrame({'Close':np.full(120,100.),'Volume':np.full(120,1000.)},index=i)
  self.assertNotIn(detect(f,f)['cycle_stage'],('초기 유입','상승 확산'))
 def test_dates(self):
  i=pd.bdate_range('2025-01-01',periods=120)
  f=pd.DataFrame({'Close':np.linspace(100,150,120),'Volume':np.full(120,1000.)},index=i)
  r=detect(f,pd.DataFrame({'Close':np.full(120,100.)},index=i))
  self.assertTrue(all(e['date']<=str(i[-1].date()) for e in r['cycle_transitions']))
if __name__=='__main__':unittest.main()
