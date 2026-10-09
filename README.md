# Adhesion to ECoG: Evaluating Flexible Cortical Electrodes

**从剥离黏附到皮层电记录质量：建立柔性 ECoG 电极的可追溯评价流程。**

本项目要回答的问题是：材料在界面上的黏附表现，能否与电极的电学稳定性及最终的皮层脑电记录质量建立可检验的联系？为此，项目按“材料原始曲线 → 同一样品的器件指标 → ECoG 记录质量”组织数据，保留样品和独立制备批次的对应关系。

**当前进度：** 已实现 90° 剥离实验原始拉力 CSV 的读取、单位宽度峰值剥离力计算、批次汇总和曲线绘图；电极阻抗、弯折/浸泡稳定性及 ECoG 信号分析是后续接入的研究计划，目前仓库没有用这些未来指标得出材料性能结论。研究问题、阶段安排及 RP 表述见 [PROJECT_IDEA.md](PROJECT_IDEA.md)。

## 现在能运行什么

`peel_analysis.py` 读取实验仪导出的重复列 `时间_1,力_1,位移_1,...`，对每条曲线计算：

`单位宽度峰值剥离力 (N/m) = 原始峰值拉力 (N) / 有效宽度 (m)`

程序不使用平滑后的曲线求峰值，不把 N/m 称作界面断裂能。结果保留原始文件的 SHA-256 摘要、每条曲线的峰值、同批均值和跨批汇总。只有一个独立批次时，跨批标准差保持为空。

## 输入准备

复制 `manifest.example.json` 为 `manifest.json`，逐项填写真实的原始 CSV 路径和实验记录。`sample_set_id` 标识一个原始 CSV 文件；`batch_id` 标识一次独立制备。同一文件里的多条曲线仍属于该批次。有效宽度必须以实验记录为准，不能从文件名推断。

| 字段 | 含义 | 例子 |
| --- | --- | --- |
| `sample_set_id` | 原始文件的唯一编号 | `S001` |
| `batch_id` | 独立制备批次 | `B001` |
| `formulation_id` | 可公开的配方代号 | `D4_A` |
| `treatment` | 表面处理代号 | `untreated` |
| `substrate` | 剥离所接触的基底 | `glass` |
| `width_mm` | 实际有效剥离宽度，mm | `4.0` |
| `raw_file` | 仪器原始 CSV 路径 | `data/raw/example.csv` |

建议在实验室私有记录中另存样品厚度、压合载荷、接触时间、剥离速度、角度、湿态条件、试片照片、失败模式和实验日期。缺失的条件保持缺失，不从曲线倒推。

## 运行

需要 Python 3.10+ 和 pandas。

```bash
python -m pip install -r requirements.txt
python peel_analysis.py manifest.json --out results.json
python plot_curves.py manifest.json --out-dir figures
python -m unittest discover -s tests -v
```

`results.json` 分为 `curves`、`batches` 和 `conditions`。第一层是每条重复曲线，第二层先汇总独立制备批次，第三层才比较配方条件。程序也会输出所读取文件的编码和哈希，便于之后复核 Origin 图与报告数值。

`figures/` 中的 SVG 展示每条原始力–位移曲线。为保持文件可读，图中对过密采样点只做显示抽稀；所有峰值仍从完整原始列计算。CSV 没有写位移单位，图轴因而明确标为“原始导出单位，请核实”。

## 公共仓库边界

仓库可公开方法、空白 manifest 和获得授权的数据。`manifest.json`、仪器原始数据及运行结果默认被 `.gitignore` 排除。公开示例可以另外用模拟数据生成，并明确标为模拟；不要把模拟结果写成材料实测结果。

## 本项目的阶段

1. 材料：从原始力–位移曲线建立可复算的黏附指标。
2. 电极：用同一 `sample_id` 接入弯折/浸泡前后线路电阻、1 kHz 阻抗和封装检查。
3. ECoG：在批准的实验设计下接入接触状态、坏道率、工频噪声、基线漂移、可用记录时长以及由专业人员标注的事件。
4. 联合分析：按独立制备批次比较材料、电学和记录指标；数据足够后再评估小样本配方推荐模型。

公开颅内脑电数据可用于练习第三阶段的信号处理，但不包含本课题材料的标签，因此不能用来评价本课题配方。

