"""Independent checks for the provided example, run after pipeline.py."""
from pathlib import Path
import sys
import json
import numpy as np
import pandas as pd
from openpyxl import load_workbook
from pipeline import INPUT_ROOT, find_source_pair, write_sheets

root = Path(__file__).resolve().parent
out = Path(sys.argv[1]) if len(sys.argv) > 1 else root/'results/1015_xiangzhang'
voc_path, env_path = find_source_pair(INPUT_ROOT/'1015_xiangzhang_0.5')
raw = pd.read_excel(voc_path)
raw.columns = raw.columns.str.strip()
hours = pd.to_datetime(raw['时间']).dt.floor('h')
result = pd.read_csv(out/'hourly_species.csv')
result['hour'] = pd.to_datetime(result.hour)
mapping = pd.read_csv(root/'species_mapping.csv')
categories = pd.read_csv(out/'hourly_categories.csv')
categories['hour'] = pd.to_datetime(categories.hour)
for h, group in raw.groupby(hours):
    for _, row in result[result.hour.eq(h)].iterrows():
        x = group[row.variable].to_numpy(dtype=float)
        np.testing.assert_allclose([row['mean'],row.se], [x.mean(),x.std(ddof=1)/np.sqrt(len(x))], atol=1e-12)
    for _, row in categories[categories.hour.eq(h)].iterrows():
        cols = mapping.loc[mapping.category.eq(row.variable),'species'].tolist()
        values = group[cols].to_numpy(dtype=float).sum(axis=1)
        np.testing.assert_allclose([row['mean'],row.se], [values.mean(),values.std(ddof=1)/np.sqrt(len(values))], atol=1e-12)

env_raw = pd.read_excel(env_path, sheet_name='数据')
env_result = pd.read_csv(out/'hourly_environment.csv')
cfg = json.loads((root/'config.json').read_text(encoding='utf-8'))
for h, group in raw.groupby(hours):
    # Independent scalar check: each environment timestamp lies in a sampling bin.
    sample_bins = set(pd.to_datetime(group['时间']).dt.floor('5min'))
    selected = env_raw[pd.to_datetime(env_raw[cfg['env_time_column']]).dt.floor('5min').isin(sample_bins)]
    for name, column in cfg['environment_columns'].items():
        row = env_result[(pd.to_datetime(env_result.hour).eq(h)) & env_result.variable.eq(name)].iloc[0]
        x = selected[column].to_numpy(dtype=float)
        assert row.n == len(x)
        np.testing.assert_allclose([row['mean'],row.se],[x.mean(),x.std(ddof=1)/np.sqrt(len(x))],atol=1e-12)

for source_path in [voc_path, env_path]:
    stem = source_path.stem
    src = load_workbook(source_path)
    dest = out/(stem+'_analysis.xlsx')
    target = load_workbook(dest)
    for sheet in src:
        assert list(sheet.values) == list(target[sheet.title].values), sheet.title
    new_sheets = {s: pd.read_excel(dest,sheet_name=s) for s in target.sheetnames if s not in src.sheetnames}
    write_sheets(dest,new_sheets)
    print(stem, 'original sheets preserved:', src.sheetnames)
print('PASS: all species/category/environment mean and SE independently verified; original sheet values unchanged.')
