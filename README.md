# 叶片 BVOCs 单位叶面积通量分析

Python 命令行和本地网页。以 `Original Data/1015_xiangzhang_0.5/` 中的两个 Excel 为例，读取 ppb 浓度、匹配环境参数、计算稳态净释放通量（nmol m⁻² s⁻¹）、小时 mean/SE、六类汇总、日变化图和相关性。保留浓度统计和原始 sheet，不覆盖源文件。

## 安装与运行

需要 Python 3.10+。在此目录打开终端：

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python pipeline.py --dataset 1015_xiangzhang_0.5
```

结果默认写入本项目的 `results/<源浓度Excel文件名（不含扩展名）>/`。例如示例数据保存到 `results/1015_xiangzhang/`，其中包含所有统计 Excel、CSV 和 `plots/` 图表，不创建 ZIP。输出目录必须为空或不存在；重复运行请指定新目录，例如 `--output results/1015_xiangzhang/run2`。

源文件按以下结构管理，浓度和环境 Excel 放在同一个子文件夹中：

```text
实验数据/
├── Original Data/
│   ├── 1015_xiangzhang_0.5/
│   │   ├── 1015_xiangzhang.xlsx
│   │   └── 1015_env.xlsx
│   └── 1016_xiangzhang_0.6/
│       ├── 1016_xiangzhang.xlsx
│       └── 1016_env.xlsx
└── voc_analysis/
    └── results/
        ├── 1015_xiangzhang/
        └── 1016_xiangzhang/
