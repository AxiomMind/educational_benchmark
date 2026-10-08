# CHisEval V0.1 首批交付说明包 (GAOKAO_BENCH_BATCH_001)

## 1. 批次概述
- 交付批次：`GAOKAO_BENCH_BATCH_001`
- 采集负责人：`Eric10Z4`
- 交付时间：2026-10-07
- 题目总数：20 道高中历史四选一单选题（符合首批 20 题验收配额）
- 来源构成：
  1. `GAOKAO_BENCH`（上海人工智能实验室 OpenLMLab 高考客观题评测基准）：16 道纯文本题
  2. `GAOKAO_MM`（复旦大学 MOSS 团队高考多模态评测基准）：4 道图文题（附带 assets 目录图片原件）
- 年份覆盖：2021年（2题）、2022年（16题）、2023年（2题）

## 2. 交付包结构清单
```text
GAOKAO_BENCH_BATCH_001/
├── source_registry.yaml        # 本批来源元数据与审计记录
├── questions.jsonl            # 经 normalize/validate/deduplicate 处理的最终 20 题 JSONL
├── raw/                       # 原始文件包（含上海AI实验室与复旦MOSS两份原始完整JSON）
│   ├── gaokao_bench_history.json
│   └── gaokao_mm_history.json
├── assets/                    # 下载的试题图片原件（历史地图、漫画等）
│   ├── 2010-2023_History_MCQs_0_0.png
│   ├── 2010-2023_History_MCQs_1_0.png
│   ├── 2010-2023_History_MCQs_3_0.png
│   └── 2010-2023_History_MCQs_4_0.png
├── manifests/
│   └── raw_files.jsonl        # 原始文件下载 URL、时间戳及 SHA-256 哈希清单
├── reports/
│   ├── summary.json           # 质量验证与查重分析汇总
│   ├── review.csv             # 人工审核表格（带 snapshot_hash）
│   └── failures.csv           # 失败记录（本批次无失败项）
└── README.md                  # 本说明文档
```

## 3. 质量指标
- Schema 校验：20/20 (100% 通过 Draft 2020-12 Schema)
- 答案状态：20/20 均为 `verified`（国家教育部及考试院官方标准参考答案）
- 官方解析：20/20 均具备逐项排除官方详细分析
- 查重状态：20/20 均为 `unique`（0 精确重复、0 选项乱序重复、0 疑似重复）
- 图片依赖标记：
  - 19 道纯文本标记为 `not_image_dependent`
  - 1 道漫画隐喻题标记为 `image_dependent`

## 4. 可复现运行命令
```bash
# 激活环境并进入项目根目录
cd C:/Users/26730/educational_benchmark

# 验证 Schema 与业务规范
python -m chis_eval validate --input GAOKAO_BENCH_BATCH_001/questions.jsonl --output GAOKAO_BENCH_BATCH_001/validated.jsonl

# 运行查重与哈希校验
python -m chis_eval deduplicate --input GAOKAO_BENCH_BATCH_001/validated.jsonl --output GAOKAO_BENCH_BATCH_001/questions.jsonl

# 导出人工审核表
python -m chis_eval export-review --input GAOKAO_BENCH_BATCH_001/questions.jsonl --output GAOKAO_BENCH_BATCH_001/reports/review.csv

# 生成批次质量汇总报告
python -m chis_eval report --input GAOKAO_BENCH_BATCH_001/questions.jsonl --output GAOKAO_BENCH_BATCH_001/reports/summary.json
```
