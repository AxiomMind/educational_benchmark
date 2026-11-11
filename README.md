# CHisEval：高中历史题库与爬虫

用于采集、解析和整理中国高中历史选择题。仓库保留四个来源的爬虫适配器、答案原图下载与 OCR 工具，以及一份可追溯的历史题库。

当前题库共 **3,995 题**，位于 [datasets/history/questions.jsonl](datasets/history/questions.jsonl)。它包含高考真题、模拟题、专题练习和课后作业，仍处于审核阶段，不能直接等同于已人工验证的标准评测集。

## 目录结构

```text
educational_benchmark/
├── README.md
├── pyproject.toml                 # Python 包、依赖和命令入口
├── package.json                  # 可选：交互登录脚本依赖
├── package-lock.json
├── config/
│   └── source_registry.yaml      # 唯一的来源配置、采集范围与授权记录
├── src/chis_eval/
│   ├── __main__.py               # python -m chis_eval
│   ├── cli.py                    # 采集、解析、清洗、查重和报告命令
│   ├── config.py                 # 来源配置检查
│   ├── models.py                 # 统一题目数据结构
│   ├── errors.py                 # 异常类型
│   ├── crawlers/
│   │   ├── base.py               # HTTP 下载、限速、重试、断点续采
│   │   └── adapters/
│   │       ├── gaokao_bench.py   # OpenLMLab GAOKAO-Bench
│   │       ├── agieval.py        # AGIEval 高考历史子集
│   │       ├── gaokao_mm.py      # OpenMOSS GAOKAO-MM
│   │       └── zujuan.py         # 组卷网试卷解析与列表采集
│   ├── parsers/                  # HTML、PDF、答案与可选 OCR 解析
│   ├── pipeline/                 # 标准化、校验、查重、审核与导出
│   └── storage/                  # JSONL、原始文件、SQLite 采集状态
├── scripts/
│   ├── login.js                  # 浏览器交互登录，本地保存会话
│   ├── fetch_answer_images.py    # 下载答案原图并记录 SHA-256
│   ├── batch_ocr_answers.py      # 离线 OCR，冲突答案不自动选取
│   ├── apply_crawled_answers.py  # 回填缺失答案到新文件并校验
│   └── check_dataset.py          # 离线验证当前题库及资源完整性
├── datasets/history/
│   ├── questions.jsonl           # 当前唯一维护的题库，3,995 题
│   ├── assets/                   # 被保留题目引用的 365 个图片文件
│   ├── raw/                      # 保留的 261 个原始 HTML/JSON/JSONL
│   ├── manifests/
│   │   └── raw_files.jsonl       # 原始文件来源、采集时间、SHA-256
│   └── reports/
│       ├── summary.json          # 当前质量统计
│       └── cleanup.json          # 去重决定和移除文件清单
├── schemas/                      # 题目、来源配置、审核字段的 JSON Schema
├── tests/                        # 离线单元测试
└── docs/
    ├── crawler_usage.md          # 采集和答案处理操作说明
    ├── data_schema.md            # 字段含义、审核规则和已知限制
    └── maintenance.md            # 本次整理记录与后续维护方法
```

运行时产生的 `data/`、`logs/`、`.venv/`、`node_modules/` 自动创建并由 Git 忽略。Cookie、答案原图缓存和临时审核表不纳入版本管理。

## 当前数据

| 主来源 | 题数 |
|---|---:|
| GAOKAO-Bench | 260 |
| AGIEval 高考历史 | 107 |
| GAOKAO-MM | 33 |
| 学科网组卷网 | 3,595 |
| **合计** | **3,995** |

2026-11-11 整理时，从原有 4,000 题中移除了 5 条确认重复的记录，保留原题号，合并其来源信息。题号因此不连续。另有 2 条题干相似但配图不同的图像变体保留在同一个 `group_id` 中。

当前质量边界：

- 3,995 题都有 A/B/C/D 答案，但全部仍为 `single_source`，人工审核状态均为 `pending`。
- 107 题没有解析；部分已有解析存在 OCR 错字或断行，未做全量人工校订。
- 345 题标记为依赖图片，其中 `CHIS_000312`、`CHIS_000363` 缺少必要漫画，已标记待处理。
- 历史批次的年份含推断值，尚未逐题核对真实考试日期；知识点、能力等标签尚未标注。
- 完全相同的文本哈希不等于完整的语义查重；后续仍应复核相似题和图像变体。

详细统计见 [summary.json](datasets/history/reports/summary.json)，去重依据见 [cleanup.json](datasets/history/reports/cleanup.json)。

## 安装

Python 3.10 或以上版本。下面以 Windows PowerShell 为例：

```powershell
git clone https://github.com/AxiomMind/educational_benchmark.git
cd educational_benchmark
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

macOS / Linux 使用 `source .venv/bin/activate` 激活环境。PDF 解析和 PaddleOCR 是可选功能，需要时再安装 `.[pdf]` 或 `.[pdf,ocr]`；答案原图脚本单独使用 Tesseract。

## 快速开始

先检查现有题库：

```bash
python scripts/check_dataset.py
python -m pytest -q
```

采集一个公开上游数据文件，并解析到本地工作目录：

```bash
python -m chis_eval crawl --source GAOKAO_BENCH --limit 1 --dry-run
python -m chis_eval crawl --source GAOKAO_BENCH --limit 1
python -m chis_eval parse --source GAOKAO_BENCH --output data/parsed/gaokao_bench.jsonl
python -m chis_eval normalize --input data/parsed/gaokao_bench.jsonl --output data/cleaned/gaokao_bench.jsonl
python -m chis_eval validate --input data/cleaned/gaokao_bench.jsonl --output data/cleaned/gaokao_bench.validated.jsonl
```

导出当前题库的审核表：

```bash
python -m chis_eval export-review --input datasets/history/questions.jsonl --output data/reviewed/history.csv
```

组卷网登录、答案图片下载、OCR 与回填步骤见 [爬虫使用说明](docs/crawler_usage.md)。所有生成任务默认写入本地 `data/`，不会自动提交或推送到 GitHub。

## 维护原则

- 当前题库只维护 `datasets/history/` 一份；旧的 20 题、400 题交付批次可从 Git 历史恢复。
- 保留题干、选项、原始文件及来源证据；重复转载来源不自动升级为独立验证答案。
- 清洗后同步重算内容哈希和质量报告；人工审核 CSV 按需生成，避免保留过期快照。
- 划分训练集、验证集或测试集时，至少按题组和重复题簇处理；已有公开基准题还需考虑模型训练污染。
- 来源的采集状态和再分发权限分别记录在 `config/source_registry.yaml`。当前来源仍标记为 `research_only`、`redistribution_allowed: false`，本次目录整理不代表新增授权。

参见 [字段说明](docs/data_schema.md) 和 [整理与维护记录](docs/maintenance.md)。
