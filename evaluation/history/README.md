# 高中历史选择题的 Direct / CoT 配对评测

2026 年 11 月，A、B、C、D 四组共测了八个模型。每个模型都回答同一批 3,993 题，每题独立请求两次，一次直接作答，一次先写简短分析再作答。每个模型有 7,986 条正式记录，全组共 63,888 条。356 题带图，3,637 题为纯文字。每个模型覆盖全部解题能力和历史板块，可在同一批题上比较两种提示的表现。

## 先用两道示例检查环境

在仓库根目录执行下列命令。需要 Python 3.9 或更高版本，只使用标准库。示例是一道时序题和一道自制图表题。

```bash
cd evaluation/history
python3 evaluate.py --data example/eval_inputs.jsonl --dry-run
```

预览会显示两套提示、两道题、一张题图和四次计划调用。只预览不产生 API 费用。要实际试跑，选择下表的一份配置，使用对应平台的 Key。程序在交互终端隐藏输入，也可以读取环境变量 `CHISEVAL_API_KEY`。

```bash
python3 evaluate.py --data example/eval_inputs.jsonl --config configs/B1.json --output runs/B1/example
python3 score_submissions.py runs/B1/example --data example/eval_key.jsonl --output scores-example
```

## 正式运行

正式评测使用从当时的 4,000 题交付包冻结的快照，其中 7 题因质量问题暂缓。仓库首页的 3,995 题是另一版本。下面的导入命令从本地 ABCD 完成包或其中的协调端 ZIP 读取数据，核对冻结包指纹和各图的 SHA-256。示例命令中的压缩包路径请替换为实际位置。

```bash
python3 import_formal_data.py "/path/to/CHisEval_ABCD测评完成版_20261118.zip"
python3 evaluate.py --dry-run
python3 evaluate.py --config configs/B1.json --limit 2 --output runs/B1/smoke
python3 evaluate.py --config configs/B1.json --output runs/B1/full
python3 score_submissions.py runs/B1/full --output scores-B1
```

全量预览应显示 3,993 题、356 道图题、7,986 次基础调用。按模型更换配置和输出目录。恢复中断时重用同一条运行命令和同一个目录。用 `--max-calls N` 可限制本次请求数，含重试。试跑与全量应使用不同目录。统一评分可在同一条命令中传入多个完整运行目录，输出参数指向一个新的目录。

| 组别 | 配置及实际请求的模型 ID |
| --- | --- |
| A | A1 `deepseek-flash`、A2 `hy4`（腾讯混元） |
| B | B1 `qwen3.5-flash-2026-02-23`、B2 `qwen3-vl-plus` |
| C | C1 `glm-4.6v-flash`、C2 `glm-4.6v` |
| D | D1 `gemini-3.1-flash-lite`、D2 `gemini-3.5-flash-lite` |

配置根据历史运行清单整理。这些 ID 和参数记录当时的服务状态。D 组使用反向代理，模型 ID 是代理接受的名称，上游版本未独立核实。仓库提供统一命令行入口。D 的默认地址指向运行程序的本机代理；在其他机器复跑时，需在配置副本中填入自己的兼容端点。

## 输入、提示词和判分

- 每次请求只组装题干、选项、共享材料和随题图片。参考答案、能力与历史板块标签由评分端保管。程序按题目所列次序把原图编码到请求里。
- [Direct 原提示词](prompts/direct.txt) 要求只给一行“答案：X”。[CoT 原提示词](prompts/cot.txt) 要求先用 1–3 个简短步骤说明依据，最后另起一行作答。这里的 CoT 指回答中可见的分析。同一模型两种条件使用相同的生成参数，输出上限为 1,024 token。
- 评分先规范化全角字符、去空行，再取最后一行的 A–D。Direct 要求恰有一行，CoT 要求答案前有分析行。重复答案行、截断、拒答和 API 失败分别记状态。正式准确率等于答对题数除以 3,993，有记录的失败项计零分。尚未完成的请求在评分摘要中单列为 pending。
- 按事实知识、时序与阶段理解、史料与语境理解、因果及证据推理四类能力，以及六个历史板块分别统计。标签保留了 AI 初标和自动分类结果，仍需人工复核。全量包含用于调试的 200 道开发题。
- 同一模型按题号配对计算 CoT 减 Direct 的准确率差，并记录“错转对”和“对转错”。评分程序同时输出 Wilson 区间、配对 bootstrap 区间和精确 McNemar 检验。最终报告另对八个模型的总体检验作 Holm 校正，并单列纯文字题与带图题。

## 怎样复核已经完成的实验

`run.json` 保存数据和提示词指纹，`results.jsonl` 保存逐题响应。统一评分核对请求内容，再从原始响应抽取答案，生成 `scored_results.jsonl`、`summary.json` 和 `error_cases.csv`。核对全量结果时，八个模型都应有 3,993 个已完成配对。

已有 ABCD 完成版的组员可以解压后在包内运行 `python3 复评分.py`，直接使用四组历史响应重建逐题得分、汇总和异常清单，无需 API Key。仓库中的示例和程序可公开查看；正式题面、答案、原图和组员原始提交由原交付包提供。来源范围见[仓库来源登记](../../config/source_registry.yaml)。
