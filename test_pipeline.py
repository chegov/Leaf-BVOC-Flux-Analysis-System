import unittest
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
from pipeline import summarize, category_totals, match_environment, bh_adjust, correlations, find_source_pair


class StatisticsTests(unittest.TestCase):
    def test_source_folder_pair_and_lockfile(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            assert root.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
            for name in ['1016_xiangzhang.xlsx', '1016_env.xlsx', '~$1016_env.xlsx']:
                (root/name).touch()
            voc, env = find_source_pair(root)
            self.assertEqual(voc.name, '1016_xiangzhang.xlsx')
            self.assertEqual(env.name, '1016_env.xlsx')

    def test_source_folder_missing_or_ambiguous_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            assert root.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
            (root/'1016_xiangzhang.xlsx').touch()
            with self.assertRaisesRegex(ValueError, '环境文件0个'):
                find_source_pair(root)
            (root/'1016_env.xlsx').touch()
            (root/'extra.xlsx').touch()
            with self.assertRaisesRegex(ValueError, '浓度文件2个'):
                find_source_pair(root)

    def test_se_and_missing(self):
        d = pd.DataFrame({'hour': [1,1,2], 'x':[1.,3.,np.nan]})
        s = summarize(d, ['hour'], ['x'])
        self.assertEqual(s.iloc[0]['mean'], 2)
        self.assertEqual(s.iloc[0]['se'], 1)
        self.assertEqual(s.iloc[1]['n'], 0)
        self.assertTrue(np.isnan(s.iloc[1]['se']))

    def test_covariance_preserved(self):
        d = pd.DataFrame({'timestamp': [1,2], 'hour':[1,1], 'a':[1,3], 'b':[3,1]})
        m = pd.DataFrame({'species':['a','b'], 'category':['OTs','OTs']})
        totals = category_totals(d,m)
        s = summarize(totals, ['hour'], ['OTs'])
        self.assertEqual(s.iloc[0]['mean'],4)
        self.assertEqual(s.iloc[0]['se'],0)
        d.loc[0,'a'] = np.nan
        self.assertTrue(np.isnan(category_totals(d,m).iloc[0]['OTs']))
        self.assertTrue(category_totals(d,m).OMTs.isna().all())

    def test_window_union_and_boundaries(self):
        t = pd.Timestamp('2026-10-15 08:42:00')
        v = pd.DataFrame({'timestamp':[t,t+pd.Timedelta(seconds=20)], 'hour':[t.floor('h')]*2})
        e = pd.DataFrame({'timestamp':pd.to_datetime(['2026-10-15 08:40:00','2026-10-15 08:44:59','2026-10-15 08:45:00'])})
        w, selected = match_environment(v,e,'five_minute_bins')
        self.assertEqual(len(w),1)
        self.assertEqual(len(selected),2)
        _, selected = match_environment(v,e,'plus_minus')
        self.assertEqual(len(selected),3)

    def test_bh_known_values(self):
        np.testing.assert_allclose(bh_adjust([.01,.04,.03,np.nan]),[.03,.04,.04,np.nan],equal_nan=True)

    def test_empty_environment_summary(self):
        d = pd.DataFrame(columns=['hour','temperature'])
        s = summarize(d,['hour'],['temperature'])
        self.assertEqual(s.columns.tolist(),['hour','variable','mean','se','n'])
        self.assertTrue(s.empty)

    def test_correlation_pairwise_and_constant(self):
        v = pd.DataFrame({'hour':[1,2,3,4], 'variable':['iso']*4, 'mean':[1.,2.,3.,np.nan]})
        e = pd.DataFrame({'hour':[1,2,3,4], 'variable':['PAR']*4, 'mean':[2.,4.,6.,8.]})
        c = correlations(v,e,'category')
        self.assertTrue(c.n.eq(3).all())
        np.testing.assert_allclose(c.r,1)
        e['mean'] = 1.
        c = correlations(v,e,'category')
        self.assertTrue(c.status.eq('constant_series').all())
        self.assertTrue(c.r.isna().all())


if __name__ == '__main__':
    unittest.main()
