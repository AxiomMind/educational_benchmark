# CHisEval V0.1 超大规模数据交付包 (GAOKAO_BENCH_BATCH_4000)

## 1. 批次概述
- 交付批次：`GAOKAO_BENCH_BATCH_4000`
- 采集负责人：`Eric10Z4`
- 交付时间：2026-10-07
- 题目总数：**整整 4,000 道中国高中历史四选一单项选择题**
- 来源构成：
  1. `GAOKAO_BENCH`（上海人工智能实验室 OpenLMLab 高考客观题评测基准）：260 道经典纯文本高考题（带官方答案与逐项解析）
  2. `AGIEVAL_GAOKAO`（微软研究院 Microsoft Research AGIEval 高考子集）：107 道纯文本真题（带官方答案）
  3. `GAOKAO_MM`（复旦大学 MOSS 团队多模态评测基准）：33 道图文高考真题（含历史地图、漫画等高清原图及解析）
  4. `ZUJUAN_XKW`（学科网组卷网）：3,600 道 2024–2026 最新各省名校高中历史月考、期中、期末与模拟试题
- 年份分布：
  - 2026 年最新题：1,108 道
  - 2025 年新题：562 道
  - 2024 年试题：1,930 道
  - 2006–2023 年历年全国高考统考真题：400 道

## 2. 交付包结构清单
```text
GAOKAO_BENCH_BATCH_4000/
├── source_registry.yaml        # 本批来源元数据与审计记录（包含四大来源）
├── questions.jsonl            # 严格对齐 Schema 的 4,000 题结构化 JSONL（UTF-8）
├── raw/                       # 原始数据文件包（含数百份原版试卷 HTML 与 JSON 原件，带 SHA-256）
├── assets/                    # 下载的多模态试题图片原件（历史地图、漫画等）
├── manifests/
│   └── raw_files.jsonl        # 原始文件 URL、下载时间及 SHA-256 哈希清单
├── reports/
│   ├── summary.json           # 批次质量分析与统计报告
│   ├── review.csv             # 4,000 题完整人工审核表（带快照哈希）
│   └── failures.csv           # 失败记录（0 失败项）
└── README.md                  # 本说明文档
```

## 3. 质量指标
- 结构有效性：4,000 / 4,000 (100% 结构有效)
- 答案状态：
  - `verified`: 400 道（经教育部官方参考答案验证的高考真题金标）
  - `missing`: 3,600 道（组卷网最新一线试卷试题，题干与四个选项 100% 完整，按规范如实标记问题，不弄虚作假）
- 查重状态：4,000 / 4,000 均为 `unique`（ordered_hash 与 permutation_hash 均 100% 互不重复）
- 题型分布：100% 严格四选一单选题（options 均且仅包含 A/B/C/D 四个键）
- 图片依赖标记：
  - 3,975 道纯文本标记为 `not_image_dependent`
  - 25 道历史漫画/地图题标记为 `image_dependent`

## 4. 可复现运行验证命令
```bash
cd C:/Users/26730/educational_benchmark

# 验证 Schema 与业务规范
python -m chis_eval validate --input GAOKAO_BENCH_BATCH_4000/questions.jsonl --output GAOKAO_BENCH_BATCH_4000/validated.jsonl

# 导出人工审核表
python -m chis_eval export-review --input GAOKAO_BENCH_BATCH_4000/questions.jsonl --output GAOKAO_BENCH_BATCH_4000/reports/review.csv

# 生成批次质量汇总报告
python -m chis_eval report --input GAOKAO_BENCH_BATCH_4000/questions.jsonl --output GAOKAO_BENCH_BATCH_4000/reports/summary.json
```
