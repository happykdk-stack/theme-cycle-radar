import sys
import types
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
try:
    import yfinance
except ImportError:
    sys.modules['yfinance']=types.SimpleNamespace(download=None)
import numpy as np
import pandas as pd
from update import analyze,build

class RadarTests(unittest.TestCase):
    def make(self,price=100):
        idx=pd.bdate_range('2025-01-01',periods=90)
        close=np.full(90,float(price))
        close[60]=103.5
        close[61:]=103.5
        vol=np.full(90,1000.)
        vol[60]=1600
        return pd.DataFrame({'Close':close,'Volume':vol},index=idx)
    def test_signal_and_future_returns(self):
        f=self.make()
        r=analyze(f,self.make(),'미국','테스트','TEST','Fund')
        self.assertEqual(len(r['signals']),1)
        self.assertEqual(r['signals'][0]['date'],f.index[60].date().isoformat())
        self.assertEqual(r['signals'][0]['return_5d_pct'],0.0)
        self.assertEqual(r['signals'][0]['return_20d_pct'],0.0)
    def test_no_false_signal_at_149_percent_volume(self):
        f=self.make();f.iloc[60,f.columns.get_loc('Volume')]=1490
        r=analyze(f,self.make(),'미국','테스트','TEST','Fund')
        self.assertEqual(len(r['signals']),0)
    def test_partial_failure(self):
        def fetch(ticker):
            if ticker=='SOXX':raise RuntimeError('offline')
            return self.make()
        r=build(fetch)
        self.assertEqual(r['status'],'partial')
        self.assertTrue(any(x['ticker']=='SOXX' for x in r['errors']))

if __name__=='__main__':unittest.main()
