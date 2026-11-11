# 数据字段与质量状态

题库采用 UTF-8 JSONL，每行一道题。机器可读约束为 [question_schema.json](../schemas/question_schema.json)，这是本项目自定义格式。

| 字段 | 含义 |
|---|---|
| question_id / record_version | 稳定题号与记录版本；删除重复题后不重新编号 |
| group_id / shared_material | 同组题目和共享材料；用于防止跨数据划分泄漏 |
| raw_question / raw_options | 保留的解析原值 |
| question / normalized_question / options | 当前题干和选项；两个题干字段必须一致 |
| answer / answer_explanation | 答案字母及解析，解析可为空 |
| answer_evidence | 每条来源的答案声明、URL 和已有证据 |
| has_image / image_paths | 是否绑定图片、相对于当前数据集目录的图片路径 |
| source / source_records | 主来源和其他已知出处 |
| labels | 能力、历史范围、时期、知识点、材料类型；当前尚未标注 |
| quality | 答案、重复、解析、审核、图片依赖状态与问题列表 |
| provenance | 原始文件、哈希、清洗变化和源题号 |

## 哈希与原始文件

- `content_hash`：原始下载文件的 SHA-256，与 `manifests/raw_files.jsonl` 对应。
- `ordered_hash`：材料、题干和有序选项的哈希。
- `permutation_hash`：材料、题干和排序后选项的哈希，用于发现选项换序。
- 内容变更后应重算哈希，增加 `record_version`，并记录修改依据。
- 整理时合并的重复来源保存在 `source_records`、`provenance.merged_occurrences` 中；后者保留旧题号、原答案字母、正确选项内容与旧提交。

## 状态的含义

`single_source` 仅表示有单来源答案声明，不等同于正确答案已经核验。当前题库没有人工审核通过的记录。

`parse_status: valid` 只表示现有业务检查未发现结构问题。它不证明年份、图片题意和 OCR 解析完全正确。

`duplicate_status: unique` 不能代替完整语义查重。图像变体 `CHIS_000273`、`CHIS_002769` 保留为 `suspected_duplicate`，并使用相同的题组 ID。

`image_dependency: image_dependent` 表示作答需要图像，即使实际图像缺失也应保持这一标记。`CHIS_000312`、`CHIS_000363` 已记录 `missing_required_image`，使用前需补图或排除。

汇总报告中的 qualified 需要同时满足结构有效、答案已验证、人工审核通过、唯一且不依赖图片等条件。当前值为 0；这不是“全部答案错误”的意思。

## 人工审核

```bash
python -m chis_eval export-review --input datasets/history/questions.jsonl --output data/reviewed/history.csv
python -m chis_eval merge-review --input datasets/history/questions.jsonl --review data/reviewed/history.csv --output data/reviewed/history.reviewed.jsonl
```

CSV 只接受审核状态、审核人和备注的回填。快照哈希可防止旧表覆盖已修改的题目；题干、选项、答案等内容修正应直接在候选 JSONL 中完成后重新生成审核表。

## 尚未完成的质量工作

历史年份包含试卷标题、引用和录入时间的推断，不能直接作为准确考试日期；部分 OCR 解析存在错字、断行和语序问题；107 条 AGIEval 记录没有解析；能力及知识点标签为空。目录整理和去重没有宣称解决这些问题。

来源权限沿用配置记录：采集批准不等于再分发授权，当前配置没有给出公开再分发许可。任何正式对外发布仍需核对上游数据与图片的实际授权。
