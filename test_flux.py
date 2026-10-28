import unittest
import numpy as np
import pandas as pd
from flux import area_from_dataset_name, flux_settings, ppb_to_flux_factor, calculate_flux_rows
from pipeline import summarize, category_totals


class FluxTests(unittest.TestCase):
    def test_dataset_area(self):
        self.assertEqual(area_from_dataset_name('1015_xiangzhang_0.5'), .5)
        self.assertIsNone(area_from_dataset_name('1015_xiangzhang'))
        with self.assertRaises(ValueError):
            area_from_dataset_name('1015_xiangzhang_0')

    def test_unit_conversion_against_molar_volume(self):
        # At 0°C and 1 atm, ideal molar volume is about 22.414 L/mol.
        expected = (5/60) / 22.413969545014 / .5
        self.assertAlmostEqual(float(ppb_to_flux_factor(5,.5,0,101325)),expected,places=12)
        self.assertAlmostEqual(float(ppb_to_flux_factor(10,.5,0,101325)),expected*2,places=12)
        self.assertAlmostEqual(float(ppb_to_flux_factor(5,1,0,101325)),expected/2,places=12)

    def test_missing_protocol_is_not_assumed(self):
        with self.assertRaisesRegex(ValueError, '总通气流量'):
            flux_settings('1015_xiangzhang_0.5/voc.xlsx', {'concentration_unit':'ppb','flux':{}})

    def test_area_conflict(self):
        with self.assertRaisesRegex(ValueError, '不一致'):
            flux_settings('1015_xiangzhang_0.5/voc.xlsx', {'flux':{'leaf_area_m2':.6}})

    def test_actual_flow_requires_temperature_for_each_hour(self):
        h1,h2 = pd.to_datetime(['2026-10-15 08:00','2026-10-15 09:00'])
        data = pd.DataFrame({'timestamp':[h1,h2],'hour':[h1,h2],'a':[10.,10.]})
        env = pd.DataFrame({'hour':[h1],'variable':['temperature'],'mean':[25.]})
        settings = {'flow_basis':'actual','chamber_pressure_pa':101325.,'flow_l_min':5.,
                    'leaf_area_m2':.5,'chamber_volume_l':10.,'background_mode':'already_corrected'}
        flux, factors = calculate_flux_rows(data,['a'],env,settings)
        self.assertAlmostEqual(flux.a.iloc[0],10*ppb_to_flux_factor(5,.5,25,101325))
        self.assertTrue(np.isnan(flux.a.iloc[1]))
        self.assertEqual(factors.status.iloc[1],'missing_temperature')

    def test_flux_mean_se_covariance_and_negative_exchange(self):
        hour = pd.Timestamp('2026-10-15 08:00')
        data = pd.DataFrame({'hour':[hour]*2, 'timestamp':[hour,hour+pd.Timedelta(seconds=10)],
                             'a':[1.,3.], 'b':[3.,1.]})
        settings = {'flow_basis':'standard','reference_temperature_c':25.,'reference_pressure_pa':101325.,
                    'flow_l_min':5.,'leaf_area_m2':.5,'chamber_volume_l':10.,
                    'background_mode':'constant_per_species','background_ppb':{'a':2.,'b':0.}}
        flux, table = calculate_flux_rows(data,['a','b'],pd.DataFrame(),settings)
        factor = table.factor_nmol_m2_s_per_ppb.iloc[0]
        self.assertLess(flux.a.iloc[0],0)  # uptake must not be clipped to zero
        summary = summarize(flux,['hour'],['a'])
        self.assertAlmostEqual(summary['mean'].iloc[0],0)
        self.assertAlmostEqual(summary.se.iloc[0],factor)
        mapping = pd.DataFrame({'species':['a','b'],'category':['OTs','OTs']})
        total = summarize(category_totals(flux,mapping),['hour'],['OTs'])
        self.assertAlmostEqual(total['mean'].iloc[0],2*factor)
        self.assertAlmostEqual(total.se.iloc[0],0)
        settings['background_ppb'] = {'a':0.}
        with self.assertRaisesRegex(ValueError,'缺少入口背景'):
            calculate_flux_rows(data,['a','b'],pd.DataFrame(),settings)


if __name__ == '__main__':
    unittest.main()