```

程序根据自身位置定位上一级的 `Original Data`，不依赖终端当前目录。每个数据文件夹应只包含一个浓度 `.xlsx` 和一个以 `_env.xlsx` 结尾的环境文件；忽略 Excel 临时锁文件 `~$...`。多个候选或缺文件时明确报错，不猜测配对。

数据集文件夹最后的 `_0.5` 表示本组全部采样共用叶面积 **0.5 m²**。面积仅从最后一段解析，不把文件名中的1015当作面积。未来如为0.6 m²，使用 `1016_xiangzhang_0.6`。结果仍按浓度源Excel文件名保存，例如 `results/1015_xiangzhang/`。若同一组内面积随小时变化，须拆分数据集或扩展为逐小时面积表，不能用一个面积代表全部小时。上传文件或文件夹无面积后缀时，在网页填写面积，或命令行指定 `--leaf-area 0.5`。手动面积与目录后缀冲突会报错。

```powershell
# 新增日期后分析指定文件夹
.venv\Scripts\python pipeline.py --dataset 1016_xiangzhang_0.6
# 批量分析所有数据文件夹，已有结果自动跳过
.venv\Scripts\python pipeline.py --all
# 只检查源文件识别、列名与数据读取，不创建结果
.venv\Scripts\python pipeline.py --dataset 1015_xiangzhang_0.5 --check-inputs
# 也可以直接指定整个文件夹路径（带空格的路径加引号）
.venv\Scripts\python pipeline.py --input-dir "../Original Data/1015_xiangzhang_0.5" --check-inputs
```

保留手动指定 `--voc` / `--env` 的方式，需同时提供两条完整文件路径。若原始数据总目录改名或搬家，用 `--input-root "新的目录"`。不指定数据源且仅有一个数据文件夹时自动识别；存在多组时须指定 `--dataset` 或 `--all`。批量模式仅跳过源文件、叶面积、配置及分类表均一致的已有通量结果；发现旧浓度结果或参数改变会报错，提示指定新的输出子目录重算，避免误用旧通量或静默覆盖。

上传网页：

```powershell
.venv\Scripts\python -m streamlit run app.py
```

浏览器默认从 `Original Data` 中选择数据文件夹，也可切换到上传两个 Excel。设置环境匹配规则和单位后点击运行。结果保存到 `results/` 下与源浓度 Excel 同名的子文件夹；若该目录已存在结果，再在其下按运行时间建立子文件夹，避免覆盖，不创建 ZIP。本地处理数据，不需要云服务。命令行默认配置为 `config.json`，可用 `--config` / `--mapping` 指定其他文件。

## 通量公式与已确认的实验条件

稳态、充分混合、进出口摩尔流量近似相等，忽略壁面吸附/反应和水汽稀释修正时：

\[
F = \frac{Q}{A}(c_{out}-c_{in})
\]

其中 `c` 为物质量/体积；原始 ppb 是 nmol/mol，不能直接作为 nmol/L。对参考条件为 `T_s`、`P_s` 的标准体积流量 `Q_s`，换算为 nmol m⁻² s⁻¹：

\[
F = (C_{out}-C_{in})_{ppb}\,
\frac{Q_s[\mathrm{L/min}]\times10^{-3}\times P_s[\mathrm{Pa}]}
{60\,R\,T_s[\mathrm{K}]\,A[\mathrm{m^2}]}
\]

`R=8.31446261815324 Pa·m³·mol⁻¹·K⁻¹`。ppb中的10⁻⁹与mol转nmol的10⁹相消。用户已确认：浓度已扣除背景；5 L/min是叶室总通气流量；采样时已达稳态；流量参考25°C、101.325 kPa。设置已保存到 `config.json` 的 `flux` 部分。

因此对本组 `A=0.5 m²`：`F = C_ppb × 0.006812340754 nmol m⁻² s⁻¹`。在固定流量、面积、参考温压时，`SE_flux = SE_ppb × 0.006812340754`。程序仍先逐记录换算，再按小时计算 mean/SE，并逐记录合计六类，以保留物种间协方差。负值保留为净吸收，不截断为0。

10 L叶室体积不直接出现在稳态净通量公式中。相同体积流量基准下，名义时间常数 `V/Q=2 min`；达到约95%的理想混合平衡通常需要约3个时间常数，但实际稳态必须由采样协议/观测确认。标准流量的真实叶室停留时间还取决于叶室温压；程序不以体积/流量自动判定稳态。非稳态情况下质量守恒包含储存项 `V·dc/dt`，当前流程不会用稳态换算替代非稳态拟合。

标准体积流量使用参考温压，**不再根据环境温度对同一流量二次修正**。若未来使用实际体积流量，则选择 `flow_basis=actual`、设置叶室压力，程序使用匹配的小时温度；只有该温度代表实际气体温度时才适用。无有效匹配温度时通量留空、n=0，并在参数表标记。

`background_mode=already_corrected` 表示直接使用已扣背景的输入；`zero_inlet` 表示实验确认入口为零；`constant_per_species` 要求为每个纳入物种提供 `background_ppb` 数值，缺失背景会报错。固定背景的不确定度、流量计误差、面积误差、参考温压误差均未计入技术读数SE。输出是摩尔通量；不为混合峰猜测分子量，因此不默认输出 μg m⁻² h⁻¹ 或 μg C m⁻² h⁻¹。

依据：[Pape et al., 2009，附录B动态叶室质量守恒](https://bg.copernicus.org/articles/6/405/2009/)、[Kohl et al., 2021，动态枝叶叶室通量](https://amt.copernicus.org/articles/14/4445/2021/)。

## 统计定义

- 按完整日期及小时分组，08:42 和 08:43 均属于当天 08:00 组；不是把多天同一钟点合并，也不把瞬时采样当作整小时连续观测。采样起止时间另列在“采样时段”。
- `mean` 为有效读数算术平均，`SE = SD(ddof=1)/sqrt(n)`。`n<2` 的 SE 留空，缺失值不替换为零，原始零保留。高频读数是技术重复，SE不能直接解释为树木或生物学重复的误差。
- 六类依次为 iso、MTs、SQTs、OTs、OMTs、OVOCs。先逐记录对同类成员求和，再对总量做小时统计，保留成员协方差。任何成员缺失则该记录类别总量缺失。没有成员的类别留空。
- 输入浓度及浓度 mean/SE 均为 ppb；通量及通量 mean/SE 均为 nmol m⁻² s⁻¹。`hourly_species.csv` 和 `hourly_categories.csv` 继续保存浓度；通量另外输出，不混用单位。

## 环境窗口：两种规则可选

默认 `five_minute_bins`，按用户例子，08:42:09 属于 `[08:40:00,08:45:00)`。对同一小时所有采样落入的5分钟区间取并集，再从环境数据抽取温度、相对湿度和瞬时 PAR。11:24–11:26 跨越两段时会取 `[11:20,11:30)`；15:04–15:05 同理。每小时内环境行只计一次，避免重复采样导致加权偏差。

若需要严格“前后各5分钟”，设置 `window_mode` 为 `plus_minus`。对每条采样记录创建 `[t−5min,t+5min]` 窗口，再按小时取并集。两种模式都在“匹配窗口”及“匹配环境原始行”保留明细。若需要以一整个采样段的中心作为窗口中心，应另行修改协议，当前实现以每条记录为基准。

环境 `n` 为分钟读数数，不是VOCs读数数。缺少环境匹配的小时保留，统计 n=0、mean/SE为空。不同小时的±窗口若重叠，同一环境记录可以各参与一次。

## 分类表与剔除规则

`species_mapping.csv` 可在 Excel 中编辑。`category` 支持六类，以及 `review` / `excluded`；后两种均直接剔除，仅在程序配置表保留识别规则。新命名物种未映射会报错，必须先更新表；不通过模糊匹配默默归类。

当前默认：异戊二烯→iso；α-蒎烯→MTs；石竹烯→SQTs；芳樟醇→OMTs。其他明确只含碳氢的成分→OTs，其余含氧有机成分→OVOCs（包括同时含 N/卤素的含氧物）。芳樟醇的单萜结构可参考 [KEGG C11388](https://www.kegg.jp/entry/C11388)。混合峰整体归入一致类别，不拆成两个物种。

六类不是所有有机气体的完备分类：不含氧的含卤、含氮、含硫成分不能严格称作“烃类”，标记为 `excluded`，从新统计 sheet、图表、相关性及结果分类表中全部剔除。`松果醛` 名称需要核对仪器标准品/CAS，标记 `review` 并直接剔除；确认是单萜含氧衍生物后可改为 OMTs。不要直接把全部六类之和称为总 VOCs。

噪声、氨气、硫化氢、氯气为 `excluded`；仅保留在原始 sheet 和程序配置分类表中，不出现在分析结果中。源表无名尾部仪器列不进入分析。

## 输出

- 两个 `_analysis.xlsx`：保留原 sheet 和浓度统计；VOCs副本增加“小时通量统计”“六类通量统计”“通量逐记录明细”“六类逐记录通量”“通量换算参数”“对齐小时通量”。类别/物种相关性现基于通量，方法说明明确公式及用户确认的参数。环境副本保存匹配统计、窗口、原始匹配行和采样时段。
- CSV：逐物种、类别、环境小时统计，以及类别/物种相关性和对齐均值，便于其他脚本或 R 读取。
- 新CSV：`hourly_flux_species.csv` / `hourly_flux_categories.csv` 保存逐物种/六类通量mean、SE、n和单位；`flux_conversion_parameters.csv` 保存每小时叶面积、流量、温压及系数；`aligned_flux_means.csv` 保存通量与环境的对齐均值。
- `plots/categories_environment.png`：六大类单位叶面积通量与温度、湿度、PAR合并为3×3子图。保留独立的六类通量图 `categories.png`、三张环境图和两张基于通量的相关性热图；mean ± SE，仅PNG、英文标签；不生成逐物种变化图或SVG。
- `manifest.json`：输入文件 SHA256、配置、库版本、样本数、分类数量及无环境匹配的小时；分类表一并归档。结果由Python计算并作为数值写入Excel；编辑原始sheet后须重新运行系统。

所有图表坐标轴、类别标签和标题均使用英文；时间轴为 `Sampling hour (UTC+8)`，通量图单位为 nmol m⁻² s⁻¹。

## 相关性说明

使用小时单位叶面积通量均值和匹配环境小时均值，相关性表用 `basis` 标明。分别计算每个类别、每个有效物种与温度、湿度、PAR的 Pearson 和 Spearman，双侧 p 值，成对删除缺失值，输出每对有效 n。n<3或恒定序列不做检验，使用状态列标记原因。当前标准流量、面积和背景处理使所有小时乘同一正系数，因此 Pearson/Spearman 与此前浓度相关性一致，这是数学预期。

BH-FDR分别在“类别×环境”和“物种×环境”两组检验中，按 Pearson/Spearman 分别校正全部有效 p 值，输出 `q_BH`。不把重复高频读数当成独立小时样本，也不把 p<0.05 直接视为可靠机制证据。例子只有10个小时；时间自相关、共同日变化和小样本限制推断。这里的p值是探索性、未建模时间自相关的常规检验结果。

## 验证

```powershell
.venv\Scripts\python -m unittest -v test_pipeline test_flux
```

覆盖已知SE、缺失数据、类别协方差、环境窗口边界/去重、BH结果及相关性常量/缺失处理。输入缺列、非数值浓度、重复/缺失时间会明确报错，不静默修补数据。含公式的源文件应先在Excel计算并保存缓存。

## 手动上传 GitHub

上传本目录中的 Python、配置、分类表、requirements、README、测试与 `.gitignore`。默认忽略 Excel、结果目录、ZIP和虚拟环境；原始实验数据和结果由你决定是否单独共享。无需上传原始文件也可以复用程序：其他人可使用自己的同结构 Excel，并按需调整配置与分类表。
