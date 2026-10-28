"""Local upload UI: streamlit run app.py."""
import json
import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from pipeline import ROOT, INPUT_ROOT, CATEGORIES, find_source_pair, run
from flux import area_from_dataset_name

st.set_page_config(page_title='VOCs 初步分析', layout='wide')
st.title('叶片 BVOCs 单位叶面积通量分析')
st.write('读取背景已校正的浓度，计算稳态叶面积通量、小时 mean/SE、六类汇总和环境相关性。')
source_mode = st.radio('数据来源', ['读取 Original Data 文件夹', '上传两个 Excel'])
voc = env = None
local_voc = local_env = None
if source_mode == '读取 Original Data 文件夹':
    folders = sorted(p for p in INPUT_ROOT.iterdir() if p.is_dir()) if INPUT_ROOT.is_dir() else []
    if folders:
        selection = st.selectbox('选择数据文件夹', folders, format_func=lambda p: p.name)
        try:
            local_voc, local_env = find_source_pair(selection)
            st.caption(f'浓度：{local_voc.name}；环境：{local_env.name}')
        except ValueError as exc:
            st.error(str(exc))
    else:
        st.info(f'请将每组源 Excel 放在 {INPUT_ROOT} 下的独立子文件夹中。')
else:
    voc = st.file_uploader('VOCs 浓度文件', type=['xlsx'], key='voc')
    env = st.file_uploader('环境参数文件', type=['xlsx'], key='env')
mapping = st.file_uploader('自定义物种分类表（可选 CSV）', type=['csv'])
cfg = json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
flux_cfg = cfg['flux']
detected_area = area_from_dataset_name(local_voc.parent.name) if local_voc is not None else None
if detected_area is not None:
    st.info(f'从数据集文件夹识别叶面积：{detected_area} m²')
area = st.number_input('叶室内叶面积 (m²)', min_value=0.000001,
                       value=detected_area, format='%.6f', disabled=detected_area is not None)
flux_cfg['leaf_area_m2'] = area
with st.expander('动态叶室与流量参数'):
    flux_cfg['chamber_volume_l'] = st.number_input('叶室体积 (L)', min_value=.001, value=float(flux_cfg['chamber_volume_l']))
    flux_cfg['flow_l_min'] = st.number_input('叶室总通气流量 (L/min)', min_value=.001, value=float(flux_cfg['flow_l_min']))
    flux_cfg['flow_is_chamber_total'] = st.checkbox('确认此流量是叶室总通气流量', value=flux_cfg['flow_is_chamber_total'])
    flux_cfg['steady_state_confirmed'] = st.checkbox('确认采样时已达到近似稳态', value=flux_cfg['steady_state_confirmed'])
    background_options = ['already_corrected', 'zero_inlet', 'constant_per_species']
    flux_cfg['background_mode'] = st.selectbox('背景处理方式', background_options,
        index=background_options.index(flux_cfg['background_mode']),
        format_func=lambda s: {'already_corrected':'浓度已扣背景', 'zero_inlet':'入口为零气',
                               'constant_per_species':'逐物种固定入口背景（在配置JSON填写background_ppb）'}[s])
    flux_cfg['flow_basis'] = st.selectbox('体积流量基准', ['standard','actual'],
        index=0 if flux_cfg['flow_basis']=='standard' else 1,
        format_func=lambda s: '标准体积流量' if s=='standard' else '实际体积流量（使用匹配温度）')
    if flux_cfg['flow_basis'] == 'standard':
        flux_cfg['reference_temperature_c'] = st.number_input('流量参考温度 (°C)', value=float(flux_cfg['reference_temperature_c']))
        flux_cfg['reference_pressure_pa'] = 1000*st.number_input('流量参考压力 (kPa)', min_value=.001,
            value=float(flux_cfg['reference_pressure_pa'])/1000, format='%.3f')
    else:
        flux_cfg['chamber_pressure_pa'] = 1000*st.number_input('叶室压力 (kPa)', min_value=.001,
            value=float(flux_cfg.get('chamber_pressure_pa') or 101325)/1000, format='%.3f')
mode = st.radio('环境匹配规则', ['采样所在5分钟区间（例：08:42 → 08:40–08:45）', '每条采样记录前后各5分钟'])
cfg['window_mode'] = 'five_minute_bins' if mode.startswith('采样所在') else 'plus_minus'
cfg['concentration_unit'] = st.text_input('浓度单位', cfg['concentration_unit'])
with st.expander('列名与输入设置'):
    st.caption('换用不同仪器导出时，修改JSON中的sheet和列名；JSON必须合法。')
    config_text = st.text_area('配置 JSON', json.dumps(cfg, ensure_ascii=False, indent=2), height=300)
st.caption('通量单位：nmol m⁻² s⁻¹。六类之外的成分直接剔除。SE基于技术读数；相关性使用小时通量均值。')
classifications = pd.read_csv(ROOT/'species_mapping.csv')
st.dataframe(classifications[classifications.category.isin(CATEGORIES)], hide_index=True)
ready = area is not None and ((local_voc is not None and local_env is not None) or (voc is not None and env is not None))
if st.button('运行分析', type='primary', disabled=not ready):
    try:
        config = json.loads(config_text)
        # Radio and unit controls own these settings.
        config['window_mode'] = cfg['window_mode']
        config['concentration_unit'] = cfg['concentration_unit']
        config.setdefault('flux', {})['leaf_area_m2'] = area
        source_name = local_voc.stem if local_voc is not None else Path(voc.name).stem
        output = ROOT/'results'/source_name
        if output.exists() and any(output.iterdir()):
            output = output/datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            if local_voc is not None:
                voc_path, env_path = local_voc, local_env
            else:
                voc_path, env_path = temp/Path(voc.name).name, temp/Path(env.name).name
                if voc_path == env_path:
                    raise ValueError('浓度和环境文件不能同名')
                voc_path.write_bytes(voc.getvalue())
                env_path.write_bytes(env.getvalue())
            (temp/'config.json').write_text(json.dumps(config, ensure_ascii=False), encoding='utf-8')
            mapping_path = ROOT/'species_mapping.csv'
            if mapping:
                mapping_path = temp/'mapping.csv'
                mapping_path.write_bytes(mapping.getvalue())
            with st.spinner('正在统计、绘图并导出…'):
                manifest = run(voc_path, env_path, output, temp/'config.json', mapping_path)
        st.session_state['result'] = (str(output), manifest)
    except Exception as exc:
        st.error(str(exc))
if 'result' in st.session_state:
    output, manifest = st.session_state['result']
    output = Path(output)
    st.success(f"完成：{manifest['sample_count']} 条采样，{manifest['hour_count']} 个小时")
    st.write(f'结果已保存到：{output}')
    st.image(str(output/'plots/categories_environment.png'))
    with st.expander('查看独立折线图'):
        for figure in ['categories', 'temperature', 'humidity', 'PAR']:
            st.image(str(output/f'plots/{figure}.png'))
    st.image(str(output/'plots/correlation_Pearson.png'))
    st.dataframe(pd.read_csv(output/'correlation_categories.csv'), hide_index=True)
