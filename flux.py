"""Steady-state, well-mixed, equal-flow chamber mass balance in molar units."""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

GAS_CONSTANT = 8.31446261815324  # Pa m3 mol-1 K-1
FLUX_UNIT = 'nmol m$^{-2}$ s$^{-1}$'


def area_from_dataset_name(name):
    """The final _0.5 in a dataset folder name means 0.5 m2 leaf area."""
    match = re.search(r'_(\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)$', str(name))
    if match is None:
        return None
    area = float(match.group(1))
    if not np.isfinite(area) or area <= 0:
        raise ValueError('文件夹名中的叶面积必须为正数，单位m²')
    return area


def flux_settings(voc_path, cfg):
    """Refuse to invent background, chamber flow, or steady-state confirmation."""
    settings = dict(cfg.get('flux', {}))
    area = area_from_dataset_name(Path(voc_path).parent.name)
    explicit_area = settings.get('leaf_area_m2')
    if explicit_area is not None:
        if area is not None and not np.isclose(float(explicit_area), area):
            raise ValueError('配置叶面积与数据集文件夹末尾面积不一致')
        area = float(explicit_area)
    if area is None or not np.isfinite(area) or area <= 0:
        raise ValueError('需将叶面积写入数据集文件夹名末尾（如_0.5），或设置flux.leaf_area_m2')
    settings['leaf_area_m2'] = area
    if cfg.get('concentration_unit') != 'ppb':
        raise ValueError('当前通量换算仅接受ppb输入')
    if settings.get('flow_is_chamber_total') is not True:
        raise ValueError('需确认flux.flow_is_chamber_total=true：流量必须是叶室总通气流量')
    if settings.get('steady_state_confirmed') is not True:
        raise ValueError('需确认采样已达稳态（flux.steady_state_confirmed=true）；非稳态不能使用稳态公式')
    if settings.get('background_mode') not in ['already_corrected', 'zero_inlet', 'constant_per_species']:
        raise ValueError('需确认背景：already_corrected、zero_inlet，或constant_per_species')
    if settings.get('flow_basis') not in ['actual', 'standard']:
        raise ValueError('需确认流量基准flux.flow_basis：actual或standard')
    for key in ['flow_l_min', 'chamber_volume_l']:
        if not np.isfinite(float(settings.get(key, np.nan))) or float(settings[key]) <= 0:
            raise ValueError(f'flux.{key}必须为正数')
    return settings


def ppb_to_flux_factor(flow_l_min, area_m2, temperature_c, pressure_pa):
    """nmol m-2 s-1 per ppb; ppb = nmol/mol cancels the 1e-9/1e9 factors."""
    if not np.isfinite(flow_l_min) or not np.isfinite(area_m2) or flow_l_min <= 0 or area_m2 <= 0:
        raise ValueError('流量和叶面积必须为正数')
    t = np.asarray(temperature_c, dtype=float) + 273.15
    p = float(pressure_pa)
    if not np.isfinite(p) or p <= 0 or np.any(np.isfinite(t) & (t <= 0)) or np.isinf(t).any():
        raise ValueError('温度必须高于绝对零度，压力必须为正数')
    return flow_l_min * 1e-3 * p / (60 * GAS_CONSTANT * t * area_m2)


def calculate_flux_rows(data, species, env_stats, settings):
    """Convert each reading with its hourly factor, then summarize elsewhere.

    The hourly temperature/pressure, flow, area and background are treated as fixed.
    Technical-reading SE does not include their calibration/measurement uncertainty.
    """
    hours = pd.Index(sorted(data.hour.unique()), name='hour')
    if settings['flow_basis'] == 'actual':
        temperature = env_stats[env_stats.variable.eq('temperature')].set_index('hour')['mean'].reindex(hours)
        pressure = settings.get('chamber_pressure_pa')
        if pressure is None:
            raise ValueError('实际体积流量需设置flux.chamber_pressure_pa（Pa）')
    else:
        reference_temperature = settings.get('reference_temperature_c')
        pressure = settings.get('reference_pressure_pa')
        if reference_temperature is None or pressure is None:
            raise ValueError('标准体积流量需明确参考温度和参考压力')
        temperature = pd.Series(float(reference_temperature), index=hours)
        if not np.isfinite(float(reference_temperature)):
            raise ValueError('标准参考温度必须为有限数值')
    factors = pd.DataFrame({'hour': hours, 'temperature_for_flow_c': temperature.to_numpy(),
                            'pressure_for_flow_pa': float(pressure),
                            'leaf_area_m2': settings['leaf_area_m2'],
                            'chamber_volume_l': settings['chamber_volume_l'],
                            'flow_l_min': settings['flow_l_min']})
    factors['factor_nmol_m2_s_per_ppb'] = ppb_to_flux_factor(
        settings['flow_l_min'], settings['leaf_area_m2'],
        factors.temperature_for_flow_c, float(pressure))
    factors['flow_basis'] = settings['flow_basis']
    factors['background_mode'] = settings['background_mode']
    factors['status'] = np.where(factors.factor_nmol_m2_s_per_ppb.isna(), 'missing_temperature', 'ok')
    per_row_factor = data.hour.map(factors.set_index('hour').factor_nmol_m2_s_per_ppb)
    if settings['background_mode'] == 'constant_per_species':
        background = settings.get('background_ppb', {})
        missing = sorted(set(species) - set(background))
        if missing:
            raise ValueError(f'以下物种缺少入口背景ppb，不可默认0: {missing}')
        background = pd.Series({name: float(background[name]) for name in species})
        if not np.isfinite(background).all() or background.lt(0).any():
            raise ValueError('入口背景浓度必须为有限非负值')
    else:
        background = pd.Series(0., index=species)
    flux = data[['timestamp', 'hour']].copy()
    flux = pd.concat([flux, data[species].sub(background, axis='columns').mul(per_row_factor, axis='index')], axis=1)
    return flux, factors
