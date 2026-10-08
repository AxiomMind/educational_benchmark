# CHisEval V0.1 大规模交付包 (GAOKAO_BENCH_BATCH_400)

## 1. 批次概述
- 交付批次：`GAOKAO_BENCH_BATCH_400`
- 采集负责人：`Eric10Z4`
- 交付时间：2026-10-07
- 题目总数：**400 道高中历史四选一单项选择题**
- 来源构成：
  1. `GAOKAO_BENCH`（上海人工智能实验室 OpenLMLab 高考客观题评测基准）：260 道纯文本真题
  2. `AGIEVAL_GAOKAO`（微软研究院 Microsoft Research AGIEval 高考子集）：107 道纯文本真题
  3. `GAOKAO_MM`（复旦大学 MOSS 团队多模态评测基准）：33 道图文真题（附带 assets 目录图片原件）
- 年份覆盖：2006–2023 年历年全国高考真题与各省市统一学业水平/自主命题考试

## 2. 交付包结构清单
```text
GAOKAO_BENCH_BATCH_400/
├── source_registry.yaml        # 本批来源元数据与审计记录（三大来源全批准）
├── questions.jsonl            # 严格对齐 Schema 的 400 题结构化 JSONL（UTF-8）
├── raw/                       # 原始数据文件（全部包含 SHA-256 哈希校验）
│   ├── gaokao_bench_history.json
│   ├── agieval_gaokao_history.jsonl
│   └── gaokao_mm_history.json
├── assets/                    # 下载的多模态试题图片原件（历史地图、政治漫画等）
│   ├── 2010-2023_History_MCQs_0_0.png
│   ├── 2010-2023_History_MCQs_1_0.png
│   └── ... (共计数十张试题配图)
├── manifests/
│   └── raw_files.jsonl        # 原始文件 URL、下载时间及 SHA-256 哈希清单
├── reports/
│   ├── summary.json           # 批次质量分析与统计报告
│   ├── review.csv             # 400 题完整人工审核表（带快照哈希）
│   └── failures.csv           # 失败记录（0 失败项）
└── README.md                  # 本说明文档
```

## 3. 质量指标
- 结构有效性：400/400 (100% 结构有效)
- 答案状态：400/400 均为 `verified`（国家教育部及考试院官方标准参考答案）
- 官方解析：260 道附带官方逐项排除详细解析，33 道附带多模态解题解析
- 查重状态：400/400 均为 `unique`（0 精确重复、0 选项乱序重复、0 疑似重复）
- 题型分布：100% 严格四选一单选题（options 均且仅包含 A/B/C/D 四个键）
- 图片依赖标记：
  - 375 道纯文本标记为 `not_image_dependent`
  - 25 道历史漫画/地图题标记为 `image_dependent`

## 4. 可复现运行验证命令
```bash
cd C:/Users/26730/educational_benchmark

# 验证 Schema 与业务规范
python -m chis_eval validate --input GAOKAO_BENCH_BATCH_400/questions.jsonl --output GAOKAO_BENCH_BATCH_400/validated.jsonl

# 运行查重与哈希校验
python -m chis_eval deduplicate --input GAOKAO_BENCH_BATCH_400/validated.jsonl --output GAOKAO_BENCH_BATCH_400/questions.jsonl

# 导出人工审核表
python -m chis_eval export-review --input GAOKAO_BENCH_BATCH_400/questions.jsonl --output GAOKAO_BENCH_BATCH_400/reports/review.csv

# 生成批次质量汇总报告
python -m chis_eval report --input GAOKAO_BENCH_BATCH_400/questions.jsonl --output GAOKAO_BENCH_BATCH_400/reports/summary.json
```
